import os
import json
import time
import hmac
import hashlib
import calendar
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.leads.billing import BillingError, create_checkout_session
from apps.leads.models import AuditRequest, ClientProject, UsageRecord, WorkspacePlan, WorkspaceSubscription
from apps.seo.models import SEOContextSnapshot, SEOProjectProfile
from apps.aeo.models import AEOAudit
from apps.tools.automation import process_due_workspace_schedules
from apps.tools.jobs import enqueue_public_site_audit
from apps.tools.notifications import deliver_workspace_audit_notifications
from apps.tools.reporting import create_audit_change_report

from .admin_utils import get_service_recommendations
from .models import AuditChangeReport, AuditIssue, AuditPage, AuditRun, AuditShareLink, WorkspaceAuditSchedule
from .recommendations import build_audit_summary
from .scoring import apply_audit_scores
from .services import get_pagespeed_api_key, run_public_site_audit


class PublicAuditFlowTests(TestCase):
    @patch("apps.tools.views.enqueue_public_site_audit")
    def test_public_audit_submission_creates_run_and_redirects(self, mocked_enqueue):

        response = self.client.post(
            reverse("tools:free-seo-audit"),
            {
                "company_name": "Northwind",
                "email": "ops@example.com",
                "website": "example.com",
                "business_type": "saas",
                "location": "Nairobi, Kenya",
                "target_goal": "Increase demo requests",
                "primary_service": "Revenue operations platform",
                "monthly_leads_goal": 40,
                "notes": "Run a first-pass audit.",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(AuditRequest.objects.count(), 1)
        self.assertEqual(AuditRun.objects.count(), 1)
        self.assertEqual(ClientProject.objects.count(), 1)
        self.assertEqual(ClientProject.objects.get().business_type, "saas")
        self.assertIn("/tools/audits/", response["Location"])
        mocked_enqueue.assert_called_once()

    @patch("apps.tools.views.enqueue_public_site_audit")
    def test_public_audit_submission_reuses_existing_inflight_run_for_same_domain(self, mocked_enqueue):
        audit_request = AuditRequest.objects.create(
            company_name="Northwind",
            email="ops@example.com",
            website="https://example.com",
        )
        existing_run = AuditRun.objects.create(
            audit_request=audit_request,
            normalized_domain="example.com",
            start_url="https://example.com/",
            status=AuditRun.Status.RUNNING,
        )

        response = self.client.post(
            reverse("tools:free-seo-audit"),
            {
                "company_name": "Northwind",
                "email": "ops@example.com",
                "website": "example.com",
                "business_type": "agency",
                "location": "Nairobi, Kenya",
                "target_goal": "Increase qualified leads",
                "primary_service": "SEO consulting",
                "monthly_leads_goal": 40,
                "notes": "Run a first-pass audit.",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("tools:audit-result", args=[existing_run.pk]))
        self.assertEqual(AuditRun.objects.count(), 1)
        self.assertEqual(AuditRequest.objects.count(), 1)
        mocked_enqueue.assert_not_called()

    def test_pending_audit_result_shows_processing_state(self):
        audit_run = AuditRun.objects.create(
            normalized_domain="example.com",
            start_url="https://example.com/",
            status=AuditRun.Status.PENDING,
        )

        response = self.client.get(reverse("tools:audit-result", args=[audit_run.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Audit In Progress")
        self.assertContains(response, "This page refreshes automatically")

    def test_completed_audit_result_exposes_pdf_actions(self):
        audit_run = AuditRun.objects.create(
            normalized_domain="example.com",
            start_url="https://example.com/",
            status=AuditRun.Status.COMPLETED,
            overall_score=78,
            summary={
                "score_breakdown": {},
                "recommendations": [],
                "performance_metrics": [
                    {
                        "short_label": "LCP",
                        "label": "Largest Contentful Paint (LCP)",
                        "value": "2.4 s",
                        "target_label": "<= 2.5s",
                        "status": "strong",
                        "description": "Shows how quickly the main content becomes visible.",
                        "impact": "Main content renders in an acceptable range.",
                    },
                    {
                        "short_label": "TTFB",
                        "label": "Time to First Byte (TTFB)",
                        "value": "920 ms",
                        "target_label": "<= 800ms",
                        "status": "warning",
                        "description": "Shows how quickly the server starts responding to the first request.",
                        "impact": "The server is slow to respond, which delays rendering and undermines trust.",
                    },
                ],
            },
        )

        response = self.client.get(reverse("tools:audit-result", args=[audit_run.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "View PDF Report")
        self.assertContains(response, reverse("tools:audit-report-pdf", args=[audit_run.pk]))
        self.assertContains(response, "Time to First Byte (TTFB)")
        self.assertContains(response, "Largest Contentful Paint (LCP)")

    def test_completed_audit_result_tolerates_none_scores_in_summary(self):
        audit_run = AuditRun.objects.create(
            normalized_domain="example.com",
            start_url="https://example.com/",
            status=AuditRun.Status.COMPLETED,
            overall_score=78,
            summary={
                "scores": {
                    "technical": None,
                    "aeo": 61,
                    "on_page": None,
                },
                "score_breakdown": {},
                "recommendations": [],
            },
        )

        response = self.client.get(reverse("tools:audit-result", args=[audit_run.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Audit Analysis: example.com")

    def test_completed_audit_report_pdf_returns_pdf_response(self):
        audit_run = AuditRun.objects.create(
            normalized_domain="example.com",
            start_url="https://example.com/",
            status=AuditRun.Status.COMPLETED,
            overall_score=78,
            pages_crawled=4,
            summary={
                "score_breakdown": {
                    "technical": {"label": "Technical", "score": 70, "status": "weak", "issues": 2}
                },
                "recommendations": [
                    {
                        "title": "Fix missing title tags",
                        "category": "On-page",
                        "priority_score": 84,
                        "description": "Important pages are missing titles.",
                        "recommended_fix": "Add unique titles.",
                        "estimated_impact": "Improves click-through rate.",
                        "page_url": "https://example.com/about/",
                        "technical_steps": ["Inspect the title tag on the affected page."],
                    }
                ],
                "issue_summary": {"total": 2, "by_category": {"on_page": 2}},
                "performance_metrics": [
                    {
                        "key": "largest_contentful_paint",
                        "label": "Largest Contentful Paint (LCP)",
                        "value": "4.2 s",
                        "target_label": "<= 2.5s",
                        "status": "critical",
                        "impact": "Main content loads late enough to cause abandonment and ranking pressure.",
                    },
                    {
                        "key": "server_response_time",
                        "label": "Time to First Byte (TTFB)",
                        "value": "1.9 s",
                        "target_label": "<= 800ms",
                        "status": "critical",
                        "impact": "Server response is slow enough to drag down the full page experience and follow-on metrics.",
                    },
                ],
            },
        )

        response = self.client.get(reverse("tools:audit-report-pdf", args=[audit_run.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))
        self.assertIn(b"Strategic fix: Add unique titles.", response.content)
        self.assertIn(b"Where found: https://example.com/about/", response.content)
        self.assertIn(b"Time to First Byte \\(TTFB\\)", response.content)

    def test_pending_audit_report_pdf_returns_409(self):
        audit_run = AuditRun.objects.create(
            normalized_domain="example.com",
            start_url="https://example.com/",
            status=AuditRun.Status.PENDING,
        )

        response = self.client.get(reverse("tools:audit-report-pdf", args=[audit_run.pk]))

        self.assertEqual(response.status_code, 409)

    def test_missing_audit_result_redirects_public_user_to_home(self):
        response = self.client.get(reverse("tools:audit-result", args=[999999]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("core:home"))

    def test_missing_audit_result_redirects_authenticated_user_to_workspace(self):
        user = get_user_model().objects.create_user(
            username="workspace-user",
            email="workspace@example.com",
            password="testpass123",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("tools:audit-result", args=[999999]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("tools:workspace-dashboard"))

    @patch("apps.tools.services.fetch_pagespeed_insights")
    @patch("apps.tools.services.safe_fetch")
    def test_public_site_audit_generates_scores_and_issues(self, mocked_fetch, mocked_pagespeed):
        homepage_html = """
        <html>
            <head>
                <title>Home</title>
                <meta name='description' content=''>
            </head>
            <body>
                <a href='/about/'>About</a>
                <p>Short page.</p>
            </body>
        </html>
        """
        about_html = """
        <html>
            <head>
                <title>About Example Company With A Very Long Title That Exceeds Limits</title>
                <link rel='canonical' href='https://example.com/about/' />
            </head>
            <body>
                <h1>About</h1>
                <img src='/hero.jpg'>
                <p>This page has enough text to be parsed but no schema and very limited structure for AI-ready answers.</p>
            </body>
        </html>
        """

        def fake_fetch(url, session=None, timeout=8):
            if url == "https://example.com/":
                return {
                    "final_url": url,
                    "status_code": 200,
                    "body": homepage_html,
                    "content_type": "text/html",
                    "response_time_ms": 900,
                }
            if url == "https://example.com/robots.txt":
                return None
            if url == "https://example.com/sitemap.xml":
                return None
            if url == "https://example.com/about/":
                return {
                    "final_url": url,
                    "status_code": 200,
                    "body": about_html,
                    "content_type": "text/html",
                    "response_time_ms": 2200,
                }
            return None

        mocked_fetch.side_effect = fake_fetch
        mocked_pagespeed.return_value = {
            "source": "Google PageSpeed Insights",
            "strategy": "mobile",
            "score": 84,
            "analysis_timestamp": "2026-03-26T12:00:00Z",
            "metrics": {
                "first_contentful_paint": "1.1 s",
                "largest_contentful_paint": "2.4 s",
                "cumulative_layout_shift": "0.02",
                "total_blocking_time": "120 ms",
                "speed_index": "2.0 s",
            },
        }

        audit_run = AuditRun.objects.create(
            normalized_domain="example.com",
            start_url="https://example.com/",
        )

        run_public_site_audit(audit_run=audit_run, page_limit=2)
        audit_run.refresh_from_db()

        self.assertEqual(audit_run.status, AuditRun.Status.COMPLETED)
        self.assertEqual(audit_run.pages_crawled, 2)
        self.assertGreater(AuditIssue.objects.filter(audit_run=audit_run).count(), 0)
        self.assertIn("scores", audit_run.summary)
        self.assertIn("score_breakdown", audit_run.summary)
        self.assertIn("recommendations", audit_run.summary)
        self.assertIn("product_modules", audit_run.summary)
        self.assertEqual(audit_run.performance_score, 84)
        self.assertEqual(audit_run.summary["pagespeed"]["source"], "Google PageSpeed Insights")

    @patch("apps.tools.services.fetch_pagespeed_insights")
    @patch("apps.tools.services.safe_fetch")
    def test_public_site_audit_includes_context_analysis_when_competitors_are_supplied(self, mocked_fetch, mocked_pagespeed):
        homepage_html = """
        <html><head><title>Northwind</title></head><body><h1>Northwind</h1><p>Main homepage copy.</p></body></html>
        """
        competitor_html = """
        <html><head><title>Competitor</title><meta name='description' content='Competing offer'></head><body><h1>Competitor headline</h1><p>This competitor page has more words than the target homepage. It is longer and more detailed for benchmark testing.</p><script type='application/ld+json'>{}</script></body></html>
        """

        def fake_fetch(url, session=None, timeout=8):
            if url == "https://example.com/":
                return {
                    "final_url": url,
                    "status_code": 200,
                    "body": homepage_html,
                    "content_type": "text/html",
                    "response_time_ms": 900,
                    "headers": {},
                }
            if url == "https://example.com/robots.txt":
                return None
            if url == "https://example.com/sitemap.xml":
                return None
            if url == "https://competitor.com/":
                return {
                    "final_url": url,
                    "status_code": 200,
                    "body": competitor_html,
                    "content_type": "text/html",
                    "response_time_ms": 600,
                    "headers": {},
                }
            return None

        mocked_fetch.side_effect = fake_fetch
        mocked_pagespeed.return_value = None

        audit_request = AuditRequest.objects.create(
            company_name="Northwind",
            email="ops@example.com",
            website="https://example.com",
            market_context="Used vehicle market in Nairobi with price-sensitive buyers.",
            competitor_urls=["https://competitor.com"],
        )
        audit_run = AuditRun.objects.create(
            audit_request=audit_request,
            normalized_domain="example.com",
            start_url="https://example.com/",
        )

        run_public_site_audit(audit_run=audit_run, page_limit=1)
        audit_run.refresh_from_db()

        self.assertIn("context_analysis", audit_run.summary)
        self.assertIn("market_context", audit_run.summary["context_analysis"])
        self.assertEqual(audit_run.summary["context_analysis"]["competitors"][0]["url"], "https://competitor.com/")


class AuditScoringTests(TestCase):
    def test_pagespeed_api_key_prefers_webspeed_name(self):
        with patch.dict(
            os.environ,
            {"webspeed": "primary-key", "PAGESPEED_API_KEY": "legacy-key"},
            clear=False,
        ):
            self.assertEqual(get_pagespeed_api_key(), "primary-key")

    def test_issue_based_performance_score_is_used_without_pagespeed(self):
        audit_run = AuditRun.objects.create(
            normalized_domain="example.com",
            start_url="https://example.com/",
        )
        AuditIssue.objects.create(
            audit_run=audit_run,
            code="slow_response",
            category=AuditIssue.Category.PERFORMANCE,
            severity=AuditIssue.Severity.MEDIUM,
            message="Page response time appears slow.",
            recommendation="Review hosting, caching, and page weight to improve response speed.",
        )

        apply_audit_scores(audit_run, has_pagespeed=False)

        self.assertEqual(audit_run.performance_score, 93)
        self.assertGreater(audit_run.overall_score, 0)

    def test_summary_builds_ranked_recommendations_and_score_breakdown(self):
        audit_run = AuditRun.objects.create(
            normalized_domain="example.com",
            start_url="https://example.com/",
        )
        high_page = AuditPage.objects.create(
            audit_run=audit_run,
            url="https://example.com/about/",
            status_code=200,
            response_time_ms=1800,
        )
        low_page = AuditPage.objects.create(
            audit_run=audit_run,
            url="https://example.com/blog/",
            status_code=200,
            response_time_ms=500,
        )

        AuditIssue.objects.create(
            audit_run=audit_run,
            page=high_page,
            code="missing_title",
            category=AuditIssue.Category.ON_PAGE,
            severity=AuditIssue.Severity.HIGH,
            message="Page title is missing.",
            recommendation="Add a unique page title aligned with the page intent.",
        )
        AuditIssue.objects.create(
            audit_run=audit_run,
            page=low_page,
            code="thin_content",
            category=AuditIssue.Category.CONTENT,
            severity=AuditIssue.Severity.LOW,
            message="Page copy is thin for a commercial page.",
            recommendation="Expand the page with clearer explanations and proof.",
        )

        apply_audit_scores(audit_run, has_pagespeed=False)
        summary = build_audit_summary(audit_run)

        self.assertIn("score_breakdown", summary)
        self.assertIn("recommendations", summary)
        self.assertIn("product_modules", summary)
        self.assertEqual(summary["recommendations"][0]["title"], "Page title is missing.")
        self.assertGreaterEqual(
            summary["recommendations"][0]["priority_score"],
            summary["recommendations"][1]["priority_score"],
        )
        self.assertEqual(summary["product_modules"], [])

    def test_summary_builds_performance_metrics_and_flags_critical_ttfb(self):
        audit_run = AuditRun.objects.create(
            normalized_domain="example.com",
            start_url="https://example.com/",
            summary={
                "pagespeed": {
                    "source": "Google PageSpeed Insights",
                    "strategy": "mobile",
                    "metrics": {
                        "largest_contentful_paint": "4.2 s",
                        "server_response_time": "1.9 s",
                        "total_blocking_time": "120 ms",
                    },
                }
            },
        )

        summary = build_audit_summary(audit_run, issues=[])

        metric_labels = [item["label"] for item in summary["performance_metrics"]]
        self.assertIn("Largest Contentful Paint (LCP)", metric_labels)
        self.assertIn("Time to First Byte (TTFB)", metric_labels)
        failure_metrics = [item["metric"] for item in summary["vitals_failures"]]
        self.assertIn("Time to First Byte (TTFB)", failure_metrics)

    def test_featured_recommendations_prioritize_category_diversity(self):
        audit_run = AuditRun.objects.create(
            normalized_domain="example.com",
            start_url="https://example.com/",
        )
        page = AuditPage.objects.create(
            audit_run=audit_run,
            url="https://example.com/about/",
            status_code=200,
            response_time_ms=1200,
        )
        second_page = AuditPage.objects.create(
            audit_run=audit_run,
            url="https://example.com/contact/",
            status_code=200,
            response_time_ms=1100,
        )
        AuditIssue.objects.create(
            audit_run=audit_run,
            page=page,
            code="missing_h1_home",
            category=AuditIssue.Category.ON_PAGE,
            severity=AuditIssue.Severity.HIGH,
            message="No H1 tag detected.",
            recommendation="Add a single H1.",
        )
        AuditIssue.objects.create(
            audit_run=audit_run,
            page=second_page,
            code="missing_h1_contact",
            category=AuditIssue.Category.ON_PAGE,
            severity=AuditIssue.Severity.HIGH,
            message="No H1 tag detected.",
            recommendation="Add a single H1.",
        )
        AuditIssue.objects.create(
            audit_run=audit_run,
            code="missing_sitemap",
            category=AuditIssue.Category.TECHNICAL,
            severity=AuditIssue.Severity.MEDIUM,
            message="sitemap.xml is missing or inaccessible.",
            recommendation="Publish an XML sitemap.",
        )

        apply_audit_scores(audit_run, has_pagespeed=False)
        summary = build_audit_summary(audit_run)

        self.assertGreaterEqual(len(summary["featured_recommendations"]), 2)
        self.assertEqual(summary["featured_recommendations"][0]["category_key"], "on_page")
        self.assertEqual(summary["featured_recommendations"][1]["category_key"], "technical")
        self.assertEqual(summary["featured_recommendations"][0]["affected_pages_count"], 2)
        self.assertEqual(summary["featured_recommendations"][0]["category_issue_count"], 2)

    def test_summary_flags_custom_work_for_severe_structural_issues(self):
        audit_run = AuditRun.objects.create(
            normalized_domain="example.com",
            start_url="https://example.com/",
            technical_score=40,
            on_page_score=52,
            content_score=58,
            aeo_score=54,
            internal_linking_score=65,
            performance_score=42,
            pages_crawled=4,
        )

        summary = build_audit_summary(audit_run, issues=[])

        self.assertTrue(summary["custom_work_items"])
        self.assertEqual(summary["custom_work_items"][0]["title"], "Website or app rebuild")

    def test_admin_service_recommendations_use_summary_service_fit_when_available(self):
        audit_run = AuditRun.objects.create(
            normalized_domain="example.com",
            start_url="https://example.com/",
            technical_score=70,
            on_page_score=74,
            content_score=82,
            aeo_score=68,
            performance_score=91,
            summary={
                "service_fit": [
                    {
                        "title": "SEO Foundation",
                        "reason": "Technical and on-page signals are under target.",
                        "impact": "Improve crawl trust and page discoverability.",
                    },
                    {
                        "title": "AEO / AI Search Optimization",
                        "reason": "AEO readiness is weak.",
                        "impact": "Improve answer-engine citation readiness.",
                    },
                ]
            },
        )

        recommendations = get_service_recommendations(audit_run)

        self.assertEqual(len(recommendations), 2)
        self.assertEqual(recommendations[0]["category"], "SEO Foundation")
        self.assertEqual(recommendations[0]["score"], 70)
        self.assertEqual(recommendations[1]["score"], 68)


class ProjectDashboardTests(TestCase):
    def test_staff_project_dashboard_shows_latest_recommendations(self):
        user = get_user_model().objects.create_user(
            username="staff",
            email="staff@example.com",
            password="testpass123",
            is_staff=True,
        )
        audit_request = AuditRequest.objects.create(
            company_name="Northwind",
            email="ops@example.com",
            website="https://example.com",
        )
        audit_run = AuditRun.objects.create(
            audit_request=audit_request,
            normalized_domain="example.com",
            start_url="https://example.com/",
            overall_score=74,
            technical_score=71,
            aeo_score=66,
            performance_score=81,
            summary={
                "score_breakdown": {
                    "technical": {
                        "label": "Technical",
                        "score": 71,
                        "status": "weak",
                        "issues": 3,
                        "next_step": "Resolve crawl blockers first.",
                    }
                },
                "recommendations": [
                    {
                        "title": "Fix missing title tags",
                        "category": "On-page",
                        "priority_score": 84,
                        "description": "Several priority pages are missing title tags.",
                        "recommended_fix": "Add unique titles to all commercial pages.",
                    }
                ],
                "product_modules": [
                    {
                        "title": "Site Health Monitor",
                        "reason": "Technical and on-page signals are under target.",
                        "plan": "Growth",
                    }
                ],
            },
        )
        project = ClientProject.objects.create(
            audit_request=audit_request,
            latest_audit_run=audit_run,
            name="Northwind",
            website="https://example.com",
            normalized_domain="example.com",
            contact_email="ops@example.com",
            latest_score=74,
        )

        self.client.force_login(user)
        response = self.client.get(reverse("tools:project-dashboard", args=[project.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fix missing title tags")
        self.assertContains(response, "Resolve crawl blockers first.")
        self.assertContains(response, "Site Health Monitor")

    def test_workspace_signup_links_audit_to_logged_in_user_dashboard(self):
        audit_request = AuditRequest.objects.create(
            company_name="Northwind",
            email="ops@example.com",
            website="https://example.com",
        )
        audit_run = AuditRun.objects.create(
            audit_request=audit_request,
            normalized_domain="example.com",
            start_url="https://example.com/",
            overall_score=74,
            summary={
                "recommendations": [
                    {
                        "title": "Fix missing title tags",
                        "recommended_fix": "Add unique titles.",
                    }
                ],
                "product_modules": [
                    {
                        "title": "Site Health Monitor",
                        "reason": "Technical signals are under target.",
                        "plan": "Growth",
                    }
                ],
            },
        )

        response = self.client.post(
            reverse("tools:workspace-signup"),
            {
                "audit": audit_run.pk,
                "email": "user@example.com",
                "password": "strongpass123",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("tools:workspace-dashboard"))

        user = get_user_model().objects.get(username="user@example.com")
        project = ClientProject.objects.get(audit_request=audit_request)
        self.assertEqual(project.owner, user)

        dashboard_response = self.client.get(reverse("tools:workspace-dashboard"))
        self.assertEqual(dashboard_response.status_code, 200)
        self.assertContains(dashboard_response, "Site Health Monitor")
        self.assertContains(dashboard_response, "Free-pass mode")

    def test_workspace_dashboard_shows_audit_history_and_delta(self):
        user = get_user_model().objects.create_user(
            username="user2@example.com",
            email="user2@example.com",
            password="strongpass123",
        )
        audit_request = AuditRequest.objects.create(
            company_name="Northwind",
            email="user2@example.com",
            website="https://example.com",
        )
        older_run = AuditRun.objects.create(
            audit_request=audit_request,
            normalized_domain="example.com",
            start_url="https://example.com/",
            overall_score=61,
            status=AuditRun.Status.COMPLETED,
            pages_crawled=5,
            summary={},
        )
        latest_run = AuditRun.objects.create(
            audit_request=audit_request,
            normalized_domain="example.com",
            start_url="https://example.com/",
            overall_score=74,
            status=AuditRun.Status.COMPLETED,
            pages_crawled=6,
            summary={},
        )
        ClientProject.objects.create(
            owner=user,
            audit_request=audit_request,
            latest_audit_run=latest_run,
            name="Northwind",
            website="https://example.com",
            normalized_domain="example.com",
            contact_email="user2@example.com",
            latest_score=74,
        )

        self.client.force_login(user)
        response = self.client.get(reverse("tools:workspace-dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Saved reruns and score comparison")
        self.assertContains(response, "+13")

    def test_workspace_dashboard_shows_fix_locations_and_module_upgrade_cta(self):
        user = get_user_model().objects.create_user(
            username="user3@example.com",
            email="user3@example.com",
            password="strongpass123",
        )
        audit_request = AuditRequest.objects.create(
            company_name="Northwind",
            email="user3@example.com",
            website="https://example.com",
        )
        latest_run = AuditRun.objects.create(
            audit_request=audit_request,
            normalized_domain="example.com",
            start_url="https://example.com/",
            overall_score=74,
            status=AuditRun.Status.COMPLETED,
            pages_crawled=6,
            summary={
                "featured_recommendations": [
                    {
                        "title": "No H1 tag detected.",
                        "category": "On-page",
                        "description": "Detected on 3 pages. This is lowering the On-page score.",
                        "recommended_fix": "Add a single H1 that clearly describes the page topic.",
                        "affected_pages_count": 3,
                        "page_examples": [
                            "https://example.com/about/",
                            "https://example.com/contact/",
                        ],
                        "category_issue_count": 3,
                    }
                ],
                "recommendations": [],
                "product_modules": [
                    {
                        "title": "Site Health Monitor",
                        "reason": "Technical and on-page signals are under target.",
                        "impact": "Continuously track crawl, metadata, indexation, and priority-page issues inside the workspace.",
                        "plan": "Growth",
                        "cta_label": "Unlock monitoring",
                    }
                ],
            },
        )
        ClientProject.objects.create(
            owner=user,
            audit_request=audit_request,
            latest_audit_run=latest_run,
            name="Northwind",
            website="https://example.com",
            normalized_domain="example.com",
            contact_email="user3@example.com",
            latest_score=74,
        )

        self.client.force_login(user)
        response = self.client.get(reverse("tools:workspace-dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Where this appears")
        self.assertContains(response, "https://example.com/about/")
        self.assertContains(response, "Unlock monitoring")
        self.assertContains(response, reverse("tools:workspace-billing-checkout"))

    def test_workspace_dashboard_shows_audits_seo_aeo_and_usage_value_panel(self):
        user = get_user_model().objects.create_user(
            username="value@example.com",
            email="value@example.com",
            password="strongpass123",
        )
        audit_request = AuditRequest.objects.create(
            company_name="Northwind",
            email="value@example.com",
            website="https://example.com",
        )
        latest_run = AuditRun.objects.create(
            audit_request=audit_request,
            normalized_domain="example.com",
            start_url="https://example.com/",
            overall_score=79,
            status=AuditRun.Status.COMPLETED,
            summary={},
        )
        project = ClientProject.objects.create(
            owner=user,
            audit_request=audit_request,
            latest_audit_run=latest_run,
            name="Northwind",
            website="https://example.com",
            normalized_domain="example.com",
            contact_email="value@example.com",
            latest_score=79,
        )
        profile = SEOProjectProfile.objects.create(
            project=project,
            business_type="automotive",
            location="Nairobi",
            target_goal="Increase qualified organic leads",
        )
        SEOContextSnapshot.objects.create(project=project, profile=profile, source_audit_run=latest_run, output_json={})
        AEOAudit.objects.create(project=project, seo_profile=profile, source_audit_run=latest_run, visibility_score=67)
        UsageRecord.objects.create(
            user=user,
            metric=UsageRecord.Metric.SEO_SNAPSHOT,
            period_start=latest_run.created_at.date().replace(day=1),
            period_end=latest_run.created_at.date().replace(
                day=calendar.monthrange(latest_run.created_at.year, latest_run.created_at.month)[1]
            ),
            quantity=2,
        )
        UsageRecord.objects.create(
            user=user,
            metric=UsageRecord.Metric.AEO_AUDIT,
            period_start=latest_run.created_at.date().replace(day=1),
            period_end=latest_run.created_at.date().replace(
                day=calendar.monthrange(latest_run.created_at.year, latest_run.created_at.month)[1]
            ),
            quantity=1,
        )
        self.client.force_login(user)

        response = self.client.get(reverse("tools:workspace-dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Audits, SEO, and AEO")
        self.assertContains(response, "Where your credits are going")
        self.assertContains(response, "SEO context refreshes")
        self.assertContains(response, "AEO analyses")

    def test_public_audit_result_shows_workspace_and_plan_ctas(self):
        audit_run = AuditRun.objects.create(
            normalized_domain="example.com",
            start_url="https://example.com/",
            overall_score=61,
            status=AuditRun.Status.COMPLETED,
            summary={
                "scores": {"technical": 60, "aeo": 64, "on_page": 58, "content": 70, "internal_linking": 66, "performance": 72, "accessibility": 0, "best_practices": 0, "seo": 0},
                "gauge_offsets": {"overall": 0},
                "score_breakdown": {
                    "on_page": {
                        "label": "On-page",
                        "score": 58,
                        "status": "weak",
                        "issues": 4,
                        "gap": 27,
                        "explanation": "Metadata and page-level relevance gaps.",
                        "next_step": "Fix headings and metadata on priority pages.",
                    }
                },
                "featured_recommendations": [
                    {
                        "title": "No H1 tag detected.",
                        "description": "Detected on 4 pages. This is lowering the On-page score.",
                        "priority_score": 92,
                        "recommended_fix": "Add a single H1.",
                        "estimated_impact": "Improves ranking alignment.",
                        "category": "On-page",
                        "category_key": "on_page",
                        "category_issue_count": 4,
                        "affected_pages_count": 4,
                        "page_examples": ["https://example.com/a", "https://example.com/b"],
                        "suggested_plan": "Growth",
                        "severity": "high",
                    }
                ],
                "recommendations": [],
                "product_modules": [],
                "custom_work_items": [],
            },
        )

        response = self.client.get(reverse("tools:audit-result", args=[audit_run.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Free-pass mode for testing")
        self.assertContains(response, "4 on-page issues")
        self.assertContains(response, "View Growth plan")
        self.assertContains(response, reverse("tools:workspace-signup"))


class WorkspaceAuthTests(TestCase):
    def test_workspace_login_links_existing_user_to_audit_project(self):
        user = get_user_model().objects.create_user(
            username="user@example.com",
            email="user@example.com",
            password="strongpass123",
        )
        audit_request = AuditRequest.objects.create(
            company_name="Northwind",
            email="user@example.com",
            website="https://example.com",
        )
        audit_run = AuditRun.objects.create(
            audit_request=audit_request,
            normalized_domain="example.com",
            start_url="https://example.com/",
            overall_score=70,
        )

        response = self.client.post(
            reverse("tools:workspace-login"),
            {
                "audit": audit_run.pk,
                "username": "user@example.com",
                "password": "strongpass123",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("tools:workspace-dashboard"))
        project = ClientProject.objects.get(audit_request=audit_request)
        self.assertEqual(project.owner, user)

    @override_settings(
        GOOGLE_OAUTH_CLIENT_ID="google-client-id",
        GOOGLE_OAUTH_CLIENT_SECRET="google-client-secret",
        GOOGLE_OAUTH_ENABLED=True,
    )
    def test_google_oauth_start_redirects_to_google(self):
        response = self.client.get(reverse("tools:google-oauth-start"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("accounts.google.com", response["Location"])
        self.assertIn("client_id=google-client-id", response["Location"])

    @override_settings(
        GOOGLE_OAUTH_CLIENT_ID="google-client-id",
        GOOGLE_OAUTH_CLIENT_SECRET="google-client-secret",
        GOOGLE_OAUTH_ENABLED=True,
    )
    @patch("apps.tools.views.exchange_google_code_for_userinfo")
    def test_google_oauth_callback_creates_user_and_links_audit(self, mocked_exchange):
        mocked_exchange.return_value = {
            "email": "googleuser@example.com",
            "given_name": "Google",
            "family_name": "User",
        }
        audit_request = AuditRequest.objects.create(
            company_name="Northwind",
            email="googleuser@example.com",
            website="https://example.com",
        )
        audit_run = AuditRun.objects.create(
            audit_request=audit_request,
            normalized_domain="example.com",
            start_url="https://example.com/",
            overall_score=81,
        )

        session = self.client.session
        session["google_oauth_state"] = "test-state"
        session["google_oauth_audit"] = str(audit_run.pk)
        session.save()

        response = self.client.get(
            reverse("tools:google-oauth-callback"),
            {"state": "test-state", "code": "oauth-code"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("tools:workspace-dashboard"))
        user = get_user_model().objects.get(email="googleuser@example.com")
        project = ClientProject.objects.get(audit_request=audit_request)
        self.assertEqual(project.owner, user)


class WorkspaceBillingTests(TestCase):
    @override_settings(
        STRIPE_PUBLISHABLE_KEY="pk_test_value",
        STRIPE_SECRET_KEY="sk_test_value",
        STRIPE_ENABLED=True,
        STRIPE_PRICE_IDS={"starter": "200", "growth": "", "authority": "", "enterprise": ""},
    )
    def test_checkout_rejects_literal_amount_instead_of_price_id(self):
        user = get_user_model().objects.create_user(
            username="pricecheck@example.com",
            email="pricecheck@example.com",
            password="strongpass123",
        )
        plan = WorkspacePlan.objects.get(slug="starter")

        with self.assertRaisesMessage(
            BillingError,
            "must be a Stripe Price ID starting with 'price_'",
        ):
            create_checkout_session(
                user=user,
                plan=plan,
                success_url="https://example.com/success",
                cancel_url="https://example.com/cancel",
            )

    @override_settings(
        STRIPE_PUBLISHABLE_KEY="pk_test_value",
        STRIPE_SECRET_KEY="sk_test_value",
        STRIPE_ENABLED=True,
        STRIPE_PRICE_IDS={"starter": "price_starter", "growth": "", "authority": "", "enterprise": ""},
    )
    @patch("apps.leads.billing.requests.post")
    def test_workspace_checkout_redirects_to_stripe(self, mocked_post):
        mocked_post.return_value.status_code = 200
        mocked_post.return_value.json.return_value = {
            "id": "cs_test_123",
            "url": "https://checkout.stripe.test/session/123",
        }
        user = get_user_model().objects.create_user(
            username="billing@example.com",
            email="billing@example.com",
            password="strongpass123",
        )
        self.client.force_login(user)

        response = self.client.post(
            reverse("tools:workspace-billing-checkout"),
            {"plan": "starter"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "https://checkout.stripe.test/session/123")
        subscription = WorkspaceSubscription.objects.get(user=user)
        self.assertEqual(subscription.plan.slug, "starter")
        self.assertEqual(subscription.stripe_checkout_session_id, "cs_test_123")

    @override_settings(
        STRIPE_WEBHOOK_SECRET="whsec_test_value",
    )
    def test_stripe_webhook_activates_subscription(self):
        user = get_user_model().objects.create_user(
            username="webhook@example.com",
            email="webhook@example.com",
            password="strongpass123",
        )
        starter_plan = WorkspacePlan.objects.get(slug="starter")
        WorkspaceSubscription.objects.create(user=user, plan=starter_plan)

        payload = {
            "id": "evt_123",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_live_123",
                    "client_reference_id": str(user.pk),
                    "customer": "cus_123",
                    "subscription": "sub_123",
                    "metadata": {"plan_slug": "starter"},
                }
            },
        }
        encoded_payload = json.dumps(payload).encode("utf-8")
        timestamp = str(int(time.time()))
        signed_payload = f"{timestamp}.{encoded_payload.decode('utf-8')}".encode("utf-8")
        signature = hmac.new(
            b"whsec_test_value",
            msg=signed_payload,
            digestmod=hashlib.sha256,
        ).hexdigest()

        response = self.client.post(
            reverse("tools:stripe-webhook"),
            data=encoded_payload,
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE=f"t={timestamp},v1={signature}",
        )

        self.assertEqual(response.status_code, 200)
        subscription = WorkspaceSubscription.objects.get(user=user)
        self.assertEqual(subscription.status, WorkspaceSubscription.Status.ACTIVE)
        self.assertEqual(subscription.stripe_customer_id, "cus_123")
        self.assertEqual(subscription.stripe_subscription_id, "sub_123")

    @override_settings(AUDIT_TIER_ENFORCEMENT=True)
    def test_workspace_dashboard_limits_history_for_free_users(self):
        user = get_user_model().objects.create_user(
            username="freeuser@example.com",
            email="freeuser@example.com",
            password="strongpass123",
        )
        audit_request = AuditRequest.objects.create(
            company_name="Northwind",
            email="freeuser@example.com",
            website="https://example.com",
        )
        older_run = AuditRun.objects.create(
            audit_request=audit_request,
            normalized_domain="example.com",
            start_url="https://example.com/",
            overall_score=61,
            status=AuditRun.Status.COMPLETED,
            pages_crawled=5,
            summary={},
        )
        latest_run = AuditRun.objects.create(
            audit_request=audit_request,
            normalized_domain="example.com",
            start_url="https://example.com/",
            overall_score=74,
            status=AuditRun.Status.COMPLETED,
            pages_crawled=6,
            summary={},
        )
        ClientProject.objects.create(
            owner=user,
            audit_request=audit_request,
            latest_audit_run=latest_run,
            name="Northwind",
            website="https://example.com",
            normalized_domain="example.com",
            contact_email="freeuser@example.com",
            latest_score=74,
        )

        self.client.force_login(user)
        response = self.client.get(reverse("tools:workspace-dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "1 older audit run")
        self.assertContains(response, "74")
        self.assertNotContains(response, str(older_run.created_at))
        self.assertContains(response, "View Latest PDF")

    @override_settings(AUDIT_TIER_ENFORCEMENT=True)
    def test_workspace_rerun_blocks_when_monthly_audit_limit_is_reached(self):
        user = get_user_model().objects.create_user(
            username="limited@example.com",
            email="limited@example.com",
            password="strongpass123",
        )
        audit_request = AuditRequest.objects.create(
            company_name="Northwind",
            email="limited@example.com",
            website="https://example.com",
        )
        latest_run = AuditRun.objects.create(
            audit_request=audit_request,
            normalized_domain="example.com",
            start_url="https://example.com/",
            overall_score=74,
            status=AuditRun.Status.COMPLETED,
            pages_crawled=6,
            summary={},
        )
        ClientProject.objects.create(
            owner=user,
            audit_request=audit_request,
            latest_audit_run=latest_run,
            name="Northwind",
            website="https://example.com",
            normalized_domain="example.com",
            contact_email="limited@example.com",
            latest_score=74,
        )
        usage_record = UsageRecord.objects.create(
            user=user,
            metric=UsageRecord.Metric.AUDIT_RUN,
            period_start=latest_run.created_at.date().replace(day=1),
            period_end=latest_run.created_at.date().replace(
                day=calendar.monthrange(latest_run.created_at.year, latest_run.created_at.month)[1]
            ),
            quantity=1,
        )
        self.client.force_login(user)

        response = self.client.post(reverse("tools:workspace-audit-rerun"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("tools:workspace-dashboard"))

    @patch("apps.tools.billing_views.enqueue_public_site_audit")
    def test_workspace_rerun_uses_selected_project(self, mocked_enqueue):
        user = get_user_model().objects.create_user(
            username="multisite@example.com",
            email="multisite@example.com",
            password="strongpass123",
        )
        first_request = AuditRequest.objects.create(
            company_name="Northwind One",
            email="multisite@example.com",
            website="https://one.example.com",
        )
        second_request = AuditRequest.objects.create(
            company_name="Northwind Two",
            email="multisite@example.com",
            website="https://two.example.com",
        )
        first_run = AuditRun.objects.create(
            audit_request=first_request,
            normalized_domain="one.example.com",
            start_url="https://one.example.com/",
            status=AuditRun.Status.COMPLETED,
        )
        second_run = AuditRun.objects.create(
            audit_request=second_request,
            normalized_domain="two.example.com",
            start_url="https://two.example.com/",
            status=AuditRun.Status.COMPLETED,
        )
        ClientProject.objects.create(
            owner=user,
            audit_request=first_request,
            latest_audit_run=first_run,
            name="Project One",
            website="https://one.example.com",
            normalized_domain="one.example.com",
            contact_email="multisite@example.com",
        )
        second_project = ClientProject.objects.create(
            owner=user,
            audit_request=second_request,
            latest_audit_run=second_run,
            name="Project Two",
            website="https://two.example.com",
            normalized_domain="two.example.com",
            contact_email="multisite@example.com",
        )

        self.client.force_login(user)
        session = self.client.session
        session["active_workspace_project_id"] = second_project.pk
        session.save()

        response = self.client.post(reverse("tools:workspace-audit-rerun"))

        self.assertEqual(response.status_code, 302)
        rerun = AuditRun.objects.order_by("-created_at").first()
        self.assertEqual(rerun.audit_request, second_request)
        mocked_enqueue.assert_called_once_with(rerun.pk)


class WorkspaceProjectSelectionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="selector@example.com",
            email="selector@example.com",
            password="strongpass123",
        )
        first_request = AuditRequest.objects.create(
            company_name="Northwind One",
            email="selector@example.com",
            website="https://one.example.com",
        )
        second_request = AuditRequest.objects.create(
            company_name="Northwind Two",
            email="selector@example.com",
            website="https://two.example.com",
        )
        first_run = AuditRun.objects.create(
            audit_request=first_request,
            normalized_domain="one.example.com",
            start_url="https://one.example.com/",
            overall_score=61,
            status=AuditRun.Status.COMPLETED,
            summary={},
        )
        second_run = AuditRun.objects.create(
            audit_request=second_request,
            normalized_domain="two.example.com",
            start_url="https://two.example.com/",
            overall_score=88,
            status=AuditRun.Status.COMPLETED,
            summary={},
        )
        self.first_project = ClientProject.objects.create(
            owner=self.user,
            audit_request=first_request,
            latest_audit_run=first_run,
            name="Project One",
            website="https://one.example.com",
            normalized_domain="one.example.com",
            contact_email="selector@example.com",
            latest_score=61,
        )
        self.second_project = ClientProject.objects.create(
            owner=self.user,
            audit_request=second_request,
            latest_audit_run=second_run,
            name="Project Two",
            website="https://two.example.com",
            normalized_domain="two.example.com",
            contact_email="selector@example.com",
            latest_score=88,
        )

    def test_workspace_project_select_switches_active_project(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("tools:workspace-project-select"),
            {"project_id": self.second_project.pk, "next": reverse("tools:workspace-dashboard")},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("tools:workspace-dashboard"))
        self.assertEqual(self.client.session["active_workspace_project_id"], self.second_project.pk)

    def test_workspace_dashboard_uses_selected_project(self):
        self.client.force_login(self.user)
        session = self.client.session
        session["active_workspace_project_id"] = self.second_project.pk
        session.save()

        response = self.client.get(reverse("tools:workspace-dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Project Two")
        self.assertEqual(response.context["project"].pk, self.second_project.pk)


class WorkspaceAutomationTests(TestCase):
    @override_settings(AUDIT_TIER_ENFORCEMENT=True)
    def test_workspace_can_enable_recurring_schedule_on_supported_plan(self):
        user = get_user_model().objects.create_user(
            username="automation@example.com",
            email="automation@example.com",
            password="strongpass123",
        )
        audit_request = AuditRequest.objects.create(
            company_name="Northwind",
            email="automation@example.com",
            website="https://example.com",
        )
        latest_run = AuditRun.objects.create(
            audit_request=audit_request,
            normalized_domain="example.com",
            start_url="https://example.com/",
            overall_score=70,
            status=AuditRun.Status.COMPLETED,
        )
        ClientProject.objects.create(
            owner=user,
            audit_request=audit_request,
            latest_audit_run=latest_run,
            name="Northwind",
            website="https://example.com",
            normalized_domain="example.com",
            contact_email="automation@example.com",
            latest_score=70,
        )
        growth_plan = WorkspacePlan.objects.get(slug="growth")
        WorkspaceSubscription.objects.create(
            user=user,
            plan=growth_plan,
            status=WorkspaceSubscription.Status.ACTIVE,
        )

        self.client.force_login(user)
        response = self.client.post(
            reverse("tools:workspace-audit-schedule"),
            {"cadence": "weekly", "is_active": "1"},
        )

        self.assertEqual(response.status_code, 302)
        schedule = WorkspaceAuditSchedule.objects.get()
        self.assertTrue(schedule.is_active)
        self.assertEqual(schedule.cadence, WorkspaceAuditSchedule.Cadence.WEEKLY)
        self.assertIsNotNone(schedule.next_run_at)

    @override_settings(AUDIT_TIER_ENFORCEMENT=True)
    def test_due_schedule_processing_queues_workspace_rerun(self):
        user = get_user_model().objects.create_user(
            username="scheduled@example.com",
            email="scheduled@example.com",
            password="strongpass123",
        )
        audit_request = AuditRequest.objects.create(
            company_name="Northwind",
            email="scheduled@example.com",
            website="https://example.com",
        )
        previous_run = AuditRun.objects.create(
            audit_request=audit_request,
            normalized_domain="example.com",
            start_url="https://example.com/",
            overall_score=72,
            status=AuditRun.Status.COMPLETED,
        )
        project = ClientProject.objects.create(
            owner=user,
            audit_request=audit_request,
            latest_audit_run=previous_run,
            name="Northwind",
            website="https://example.com",
            normalized_domain="example.com",
            contact_email="scheduled@example.com",
            latest_score=72,
        )
        growth_plan = WorkspacePlan.objects.get(slug="growth")
        WorkspaceSubscription.objects.create(
            user=user,
            plan=growth_plan,
            status=WorkspaceSubscription.Status.ACTIVE,
        )
        schedule = WorkspaceAuditSchedule.objects.create(
            project=project,
            cadence=WorkspaceAuditSchedule.Cadence.WEEKLY,
            is_active=True,
            next_run_at=timezone.now() - timedelta(minutes=5),
        )

        queued_ids = []
        summary = process_due_workspace_schedules(
            now=timezone.now(),
            enqueue_fn=queued_ids.append,
        )

        schedule.refresh_from_db()
        self.assertEqual(summary["queued"], 1)
        self.assertEqual(summary["failed"], 0)
        self.assertEqual(len(queued_ids), 1)
        self.assertEqual(schedule.last_audit_run_id, queued_ids[0])
        self.assertIsNotNone(schedule.last_run_at)
        self.assertGreater(AuditRun.objects.count(), 1)
        self.assertEqual(UsageRecord.objects.get(user=user, metric=UsageRecord.Metric.AUDIT_RUN).quantity, 1)

    @override_settings(AUDIT_TIER_ENFORCEMENT=True)
    def test_free_plan_cannot_enable_recurring_schedule(self):
        user = get_user_model().objects.create_user(
            username="freeautomation@example.com",
            email="freeautomation@example.com",
            password="strongpass123",
        )
        audit_request = AuditRequest.objects.create(
            company_name="Northwind",
            email="freeautomation@example.com",
            website="https://example.com",
        )
        latest_run = AuditRun.objects.create(
            audit_request=audit_request,
            normalized_domain="example.com",
            start_url="https://example.com/",
            overall_score=70,
            status=AuditRun.Status.COMPLETED,
        )
        ClientProject.objects.create(
            owner=user,
            audit_request=audit_request,
            latest_audit_run=latest_run,
            name="Northwind",
            website="https://example.com",
            normalized_domain="example.com",
            contact_email="freeautomation@example.com",
            latest_score=70,
        )

        self.client.force_login(user)
        response = self.client.post(
            reverse("tools:workspace-audit-schedule"),
            {"cadence": "weekly", "is_active": "1"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(WorkspaceAuditSchedule.objects.exists())

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_deliver_workspace_audit_notifications_sends_email_with_pdf(self):
        user = get_user_model().objects.create_user(
            username="reports@example.com",
            email="reports@example.com",
            password="strongpass123",
        )
        audit_request = AuditRequest.objects.create(
            company_name="Northwind",
            email="reports@example.com",
            website="https://example.com",
        )
        audit_run = AuditRun.objects.create(
            audit_request=audit_request,
            normalized_domain="example.com",
            start_url="https://example.com/",
            overall_score=74,
            status=AuditRun.Status.COMPLETED,
            completed_at=timezone.now(),
            summary={"score_breakdown": {}, "recommendations": [], "issue_summary": {}},
        )
        project = ClientProject.objects.create(
            owner=user,
            audit_request=audit_request,
            latest_audit_run=audit_run,
            name="Northwind",
            website="https://example.com",
            normalized_domain="example.com",
            contact_email="reports@example.com",
            latest_score=74,
        )
        schedule = WorkspaceAuditSchedule.objects.create(
            project=project,
            cadence=WorkspaceAuditSchedule.Cadence.WEEKLY,
            is_active=True,
            email_reports_enabled=True,
            alert_on_score_drop=True,
            report_recipients=["stakeholder@example.com"],
        )
        change_report = create_audit_change_report(audit_run, project=project)

        result = deliver_workspace_audit_notifications(
            audit_run=audit_run,
            project=project,
            change_report=change_report,
        )

        schedule.refresh_from_db()
        self.assertEqual(result["reports_sent"], 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["stakeholder@example.com"])
        self.assertEqual(mail.outbox[0].attachments[0][2], "application/pdf")

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        AUDIT_TIER_ENFORCEMENT=True,
    )
    def test_email_reports_do_not_create_share_links_without_sharing_capability(self):
        user = get_user_model().objects.create_user(
            username="emailonly@example.com",
            email="emailonly@example.com",
            password="strongpass123",
        )
        audit_request = AuditRequest.objects.create(
            company_name="Northwind",
            email="emailonly@example.com",
            website="https://example.com",
        )
        audit_run = AuditRun.objects.create(
            audit_request=audit_request,
            normalized_domain="example.com",
            start_url="https://example.com/",
            overall_score=81,
            status=AuditRun.Status.COMPLETED,
            completed_at=timezone.now(),
            summary={"score_breakdown": {}, "recommendations": [], "issue_summary": {}},
        )
        project = ClientProject.objects.create(
            owner=user,
            audit_request=audit_request,
            latest_audit_run=audit_run,
            name="Northwind",
            website="https://example.com",
            normalized_domain="example.com",
            contact_email="emailonly@example.com",
            latest_score=81,
        )
        authority_plan = WorkspacePlan.objects.get(slug="authority")
        authority_plan.email_reports_enabled = True
        authority_plan.stakeholder_sharing_enabled = False
        authority_plan.save(update_fields=["email_reports_enabled", "stakeholder_sharing_enabled", "updated_at"])
        WorkspaceSubscription.objects.create(
            user=user,
            plan=authority_plan,
            status=WorkspaceSubscription.Status.ACTIVE,
        )
        WorkspaceAuditSchedule.objects.create(
            project=project,
            cadence=WorkspaceAuditSchedule.Cadence.WEEKLY,
            is_active=True,
            email_reports_enabled=True,
            report_recipients=["stakeholder@example.com"],
        )

        result = deliver_workspace_audit_notifications(audit_run=audit_run, project=project)

        self.assertEqual(result["reports_sent"], 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertFalse(AuditShareLink.objects.filter(audit_run=audit_run).exists())
        self.assertNotIn("Shareable report link", mail.outbox[0].body)


class AuditReportingTests(TestCase):
    def test_change_report_tracks_new_and_resolved_issues(self):
        audit_request = AuditRequest.objects.create(
            company_name="Northwind",
            email="reporting@example.com",
            website="https://example.com",
        )
        previous_run = AuditRun.objects.create(
            audit_request=audit_request,
            normalized_domain="example.com",
            start_url="https://example.com/",
            overall_score=60,
            technical_score=58,
            on_page_score=62,
            status=AuditRun.Status.COMPLETED,
            pages_crawled=4,
        )
        latest_run = AuditRun.objects.create(
            audit_request=audit_request,
            normalized_domain="example.com",
            start_url="https://example.com/",
            overall_score=75,
            technical_score=76,
            on_page_score=70,
            status=AuditRun.Status.COMPLETED,
            pages_crawled=6,
        )
        project = ClientProject.objects.create(
            audit_request=audit_request,
            latest_audit_run=latest_run,
            name="Northwind",
            website="https://example.com",
            normalized_domain="example.com",
            contact_email="reporting@example.com",
            latest_score=75,
        )
        previous_page = AuditPage.objects.create(audit_run=previous_run, url="https://example.com/about/", status_code=200)
        latest_page = AuditPage.objects.create(audit_run=latest_run, url="https://example.com/about/", status_code=200)
        new_page = AuditPage.objects.create(audit_run=latest_run, url="https://example.com/contact/", status_code=200)

        AuditIssue.objects.create(
            audit_run=previous_run,
            page=previous_page,
            code="missing_title",
            category=AuditIssue.Category.ON_PAGE,
            severity=AuditIssue.Severity.HIGH,
            message="Page title is missing.",
            recommendation="Add a unique page title.",
        )
        AuditIssue.objects.create(
            audit_run=latest_run,
            page=latest_page,
            code="slow_response",
            category=AuditIssue.Category.PERFORMANCE,
            severity=AuditIssue.Severity.MEDIUM,
            message="Page response time appears slow.",
            recommendation="Improve response time.",
        )
        AuditIssue.objects.create(
            audit_run=latest_run,
            page=new_page,
            code="missing_h1",
            category=AuditIssue.Category.ON_PAGE,
            severity=AuditIssue.Severity.HIGH,
            message="No H1 tag detected.",
            recommendation="Add a single H1.",
        )

        report = create_audit_change_report(latest_run, project=project, previous_audit_run=previous_run)

        self.assertEqual(report.overall_score_delta, 15)
        self.assertEqual(report.pages_crawled_delta, 2)
        self.assertEqual(report.new_issue_count, 2)
        self.assertEqual(report.resolved_issue_count, 1)
        self.assertIn("improved by 15 points", report.summary["headline"])
        self.assertEqual(report.summary["new_issue_categories"]["on_page"], 1)
        self.assertEqual(report.summary["resolved_issue_categories"]["on_page"], 1)

    def test_schedule_command_uses_processing_service(self):
        with patch("apps.tools.management.commands.process_workspace_schedules.process_due_workspace_schedules") as mocked_process:
            mocked_process.return_value = {"processed": 1, "queued": 1, "skipped": 0, "failed": 0}
            call_command("process_workspace_schedules")

        mocked_process.assert_called_once()


class AuditExportAndQueueTests(TestCase):
    @override_settings(AUDIT_TIER_ENFORCEMENT=True)
    def test_workspace_export_and_share_routes_require_supported_plan(self):
        user = get_user_model().objects.create_user(
            username="exports@example.com",
            email="exports@example.com",
            password="strongpass123",
        )
        audit_request = AuditRequest.objects.create(
            company_name="Northwind",
            email="exports@example.com",
            website="https://example.com",
        )
        audit_run = AuditRun.objects.create(
            audit_request=audit_request,
            normalized_domain="example.com",
            start_url="https://example.com/",
            overall_score=80,
            status=AuditRun.Status.COMPLETED,
            summary={"score_breakdown": {}, "recommendations": [], "issue_summary": {}},
        )
        ClientProject.objects.create(
            owner=user,
            audit_request=audit_request,
            latest_audit_run=audit_run,
            name="Northwind",
            website="https://example.com",
            normalized_domain="example.com",
            contact_email="exports@example.com",
            latest_score=80,
        )
        growth_plan = WorkspacePlan.objects.get(slug="growth")
        growth_plan.export_reports_enabled = True
        growth_plan.stakeholder_sharing_enabled = True
        growth_plan.email_reports_enabled = True
        growth_plan.save()
        WorkspaceSubscription.objects.create(
            user=user,
            plan=growth_plan,
            status=WorkspaceSubscription.Status.ACTIVE,
        )

        self.client.force_login(user)
        json_response = self.client.get(reverse("tools:workspace-audit-export-json", args=[audit_run.pk]))
        csv_response = self.client.get(reverse("tools:workspace-audit-export-csv", args=[audit_run.pk]))
        share_response = self.client.post(reverse("tools:workspace-audit-share", args=[audit_run.pk]))

        self.assertEqual(json_response.status_code, 200)
        self.assertEqual(csv_response.status_code, 200)
        self.assertEqual(share_response.status_code, 302)
        self.assertTrue(AuditShareLink.objects.filter(audit_run=audit_run).exists())

    @override_settings(AUDIT_TIER_ENFORCEMENT=True)
    def test_workspace_export_and_share_routes_block_incomplete_audits(self):
        user = get_user_model().objects.create_user(
            username="pendingexports@example.com",
            email="pendingexports@example.com",
            password="strongpass123",
        )
        audit_request = AuditRequest.objects.create(
            company_name="Northwind",
            email="pendingexports@example.com",
            website="https://example.com",
        )
        audit_run = AuditRun.objects.create(
            audit_request=audit_request,
            normalized_domain="example.com",
            start_url="https://example.com/",
            overall_score=0,
            status=AuditRun.Status.RUNNING,
            summary={},
        )
        ClientProject.objects.create(
            owner=user,
            audit_request=audit_request,
            latest_audit_run=audit_run,
            name="Northwind",
            website="https://example.com",
            normalized_domain="example.com",
            contact_email="pendingexports@example.com",
            latest_score=0,
        )
        authority_plan = WorkspacePlan.objects.get(slug="authority")
        authority_plan.export_reports_enabled = True
        authority_plan.stakeholder_sharing_enabled = True
        authority_plan.save(update_fields=["export_reports_enabled", "stakeholder_sharing_enabled", "updated_at"])
        WorkspaceSubscription.objects.create(
            user=user,
            plan=authority_plan,
            status=WorkspaceSubscription.Status.ACTIVE,
        )

        self.client.force_login(user)
        json_response = self.client.get(reverse("tools:workspace-audit-export-json", args=[audit_run.pk]))
        csv_response = self.client.get(reverse("tools:workspace-audit-export-csv", args=[audit_run.pk]))
        share_response = self.client.post(reverse("tools:workspace-audit-share", args=[audit_run.pk]))

        self.assertEqual(json_response.status_code, 409)
        self.assertEqual(csv_response.status_code, 409)
        self.assertEqual(share_response.status_code, 409)
        self.assertFalse(AuditShareLink.objects.filter(audit_run=audit_run).exists())

    def test_shared_audit_routes_return_404_for_incomplete_audits(self):
        audit_run = AuditRun.objects.create(
            normalized_domain="example.com",
            start_url="https://example.com/",
            status=AuditRun.Status.RUNNING,
        )
        share_link = AuditShareLink.objects.create(
            audit_run=audit_run,
            token="test-share-token",
        )

        html_response = self.client.get(reverse("tools:shared-audit-report", args=[share_link.token]))
        pdf_response = self.client.get(reverse("tools:shared-audit-report-pdf", args=[share_link.token]))

        self.assertEqual(html_response.status_code, 404)
        self.assertEqual(pdf_response.status_code, 404)

    def test_shared_audit_report_shows_solution_and_location_details(self):
        audit_run = AuditRun.objects.create(
            normalized_domain="example.com",
            start_url="https://example.com/",
            overall_score=82,
            status=AuditRun.Status.COMPLETED,
            pages_crawled=5,
            completed_at=timezone.now(),
            summary={
                "issue_summary": {"total": 3, "by_category": {"on_page": 2, "technical": 1}},
                "featured_recommendations": [
                    {
                        "title": "No H1 tag detected.",
                        "category": "On-page",
                        "description": "Detected on 2 pages. This is lowering the On-page score.",
                        "recommended_fix": "Add a single H1 tag to each affected page.",
                        "estimated_impact": "Improves ranking alignment and page clarity.",
                        "affected_pages_count": 2,
                        "page_examples": [
                            "https://example.com/about/",
                            "https://example.com/contact/",
                        ],
                    }
                ],
                "score_breakdown": {
                    "on_page": {"label": "On-page", "score": 58, "issues": 2, "next_step": "Fix headings and metadata first."}
                },
                "product_modules": [
                    {
                        "title": "Site Health Monitor",
                        "plan": "Growth",
                        "reason": "Technical and on-page signals are under target.",
                        "impact": "Track priority issues and reruns in one workflow.",
                    }
                ],
            },
        )
        share_link = AuditShareLink.objects.create(
            audit_run=audit_run,
            token="completed-share-token",
        )

        response = self.client.get(reverse("tools:shared-audit-report", args=[share_link.token]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Where this appears")
        self.assertContains(response, "Add a single H1 tag to each affected page.")
        self.assertContains(response, "Improves ranking alignment and page clarity.")
        self.assertContains(response, "Site Health Monitor")

    @override_settings(AUDIT_USE_CELERY=True)
    @patch("apps.tools.tasks.run_public_site_audit_task.delay")
    def test_enqueue_public_site_audit_uses_celery_when_enabled(self, mocked_delay):
        enqueue_public_site_audit(42)
        mocked_delay.assert_called_once_with(42)
