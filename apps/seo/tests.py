from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.leads.models import AuditRequest, ClientProject
from apps.tools.models import AuditPage, AuditRun

from .models import (
    SEOCompetitor,
    SEOContextSnapshot,
    SEOOpportunitySnapshot,
    SEOProjectProfile,
    SEOSiteStructureSnapshot,
)
from .services import build_seo_context_payload, build_seo_opportunity_payload, get_or_build_seo_snapshot


class SEOContextServiceTests(TestCase):
    @patch("apps.seo.services.fetch_many")
    @patch("apps.seo.services.safe_fetch")
    def test_build_seo_context_payload_generates_local_keyword_clusters(self, mocked_fetch, mocked_fetch_many):
        audit_request = AuditRequest.objects.create(
            company_name="Northwind",
            email="ops@example.com",
            website="https://example.com",
            competitor_urls=["https://competitor.com"],
        )
        audit_run = AuditRun.objects.create(
            audit_request=audit_request,
            normalized_domain="example.com",
            start_url="https://example.com/",
            overall_score=68,
            technical_score=61,
            on_page_score=55,
            content_score=73,
            aeo_score=64,
            status=AuditRun.Status.COMPLETED,
            summary={
                "featured_recommendations": [
                    {
                        "title": "No H1 tag detected.",
                        "category": "On-page",
                        "category_key": "on_page",
                        "priority_score": 91,
                        "recommended_fix": "Add a single H1 to each affected service page.",
                        "estimated_impact": "Improves ranking alignment and click-through clarity.",
                        "page_examples": ["https://example.com/vehicles/"],
                        "technical_steps": ["Inspect the heading structure on the affected URL."],
                    }
                ],
                "score_breakdown": {
                    "on_page": {"label": "On-page", "score": 55, "next_step": "Fix headings and metadata on revenue pages."}
                },
            },
        )
        project = ClientProject.objects.create(
            audit_request=audit_request,
            latest_audit_run=audit_run,
            name="Northwind",
            website="https://example.com",
            normalized_domain="example.com",
            contact_email="ops@example.com",
            latest_score=68,
        )
        profile = SEOProjectProfile.objects.create(
            project=project,
            business_type="automotive",
            location="Nairobi",
            target_goal="Increase qualified organic leads",
            primary_service="used car dealership",
            target_audience="price-sensitive car buyers",
        )
        AuditPage.objects.create(
            audit_run=audit_run,
            url="https://example.com/vehicles/",
            status_code=200,
            title="Used Car Dealership Nairobi",
            h1="Used Cars in Nairobi",
            word_count=180,
        )

        def fake_fetch(url, session=None, timeout=10):
            if "sitemap.xml" in url:
                return {
                    "final_url": url,
                    "status_code": 200,
                    "body": "<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'><url><loc>https://competitor.com/pricing/</loc></url><url><loc>https://competitor.com/faq/</loc></url></urlset>",
                    "headers": {},
                    "content_type": "application/xml",
                    "response_time_ms": 120,
                }
            return {
                "final_url": "https://competitor.com/",
                "status_code": 200,
                "body": "<html><head><title>Best Used Car Dealership Nairobi</title><meta name='description' content='Buy used cars in Nairobi'></head><body><h1>Used Cars Nairobi</h1><a href='/pricing/'>Pricing</a><a href='/faq/'>FAQ</a></body></html>",
                "headers": {},
                "content_type": "text/html",
                "response_time_ms": 200,
            }

        mocked_fetch.side_effect = fake_fetch
        mocked_fetch_many.return_value = {
            "https://competitor.com/": {
                "final_url": "https://competitor.com/",
                "status_code": 200,
                "body": "<html><head><title>Best Used Car Dealership Nairobi</title></head><body><h1>Used Cars Nairobi</h1></body></html>",
                "headers": {},
                "content_type": "text/html",
                "response_time_ms": 200,
            },
            "https://competitor.com/pricing/": {
                "final_url": "https://competitor.com/pricing/",
                "status_code": 200,
                "body": "<html><head><title>Used Car Pricing Nairobi</title></head><body><h1>Pricing</h1></body></html>",
                "headers": {},
                "content_type": "text/html",
                "response_time_ms": 220,
            },
            "https://competitor.com/faq/": {
                "final_url": "https://competitor.com/faq/",
                "status_code": 200,
                "body": "<html><head><title>Used Car FAQ Nairobi</title></head><body><h1>FAQ</h1><script type='application/ld+json'>{}</script></body></html>",
                "headers": {},
                "content_type": "text/html",
                "response_time_ms": 180,
            },
        }

        payload = build_seo_context_payload(project, profile, audit_run)

        self.assertEqual(payload["context"]["industry_label"], "Automotive")
        self.assertIn("core commercial", payload["keyword_clusters"])
        self.assertIn("used car dealership Nairobi", payload["keyword_clusters"]["core commercial"])
        self.assertTrue(payload["recommendations"])
        self.assertIn("Nairobi", payload["recommendations"][0]["why_it_matters"])
        self.assertTrue(payload["competitors"])
        self.assertGreaterEqual(payload["benchmark_summary"]["available_competitors"], 1)
        self.assertTrue(SEOCompetitor.objects.filter(project=project, is_active=True).exists())

        opportunity_payload = build_seo_opportunity_payload(project, profile, audit_run)
        self.assertTrue(opportunity_payload["keyword_opportunities"])
        self.assertTrue(opportunity_payload["page_map"])
        self.assertTrue(opportunity_payload["execution_queue"])
        self.assertGreaterEqual(opportunity_payload["value_summary"]["competitors_benchmarked"], 1)

    def test_get_or_build_seo_snapshot_reuses_existing_snapshot_for_same_inputs(self):
        audit_request = AuditRequest.objects.create(
            company_name="Northwind",
            email="ops@example.com",
            website="https://example.com",
        )
        audit_run = AuditRun.objects.create(
            audit_request=audit_request,
            normalized_domain="example.com",
            start_url="https://example.com/",
            overall_score=70,
            status=AuditRun.Status.COMPLETED,
            summary={},
        )
        project = ClientProject.objects.create(
            audit_request=audit_request,
            latest_audit_run=audit_run,
            name="Northwind",
            website="https://example.com",
            normalized_domain="example.com",
            contact_email="ops@example.com",
            latest_score=70,
        )
        profile = SEOProjectProfile.objects.create(
            project=project,
            business_type="agency",
            location="Nairobi",
            target_goal="Increase proposal-qualified traffic",
        )

        first = get_or_build_seo_snapshot(project=project, profile=profile, audit_run=audit_run)
        second = get_or_build_seo_snapshot(project=project, profile=profile, audit_run=audit_run)

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(SEOContextSnapshot.objects.count(), 1)
        self.assertEqual(SEOSiteStructureSnapshot.objects.count(), 1)
        self.assertEqual(SEOOpportunitySnapshot.objects.count(), 0)


class WorkspaceSEOViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="seo@example.com",
            email="seo@example.com",
            password="strongpass123",
        )
        audit_request = AuditRequest.objects.create(
            company_name="Northwind",
            email="seo@example.com",
            website="https://example.com",
        )
        self.audit_run = AuditRun.objects.create(
            audit_request=audit_request,
            normalized_domain="example.com",
            start_url="https://example.com/",
            overall_score=77,
            technical_score=74,
            on_page_score=61,
            content_score=80,
            aeo_score=69,
            status=AuditRun.Status.COMPLETED,
            summary={
                "featured_recommendations": [
                    {
                        "title": "No H1 tag detected.",
                        "category": "On-page",
                        "category_key": "on_page",
                        "priority_score": 92,
                        "recommended_fix": "Add a single H1 that aligns with the page topic.",
                        "estimated_impact": "Improves ranking alignment and click-through clarity.",
                        "page_examples": ["https://example.com/about-us"],
                        "technical_steps": ["Update the main heading on the affected page."],
                    }
                ],
                "score_breakdown": {
                    "on_page": {
                        "label": "On-page",
                        "score": 61,
                        "issues": 3,
                        "next_step": "Fix headings and metadata on priority pages.",
                    }
                },
            },
        )
        self.project = ClientProject.objects.create(
            owner=self.user,
            audit_request=audit_request,
            latest_audit_run=self.audit_run,
            name="Northwind",
            website="https://example.com",
            normalized_domain="example.com",
            contact_email="seo@example.com",
            latest_score=77,
        )

    def test_workspace_seo_view_renders_profile_form(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("seo:workspace-seo"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Business and competitor context")
        self.assertContains(response, "Refresh SEO Intelligence")

    @patch("apps.seo.services.fetch_many")
    @patch("apps.seo.services.safe_fetch")
    def test_workspace_seo_post_creates_profile_and_snapshot(self, mocked_fetch, mocked_fetch_many):
        self.client.force_login(self.user)
        mocked_fetch.return_value = {
            "final_url": "https://competitor.com/",
            "status_code": 200,
            "body": "<html><head><title>Competitor Nairobi</title></head><body><h1>Competitor</h1></body></html>",
            "headers": {},
            "content_type": "text/html",
            "response_time_ms": 150,
        }
        mocked_fetch_many.return_value = {
            "https://competitor.com/": mocked_fetch.return_value,
        }

        response = self.client.post(
            reverse("seo:workspace-seo"),
            {
                "business_type": "automotive",
                "location": "Nairobi",
                "target_goal": "Increase qualified organic leads",
                "primary_service": "used car dealership",
                "target_audience": "price-sensitive car buyers",
                "competitor_urls": "https://competitor.com",
            },
        )

        self.assertEqual(response.status_code, 200)
        profile = SEOProjectProfile.objects.get(project=self.project)
        snapshot = SEOContextSnapshot.objects.get(project=self.project)
        opportunity_snapshot = SEOOpportunitySnapshot.objects.get(project=self.project)
        self.assertEqual(profile.location, "Nairobi")
        self.assertEqual(snapshot.source_audit_run, self.audit_run)
        self.assertEqual(opportunity_snapshot.source_audit_run, self.audit_run)
        self.assertContains(response, "SEO Opportunity Roadmap")
        self.assertContains(response, "Keyword Opportunity Queue")
        self.assertContains(response, "Execution Queue")
        self.assertContains(response, "used car dealership Nairobi")
        self.assertContains(response, "No H1 tag detected.")
