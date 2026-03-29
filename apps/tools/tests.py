from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from apps.leads.models import AuditRequest

from .models import AuditIssue, AuditRun
from .services import run_public_site_audit


class PublicAuditFlowTests(TestCase):
    @patch("apps.tools.views.run_public_site_audit")
    def test_public_audit_submission_creates_run_and_redirects(self, mocked_run):
        def complete_run(*, audit_run, page_limit=5):
            audit_run.status = AuditRun.Status.COMPLETED
            audit_run.normalized_domain = "example.com"
            audit_run.overall_score = 78
            audit_run.summary = {"quick_wins": [], "service_fit": []}
            audit_run.save()
            return audit_run

        mocked_run.side_effect = complete_run

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
        self.assertEqual(audit_run.performance_score, 84)
        self.assertEqual(audit_run.summary["pagespeed"]["source"], "Google PageSpeed Insights")
