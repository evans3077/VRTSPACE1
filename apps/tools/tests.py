import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.leads.models import ClientProject
from apps.leads.models import AuditRequest

from .admin_utils import get_service_recommendations
from .models import AuditIssue, AuditPage, AuditRun
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
                "monthly_leads_goal": 40,
                "notes": "Run a first-pass audit.",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(AuditRequest.objects.count(), 1)
        self.assertEqual(AuditRun.objects.count(), 1)
        self.assertIn("/tools/audits/", response["Location"])
        mocked_enqueue.assert_called_once()

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
