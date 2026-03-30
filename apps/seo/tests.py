from unittest.mock import patch

import requests
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.test.utils import override_settings

from apps.leads.models import AuditRequest, ClientProject
from apps.content.models import GeneratedContent
from apps.tools.models import AuditPage, AuditRun

from .backlinks import build_backlink_snapshot_payload, refresh_project_backlink_intelligence
from .models import (
    BacklinkProspect,
    BacklinkSnapshot,
    SEOCompetitor,
    SEOCompetitorSnapshot,
    SEOContextSnapshot,
    SEOOpportunitySnapshot,
    SEOProjectProfile,
    SEOSiteStructureSnapshot,
)
from .discovery import build_discovery_queries, discover_serp_competitors, fetch_search_results
from .services import (
    build_local_keyword_set,
    build_seo_context_payload,
    build_seo_opportunity_payload,
    get_or_build_seo_snapshot,
)


class SEOContextServiceTests(TestCase):
    @patch("apps.seo.services.discover_serp_competitors")
    @patch("apps.seo.services.fetch_many")
    @patch("apps.seo.services.safe_fetch")
    def test_build_seo_context_payload_generates_local_keyword_clusters(
        self,
        mocked_fetch,
        mocked_fetch_many,
        mocked_discovery,
    ):
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
        mocked_discovery.return_value = {
            "provider": "serpapi",
            "enabled": True,
            "queries": ["used car dealership Nairobi", "best used car dealership Nairobi"],
            "competitors": [
                {
                    "homepage_url": "https://competitor.com/",
                    "normalized_domain": "competitor.com",
                    "label": "competitor.com",
                    "queries": ["used car dealership Nairobi"],
                    "query_count": 1,
                    "best_position": 2,
                    "average_position": 2.0,
                    "sample_titles": ["Best Used Car Dealership Nairobi"],
                    "sample_snippets": ["Buy used cars in Nairobi"],
                    "result_urls": ["https://competitor.com/"],
                    "discovery_score": 33,
                }
            ],
        }
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
        self.assertIn("used car dealership Nairobi", payload["benchmark_summary"]["discovery_queries"])
        self.assertTrue(SEOCompetitor.objects.filter(project=project, is_active=True).exists())

        opportunity_payload = build_seo_opportunity_payload(project, profile, audit_run)
        self.assertTrue(opportunity_payload["keyword_opportunities"])
        self.assertTrue(opportunity_payload["page_map"])
        self.assertTrue(opportunity_payload["execution_queue"])
        self.assertGreaterEqual(opportunity_payload["value_summary"]["competitors_benchmarked"], 1)
        first_task = opportunity_payload["execution_queue"][0]
        self.assertTrue(first_task["edit_targets"])
        self.assertTrue(first_task["edit_targets"][0]["changes"])

    @override_settings(SERP_DISCOVERY_ENABLED=False)
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

    def test_build_seo_opportunity_payload_tolerates_legacy_string_competitor_pages(self):
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
            primary_service="seo agency",
            target_audience="marketing leaders",
        )
        competitor = SEOCompetitor.objects.create(
            project=project,
            homepage_url="https://competitor.com/",
            normalized_domain="competitor.com",
            label="competitor.com",
            source=SEOCompetitor.Source.PROFILE,
            is_active=True,
        )
        SEOCompetitorSnapshot.objects.create(
            competitor=competitor,
            source_audit_run=audit_run,
            output_json={
                "status": "ok",
                "pages": ["https://competitor.com/services/seo/"],
                "summary": {
                    "counts_by_type": {"service": 1},
                    "avg_word_count_by_type": {"service": 420},
                    "faq_schema_pages": 0,
                    "location_match_pages": 1,
                    "page_count": 1,
                },
            },
        )
        context_snapshot = SEOContextSnapshot.objects.create(
            project=project,
            profile=profile,
            source_audit_run=audit_run,
            output_json={
                "context": {
                    "business_type": "agency",
                    "industry_label": "Agency / Professional Services",
                    "location": "Nairobi",
                    "target_goal": "Increase proposal-qualified traffic",
                    "primary_service": "seo agency",
                    "target_audience": "marketing leaders",
                },
                "site_structure": {
                    "pages": [{"url": "https://example.com/", "title": "Home", "page_type": "home"}],
                    "summary": {
                        "counts_by_type": {"home": 1},
                        "avg_word_count_by_type": {"home": 250},
                        "faq_schema_pages": 0,
                        "location_match_pages": 0,
                        "page_count": 1,
                    },
                },
                "recommendations": [],
                "competitors": [
                    {"domain": "competitor.com", "status": "ok", "url": "https://competitor.com/"}
                ],
            },
        )

        payload = build_seo_opportunity_payload(
            project,
            profile,
            audit_run,
            context_snapshot=context_snapshot,
        )

        self.assertTrue(payload["page_map"])
        self.assertTrue(payload["keyword_opportunities"])


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

    @patch("apps.seo.services.discover_serp_competitors")
    @patch("apps.seo.services.fetch_many")
    @patch("apps.seo.services.safe_fetch")
    def test_workspace_seo_post_creates_profile_and_snapshot(self, mocked_fetch, mocked_fetch_many, mocked_discovery):
        self.client.force_login(self.user)
        mocked_fetch.return_value = {
            "final_url": "https://competitor.com/",
            "status_code": 200,
            "body": "<html><head><title>Competitor Nairobi</title></head><body><h1>Competitor</h1></body></html>",
            "headers": {},
            "content_type": "text/html",
            "response_time_ms": 150,
        }
        mocked_discovery.return_value = {
            "provider": "serpapi",
            "enabled": True,
            "queries": ["used car dealership Nairobi", "best used car dealership Nairobi"],
            "competitors": [
                {
                    "homepage_url": "https://competitor.com/",
                    "normalized_domain": "competitor.com",
                    "label": "competitor.com",
                    "queries": ["used car dealership Nairobi"],
                    "query_count": 1,
                    "best_position": 2,
                    "average_position": 2.0,
                    "sample_titles": ["Competitor Nairobi"],
                    "sample_snippets": ["Competitor snippet"],
                    "result_urls": ["https://competitor.com/"],
                    "discovery_score": 33,
                }
            ],
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
        self.assertContains(response, "Exact page edits")
        self.assertContains(response, "used car dealership Nairobi")
        self.assertContains(response, "SERP discovery queries used")
        self.assertContains(response, "No H1 tag detected.")

    @override_settings(SEO_REFRESH_ASYNC=True)
    @patch("apps.seo.views.enqueue_project_seo_refresh")
    def test_workspace_seo_post_queues_refresh_when_async_enabled(self, mocked_enqueue):
        self.client.force_login(self.user)

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

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("seo:workspace-seo"))
        profile = SEOProjectProfile.objects.get(project=self.project)
        self.assertEqual(profile.metadata.get("refresh_status"), "queued")
        mocked_enqueue.assert_called_once_with(self.project.pk)

    def test_workspace_seo_post_infers_business_type_when_left_blank(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("seo:workspace-seo"),
            {
                "business_type": "",
                "location": "Nairobi",
                "target_goal": "Increase qualified organic leads",
                "primary_service": "used car dealership",
                "target_audience": "price-sensitive car buyers",
                "competitor_urls": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        profile = SEOProjectProfile.objects.get(project=self.project)
        self.assertEqual(profile.business_type, "automotive")
        self.assertEqual(profile.metadata.get("business_type_source"), "inferred")

    def test_workspace_backlink_prospect_update_persists_status_and_notes(self):
        snapshot = BacklinkSnapshot.objects.create(
            project=self.project,
            profile=SEOProjectProfile.objects.create(
                project=self.project,
                business_type="automotive",
                location="Nairobi",
                target_goal="Increase qualified organic leads",
                primary_service="used car dealership",
                target_audience="price-sensitive car buyers",
            ),
            source_audit_run=self.audit_run,
            output_json={},
        )
        prospect = BacklinkProspect.objects.create(
            project=self.project,
            snapshot=snapshot,
            domain="example.org",
            homepage_url="https://example.org/",
            prospect_url="https://example.org/resources/",
            title="Example resource page",
            target_asset_title="FAQ asset",
            target_asset_type="faq",
            target_asset_url="https://example.com/faq/",
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("seo:workspace-backlink-prospect-update", args=[prospect.pk]),
            {
                "status": BacklinkProspect.Status.SHORTLISTED,
                "suggested_anchor_text": "used car dealership Nairobi",
                "notes": "Good local association target",
            },
        )

        self.assertEqual(response.status_code, 302)
        prospect.refresh_from_db()
        self.assertEqual(prospect.status, BacklinkProspect.Status.SHORTLISTED)
        self.assertEqual(prospect.suggested_anchor_text, "used car dealership Nairobi")
        self.assertEqual(prospect.metadata.get("notes"), "Good local association target")


class BacklinkIntelligenceTests(TestCase):
    @patch("apps.seo.backlinks.fetch_search_results")
    def test_build_backlink_snapshot_payload_generates_assets_and_scored_prospects(self, mocked_fetch):
        audit_request = AuditRequest.objects.create(
            company_name="Northwind",
            email="ops@example.com",
            website="https://example.com",
        )
        audit_run = AuditRun.objects.create(
            audit_request=audit_request,
            normalized_domain="example.com",
            start_url="https://example.com/",
            overall_score=72,
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
            latest_score=72,
        )
        profile = SEOProjectProfile.objects.create(
            project=project,
            business_type="automotive",
            location="Nairobi",
            target_goal="Increase qualified leads",
            primary_service="used car dealership",
            target_audience="price-sensitive car buyers",
        )
        GeneratedContent.objects.create(
            project=project,
            output_type=GeneratedContent.OutputType.ARTICLE,
            title="Used Car Buying Guide Nairobi",
            business_type="automotive",
            location="Nairobi",
            target_audience="price-sensitive car buyers",
            page_goal="Generate citations",
            offer_summary="used car dealership",
            target_keywords=["used car dealership Nairobi"],
            body="Guide body",
            cta="CTA",
            brief_json={"summary": "Useful guide asset", "action": "Publish and pitch this guide."},
        )
        mocked_fetch.return_value = {
            "provider": "duckduckgo",
            "payload": {
                "organic_results": [
                    {
                        "position": 1,
                        "title": "Nairobi automotive association resources",
                        "link": "https://association.or.ke/resources/used-cars/",
                        "snippet": "Resources for used car buyers in Nairobi",
                    },
                    {
                        "position": 2,
                        "title": "Unrelated travel blog",
                        "link": "https://travelblog.example.com/nairobi/",
                        "snippet": "Things to do in Nairobi",
                    },
                ],
                "local_results": [],
            },
            "errors": [],
        }

        payload = build_backlink_snapshot_payload(
            project,
            profile,
            {"context": {"priority_pages": ["Build service pages"]}},
            {
                "page_map": [
                    {
                        "page_type": "faq",
                        "page_type_label": "FAQ",
                        "status": "optimize",
                        "priority_score": 85,
                        "target_keyword": "used car sales nairobi faq",
                        "target_urls": ["https://example.com/faq/"],
                        "reason": "FAQ coverage is weak.",
                        "action": "Improve the FAQ page and make it more citeable.",
                    }
                ]
            },
        )

        self.assertTrue(payload["linkable_assets"])
        self.assertTrue(payload["prospects"])
        self.assertEqual(payload["prospects"][0]["domain"], "association.or.ke")
        self.assertGreater(payload["prospects"][0]["total_score"], 0)

    @patch("apps.seo.backlinks.fetch_search_results")
    def test_refresh_project_backlink_intelligence_creates_snapshot_and_prospects(self, mocked_fetch):
        audit_request = AuditRequest.objects.create(
            company_name="Northwind",
            email="ops@example.com",
            website="https://example.com",
        )
        audit_run = AuditRun.objects.create(
            audit_request=audit_request,
            normalized_domain="example.com",
            start_url="https://example.com/",
            overall_score=72,
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
            latest_score=72,
        )
        profile = SEOProjectProfile.objects.create(
            project=project,
            business_type="automotive",
            location="Nairobi",
            target_goal="Increase qualified leads",
            primary_service="used car dealership",
            target_audience="price-sensitive car buyers",
        )
        context_snapshot = SEOContextSnapshot.objects.create(
            project=project,
            profile=profile,
            source_audit_run=audit_run,
            output_json={"context": {"priority_pages": ["Build service pages"]}},
        )
        opportunity_snapshot = SEOOpportunitySnapshot.objects.create(
            project=project,
            profile=profile,
            source_audit_run=audit_run,
            source_context_snapshot=context_snapshot,
            output_json={
                "page_map": [
                    {
                        "page_type": "service",
                        "page_type_label": "Service",
                        "status": "missing",
                        "priority_score": 92,
                        "target_keyword": "used car dealership Nairobi",
                        "target_urls": [],
                        "reason": "Missing service page.",
                        "action": "Create a dedicated service page.",
                    }
                ]
            },
        )
        mocked_fetch.return_value = {
            "provider": "duckduckgo",
            "payload": {
                "organic_results": [
                    {
                        "position": 1,
                        "title": "Used car dealership Nairobi association",
                        "link": "https://association.or.ke/members/",
                        "snippet": "Directory of used car dealership businesses in Nairobi",
                    }
                ],
                "local_results": [],
            },
            "errors": [],
        }

        snapshot = refresh_project_backlink_intelligence(
            project,
            context_snapshot=context_snapshot,
            opportunity_snapshot=opportunity_snapshot,
        )

        self.assertIsNotNone(snapshot)
        self.assertEqual(BacklinkSnapshot.objects.count(), 1)
        self.assertTrue(BacklinkProspect.objects.filter(project=project).exists())


class SEOCompetitorDiscoveryTests(TestCase):
    def test_build_local_keyword_set_uses_business_specific_terms(self):
        profile = SEOProjectProfile(
            business_type="automotive",
            location="Nairobi",
            target_goal="Increase qualified leads",
            primary_service="used car sales",
            target_audience="price-sensitive car buyers",
        )

        keywords = build_local_keyword_set(profile)

        self.assertIn("used cars for sale Nairobi", keywords)
        self.assertIn("car dealer Nairobi", keywords)
        self.assertNotIn("service Nairobi", keywords)

    def test_build_discovery_queries_uses_service_location_and_audience(self):
        profile = SEOProjectProfile(
            business_type="automotive",
            location="Nairobi",
            target_goal="Increase qualified leads",
            primary_service="used car dealership",
            target_audience="price-sensitive car buyers",
        )

        queries = build_discovery_queries(profile)

        self.assertIn("used car dealership Nairobi", queries)
        self.assertIn("best used car dealership Nairobi", queries)
        self.assertIn("used car dealership near me", queries)

    @override_settings(
        SERP_DISCOVERY_ENABLED=True,
        SERP_DISCOVERY_PROVIDER="serpapi",
        SERPAPI_API_KEY="test-key",
        SERP_DISCOVERY_QUERY_LIMIT=2,
        SERP_DISCOVERY_RESULTS_PER_QUERY=5,
    )
    @patch("apps.seo.discovery.fetch_serpapi_results")
    def test_discover_serp_competitors_aggregates_real_result_domains(self, mocked_serp_fetch):
        audit_request = AuditRequest.objects.create(
            company_name="Northwind",
            email="ops@example.com",
            website="https://example.com",
        )
        project = ClientProject.objects.create(
            audit_request=audit_request,
            name="Northwind",
            website="https://example.com",
            normalized_domain="example.com",
            contact_email="ops@example.com",
        )
        profile = SEOProjectProfile.objects.create(
            project=project,
            business_type="automotive",
            location="Nairobi",
            target_goal="Increase qualified leads",
            primary_service="used car dealership",
            target_audience="price-sensitive car buyers",
        )
        mocked_serp_fetch.side_effect = [
            {
                "organic_results": [
                    {
                        "position": 1,
                        "title": "Best Used Cars Nairobi",
                        "link": "https://competitor-a.com/used-cars/",
                        "snippet": "Used cars in Nairobi",
                    },
                    {
                        "position": 2,
                        "title": "Competitor B Nairobi",
                        "link": "https://competitor-b.com/",
                        "snippet": "Another used car dealer",
                    },
                ],
                "local_results": [],
            },
            {
                "organic_results": [
                    {
                        "position": 3,
                        "title": "Best Used Cars Nairobi",
                        "link": "https://competitor-a.com/pricing/",
                        "snippet": "Pricing for used cars",
                    }
                ],
                "local_results": [],
            },
        ]

        discovery = discover_serp_competitors(project, profile)

        self.assertTrue(discovery["enabled"])
        self.assertEqual(len(discovery["queries"]), 2)
        self.assertEqual(discovery["competitors"][0]["normalized_domain"], "competitor-a.com")
        self.assertEqual(discovery["competitors"][0]["query_count"], 2)
        self.assertEqual(discovery["competitors"][0]["best_position"], 1)
        self.assertTrue(discovery["competitors"][0]["average_relevance"] >= 4)

    @override_settings(
        SERP_DISCOVERY_ENABLED=True,
        SERP_DISCOVERY_PROVIDER="serpapi",
        SERPAPI_API_KEY="test-key",
        SERP_DISCOVERY_QUERY_LIMIT=1,
        SERP_DISCOVERY_RESULTS_PER_QUERY=5,
    )
    @patch("apps.seo.discovery.fetch_serpapi_results")
    def test_discover_serp_competitors_tolerates_string_and_nested_local_results(self, mocked_serp_fetch):
        audit_request = AuditRequest.objects.create(
            company_name="Northwind",
            email="ops@example.com",
            website="https://example.com",
        )
        project = ClientProject.objects.create(
            audit_request=audit_request,
            name="Northwind",
            website="https://example.com",
            normalized_domain="example.com",
            contact_email="ops@example.com",
        )
        profile = SEOProjectProfile.objects.create(
            project=project,
            business_type="automotive",
            location="Nairobi",
            target_goal="Increase qualified leads",
            primary_service="used car dealership",
            target_audience="price-sensitive car buyers",
        )
        mocked_serp_fetch.return_value = {
            "organic_results": [
                "https://competitor-a.com/used-cars/",
                {
                    "position": 2,
                    "title": "Competitor B Nairobi",
                    "link": "https://competitor-b.com/",
                    "snippet": "Another used car dealer",
                },
            ],
            "local_results": {
                "places": [
                    {
                        "position": 3,
                        "title": "Competitor C Nairobi",
                        "website": "https://competitor-c.com/",
                        "description": "Local competitor",
                    }
                ]
            },
        }

        discovery = discover_serp_competitors(project, profile)

        domains = [item["normalized_domain"] for item in discovery["competitors"]]
        self.assertIn("competitor-a.com", domains)
        self.assertIn("competitor-b.com", domains)
        self.assertNotIn("competitor-c.com", domains)

    @override_settings(
        SERP_DISCOVERY_ENABLED=True,
        SERP_DISCOVERY_PROVIDER="serpapi",
        SERPAPI_API_KEY="test-key",
        SERP_DISCOVERY_QUERY_LIMIT=1,
        SERP_DISCOVERY_RESULTS_PER_QUERY=5,
    )
    @patch("apps.seo.discovery.fetch_serpapi_results")
    def test_discover_serp_competitors_filters_low_relevance_noise(self, mocked_serp_fetch):
        audit_request = AuditRequest.objects.create(
            company_name="Northwind",
            email="ops@example.com",
            website="https://example.com",
        )
        project = ClientProject.objects.create(
            audit_request=audit_request,
            name="Northwind",
            website="https://example.com",
            normalized_domain="example.com",
            contact_email="ops@example.com",
        )
        profile = SEOProjectProfile.objects.create(
            project=project,
            business_type="automotive",
            location="Nairobi",
            target_goal="Increase qualified leads",
            primary_service="used car dealership",
            target_audience="price-sensitive car buyers",
        )
        mocked_serp_fetch.return_value = {
            "organic_results": [
                {
                    "position": 1,
                    "title": "Used Car Dealership Nairobi",
                    "link": "https://competitor-a.com/",
                    "snippet": "Buy used cars in Nairobi",
                },
                {
                    "position": 2,
                    "title": "Nairobi travel guide",
                    "link": "https://random-blog.com/",
                    "snippet": "Things to do in Nairobi",
                },
            ],
            "local_results": [],
        }

        discovery = discover_serp_competitors(project, profile)

        domains = [item["normalized_domain"] for item in discovery["competitors"]]
        self.assertIn("competitor-a.com", domains)
        self.assertNotIn("random-blog.com", domains)

    @override_settings(
        SERP_DISCOVERY_ENABLED=True,
        SERP_DISCOVERY_PROVIDER="serpapi",
        SERPAPI_API_KEY="test-key",
        SERP_DISCOVERY_QUERY_LIMIT=1,
        SERP_DISCOVERY_RESULTS_PER_QUERY=5,
    )
    @patch("apps.seo.discovery.fetch_serpapi_results")
    def test_discover_serp_competitors_filters_foreign_and_non_competitor_results(self, mocked_serp_fetch):
        audit_request = AuditRequest.objects.create(
            company_name="Northwind",
            email="ops@example.com",
            website="https://example.com",
        )
        project = ClientProject.objects.create(
            audit_request=audit_request,
            name="Northwind",
            website="https://example.com",
            normalized_domain="example.com",
            contact_email="ops@example.com",
        )
        profile = SEOProjectProfile.objects.create(
            project=project,
            business_type="automotive",
            location="Nairobi",
            target_goal="Increase qualified leads",
            primary_service="used car dealership",
            target_audience="price-sensitive car buyers",
        )
        mocked_serp_fetch.return_value = {
            "organic_results": [
                {
                    "position": 1,
                    "title": "Used Cars Nairobi | Car Dealer in Kenya",
                    "link": "https://relevant-cars.co.ke/",
                    "snippet": "Buy used cars in Nairobi from a trusted car dealer.",
                },
                {
                    "position": 2,
                    "title": "Top 10 Cleaning Companies in Austin TX",
                    "link": "https://nairobionlineblog.wordpress.com/2026/03/21/top-10-cleaning-companies-in-austin-tx/",
                    "snippet": "A list of cleaning companies in Austin.",
                },
                {
                    "position": 3,
                    "title": "D7 Lead Finder - Find Free Business Leads In Any Industry",
                    "link": "https://d7leadfinder.com/",
                    "snippet": "Lead generation software for any business.",
                },
            ],
            "local_results": [],
        }

        discovery = discover_serp_competitors(project, profile)

        domains = [item["normalized_domain"] for item in discovery["competitors"]]
        self.assertIn("relevant-cars.co.ke", domains)
        self.assertNotIn("nairobionlineblog.wordpress.com", domains)
        self.assertNotIn("d7leadfinder.com", domains)

    @override_settings(
        SERP_DISCOVERY_ENABLED=True,
        SERP_DISCOVERY_PROVIDER="serpapi",
        SERPAPI_API_KEY="test-key",
        SERP_DISCOVERY_QUERY_LIMIT=1,
        SERP_DISCOVERY_RESULTS_PER_QUERY=5,
    )
    @patch("apps.seo.discovery.fetch_serpapi_results", return_value="unexpected-payload")
    def test_discover_serp_competitors_degrades_when_provider_payload_is_invalid(self, mocked_serp_fetch):
        audit_request = AuditRequest.objects.create(
            company_name="Northwind",
            email="ops@example.com",
            website="https://example.com",
        )
        project = ClientProject.objects.create(
            audit_request=audit_request,
            name="Northwind",
            website="https://example.com",
            normalized_domain="example.com",
            contact_email="ops@example.com",
        )
        profile = SEOProjectProfile.objects.create(
            project=project,
            business_type="automotive",
            location="Nairobi",
            target_goal="Increase qualified leads",
            primary_service="used car dealership",
            target_audience="price-sensitive car buyers",
        )

        discovery = discover_serp_competitors(project, profile)

        self.assertTrue(discovery["enabled"])
        self.assertEqual(discovery["competitors"], [])
        self.assertEqual(discovery["errors"], [])

    @override_settings(
        SERP_DISCOVERY_ENABLED=True,
        SERP_DISCOVERY_PROVIDER="serpapi,duckduckgo",
        SERPAPI_API_KEY="test-key",
    )
    @patch("apps.seo.discovery.fetch_duckduckgo_results")
    @patch("apps.seo.discovery.fetch_serpapi_results", side_effect=requests.RequestException("serpapi unavailable"))
    def test_fetch_search_results_falls_back_to_duckduckgo(self, mocked_serpapi, mocked_duckduckgo):
        mocked_duckduckgo.return_value = {
            "organic_results": [
                {
                    "position": 1,
                    "title": "Fallback result",
                    "link": "https://fallback.example.com/",
                    "snippet": "Fallback snippet",
                }
            ],
            "local_results": [],
        }

        result = fetch_search_results("used car dealership Nairobi", location="Nairobi")

        self.assertEqual(result["provider"], "duckduckgo")
        self.assertTrue(result["payload"]["organic_results"])
        self.assertEqual(result["errors"][0]["provider"], "serpapi")
