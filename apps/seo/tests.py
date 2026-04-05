from datetime import timedelta
from unittest.mock import patch

import requests
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.test.utils import override_settings
from django.utils import timezone

from apps.leads.models import AuditRequest, ClientProject, UsageRecord, WorkspaceCreditLedger, WorkspacePlan, WorkspaceSubscription
from apps.content.models import ContentEditorialTask, GeneratedContent
from apps.tools.models import AuditPage, AuditRun

from .backlinks import build_backlink_snapshot_payload, refresh_project_backlink_intelligence
from .models import (
    BacklinkProspect,
    BacklinkSnapshot,
    SEOCampaign,
    SEOCompetitor,
    SEOCompetitorSnapshot,
    SEOContextSnapshot,
    SEOOpportunitySnapshot,
    SEOProjectProfile,
    SEOShareLink,
    SEOSiteStructureSnapshot,
)
from .discovery import build_discovery_queries, build_discovery_routes, discover_serp_competitors, fetch_search_results
from .services import (
    build_campaign_workspace_items,
    build_competitor_trend_summary,
    build_local_keyword_set,
    build_serp_evidence_history,
    build_seo_context_payload,
    build_seo_opportunity_payload,
    get_or_build_seo_snapshot,
    sync_project_campaign_chain,
    sync_project_seo_campaigns,
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
            "market_surfaces": [
                {
                    "homepage_url": "https://www.google.com/maps",
                    "normalized_domain": "www.google.com",
                    "label": "www.google.com",
                    "bucket": "market_surface",
                    "bucket_label": "Market Surface",
                    "bucket_reason": "comparison-surface",
                    "queries": ["used car dealership Nairobi"],
                    "query_count": 1,
                    "best_position": 1,
                    "average_position": 1.0,
                    "average_relevance": 9.0,
                }
            ],
            "citation_sources": [
                {
                    "homepage_url": "https://www.yelp.com/",
                    "normalized_domain": "www.yelp.com",
                    "label": "www.yelp.com",
                    "bucket": "citation_source",
                    "bucket_label": "Citation Source",
                    "bucket_reason": "citation-host",
                    "queries": ["used car dealership Nairobi"],
                    "query_count": 1,
                    "best_position": 4,
                    "average_position": 4.0,
                    "average_relevance": 6.0,
                }
            ],
            "backlink_prospects": [
                {
                    "homepage_url": "https://industryblog.example.com/",
                    "normalized_domain": "industryblog.example.com",
                    "label": "industryblog.example.com",
                    "bucket": "backlink_prospect",
                    "bucket_label": "Backlink Prospect",
                    "bucket_reason": "editorial-surface",
                    "queries": ["used car dealership Nairobi"],
                    "query_count": 1,
                    "best_position": 6,
                    "average_position": 6.0,
                    "average_relevance": 5.0,
                }
            ],
            "routing_policy": {
                "business_type": "automotive",
                "primary_service": "used car dealership",
                "event_focused_hospitality": False,
                "source_families": [
                    "web_search",
                    "benchmark_competitors",
                    "market_surfaces",
                    "citation_sources",
                    "backlink_prospects",
                ],
            },
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
        self.assertIn("root_cause_label", payload["recommendations"][0])
        self.assertGreater(payload["recommendations"][0]["evidence_score"], 0)
        self.assertTrue(payload["competitors"])
        self.assertTrue(payload["competitor_patterns"])
        self.assertTrue(payload["page_comparisons"])
        self.assertGreaterEqual(payload["benchmark_summary"]["available_competitors"], 1)
        self.assertIn("used car dealership Nairobi", payload["benchmark_summary"]["discovery_queries"])
        self.assertEqual(payload["benchmark_summary"]["market_surfaces_observed"], 1)
        self.assertEqual(payload["benchmark_summary"]["citation_sources_observed"], 1)
        self.assertEqual(payload["benchmark_summary"]["backlink_sources_observed"], 1)
        self.assertEqual(payload["discovery"]["routing_policy"]["business_type"], "automotive")
        self.assertTrue(SEOCompetitor.objects.filter(project=project, is_active=True).exists())

        opportunity_payload = build_seo_opportunity_payload(project, profile, audit_run)
        self.assertTrue(opportunity_payload["keyword_opportunities"])
        self.assertTrue(opportunity_payload["page_map"])
        self.assertTrue(opportunity_payload["execution_queue"])
        self.assertGreaterEqual(opportunity_payload["value_summary"]["competitors_benchmarked"], 1)
        self.assertEqual(opportunity_payload["value_summary"]["market_surfaces"], 1)
        self.assertEqual(opportunity_payload["value_summary"]["citation_sources"], 1)
        self.assertEqual(opportunity_payload["value_summary"]["backlink_sources"], 1)
        first_task = opportunity_payload["execution_queue"][0]
        self.assertTrue(first_task["edit_targets"])
        self.assertTrue(first_task["edit_targets"][0]["changes"])
        self.assertIn("confidence_label", first_task)

    @override_settings(SERP_DISCOVERY_ENABLED=False)
    @patch("apps.seo.services.fetch_many")
    @patch("apps.seo.services.safe_fetch")
    def test_build_seo_context_payload_respects_manual_competitor_suppression(
        self,
        mocked_fetch,
        mocked_fetch_many,
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
        competitor = SEOCompetitor.objects.create(
            project=project,
            homepage_url="https://competitor.com",
            normalized_domain="competitor.com",
            label="competitor.com",
            source=SEOCompetitor.Source.PROFILE,
            is_active=True,
            metadata={"review": {"decision": "suppressed", "note": "Wrong business class"}},
        )

        def fake_fetch(url, session=None, timeout=10):
            if "sitemap.xml" in url:
                return {
                    "final_url": url,
                    "status_code": 200,
                    "body": "<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'><url><loc>https://competitor.com/pricing/</loc></url></urlset>",
                    "headers": {},
                    "content_type": "application/xml",
                    "response_time_ms": 120,
                }
            return {
                "final_url": "https://competitor.com/",
                "status_code": 200,
                "body": "<html><head><title>Best Used Car Dealership Nairobi</title></head><body><h1>Used Cars Nairobi</h1><a href='/pricing/'>Pricing</a></body></html>",
                "headers": {},
                "content_type": "text/html",
                "response_time_ms": 180,
            }

        mocked_fetch.side_effect = fake_fetch
        mocked_fetch_many.return_value = {
            "https://competitor.com/": fake_fetch("https://competitor.com/"),
            "https://competitor.com/pricing/": {
                "final_url": "https://competitor.com/pricing/",
                "status_code": 200,
                "body": "<html><head><title>Used Car Pricing Nairobi</title></head><body><h1>Pricing</h1></body></html>",
                "headers": {},
                "content_type": "text/html",
                "response_time_ms": 200,
            },
        }

        payload = build_seo_context_payload(project, profile, audit_run)

        self.assertEqual(payload["competitors"], [])
        self.assertEqual(payload["competitor_trace"][0]["final_decision"], "suppressed")
        self.assertEqual(payload["competitor_trace"][0]["review_note"], "Wrong business class")
        self.assertFalse(payload["competitor_trace"][0]["included"])

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

    def test_build_serp_evidence_history_and_competitor_trends_from_snapshots(self):
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
            business_type="automotive",
            location="Nairobi",
            target_goal="Increase qualified organic leads",
            primary_service="used car dealership",
        )
        first = SEOContextSnapshot.objects.create(
            project=project,
            profile=profile,
            source_audit_run=audit_run,
            output_json={
                "benchmark_summary": {
                    "included_competitors": 2,
                    "filtered_out_competitors": 3,
                    "average_relevance": 7.2,
                },
                "discovery": {"queries": ["used car dealership Nairobi", "car financing Nairobi"]},
                "competitor_trace": [
                    {
                        "domain": "competitor-a.com",
                        "url": "https://competitor-a.com/",
                        "included": True,
                        "status": "ok",
                        "best_position": 3,
                        "average_relevance": 7.0,
                        "final_decision_label": "Accepted",
                        "queries": ["used car dealership Nairobi"],
                    },
                    {
                        "domain": "competitor-b.com",
                        "url": "https://competitor-b.com/",
                        "included": True,
                        "status": "ok",
                        "best_position": 4,
                        "average_relevance": 7.4,
                        "final_decision_label": "Accepted",
                        "queries": ["car financing Nairobi"],
                    },
                ],
            },
        )
        second = SEOContextSnapshot.objects.create(
            project=project,
            profile=profile,
            source_audit_run=audit_run,
            output_json={
                "benchmark_summary": {
                    "included_competitors": 3,
                    "filtered_out_competitors": 1,
                    "average_relevance": 8.4,
                },
                "discovery": {"queries": ["used cars for sale Nairobi", "best used car dealer Nairobi"]},
                "competitor_trace": [
                    {
                        "domain": "competitor-a.com",
                        "url": "https://competitor-a.com/",
                        "included": True,
                        "status": "ok",
                        "best_position": 2,
                        "average_relevance": 8.6,
                        "final_decision_label": "Accepted",
                        "queries": ["used cars for sale Nairobi"],
                    },
                    {
                        "domain": "competitor-c.com",
                        "url": "https://competitor-c.com/",
                        "included": True,
                        "status": "ok",
                        "best_position": 5,
                        "average_relevance": 8.1,
                        "final_decision_label": "Accepted",
                        "queries": ["best used car dealer Nairobi"],
                    },
                ],
            },
        )

        history = build_serp_evidence_history(project)
        trends = build_competitor_trend_summary(project)

        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["snapshot_id"], first.pk)
        self.assertEqual(history[1]["snapshot_id"], second.pk)
        self.assertEqual(history[1]["relevance_delta"], 1.2)
        self.assertIn("competitor-a.com", history[1]["included_domains"])
        self.assertEqual(trends[0]["domain"], "competitor-a.com")
        self.assertEqual(trends[0]["appearances"], 2)
        self.assertEqual(trends[0]["best_position"], 2)

    def test_sync_project_seo_campaigns_creates_campaigns_from_execution_queue(self):
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
            business_type="automotive",
            location="Nairobi",
            target_goal="Increase qualified organic leads",
            primary_service="used car dealership",
        )
        context_snapshot = SEOContextSnapshot.objects.create(
            project=project,
            profile=profile,
            source_audit_run=audit_run,
            output_json={"context": {}, "benchmark_summary": {}},
        )
        opportunity_snapshot = SEOOpportunitySnapshot.objects.create(
            project=project,
            profile=profile,
            source_audit_run=audit_run,
            source_context_snapshot=context_snapshot,
            output_json={
                "execution_queue": [
                    {
                        "title": "Upgrade FAQ coverage",
                        "page_type": "faq",
                        "target_keyword": "used car dealership Nairobi faq",
                        "keywords": ["used car dealership Nairobi faq", "used car dealer faqs Nairobi"],
                        "target_urls": ["https://example.com/faq/"],
                        "action_steps": [
                            "Tighten titles, headings, internal links, and local modifiers on faq pages.",
                            "Re-run SEO refresh and audit validation.",
                        ],
                        "priority_score": 91,
                        "deliverable": "Improve the current FAQ pages",
                        "where_to_apply": ["https://example.com/faq/"],
                        "edit_targets": [{"url": "https://example.com/faq/", "changes": ["Update title", "Expand FAQ coverage"]}],
                    }
                ]
            },
        )

        campaigns = sync_project_seo_campaigns(
            project,
            context_snapshot=context_snapshot,
            opportunity_snapshot=opportunity_snapshot,
        )

        self.assertEqual(len(campaigns), 1)
        campaign = campaigns[0]
        self.assertEqual(campaign.title, "Upgrade FAQ coverage")
        self.assertEqual(campaign.target_keyword, "used car dealership Nairobi faq")
        self.assertEqual(campaign.related_page_urls, ["https://example.com/faq/"])
        self.assertEqual(campaign.status, SEOCampaign.Status.QUEUED)

    def test_sync_project_campaign_chain_links_editorial_drafts_backlinks_and_validation(self):
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
            business_type="automotive",
            location="Nairobi",
            target_goal="Increase qualified organic leads",
            primary_service="used car dealership",
        )
        context_snapshot = SEOContextSnapshot.objects.create(
            project=project,
            profile=profile,
            source_audit_run=audit_run,
            output_json={"context": {}, "benchmark_summary": {}},
        )
        opportunity_snapshot = SEOOpportunitySnapshot.objects.create(
            project=project,
            profile=profile,
            source_audit_run=audit_run,
            source_context_snapshot=context_snapshot,
            output_json={
                "execution_queue": [
                    {
                        "title": "Upgrade FAQ coverage",
                        "page_type": "faq",
                        "target_keyword": "used car dealership Nairobi faq",
                        "keywords": ["used car dealership Nairobi faq"],
                        "target_urls": ["https://example.com/faq/"],
                        "action_steps": ["Expand FAQ coverage."],
                        "priority_score": 91,
                        "deliverable": "Improve the current FAQ pages",
                        "where_to_apply": ["https://example.com/faq/"],
                        "edit_targets": [{"url": "https://example.com/faq/", "changes": ["Expand FAQ coverage"]}],
                    }
                ]
            },
        )
        campaign = sync_project_seo_campaigns(
            project,
            context_snapshot=context_snapshot,
            opportunity_snapshot=opportunity_snapshot,
        )[0]
        campaign.status = SEOCampaign.Status.COMPLETED
        campaign.metadata = {
            **(campaign.metadata or {}),
            "completed_at": (timezone.now() - timedelta(hours=1)).isoformat(),
        }
        campaign.save(update_fields=["status", "metadata", "updated_at"])
        task = ContentEditorialTask.objects.create(
            project=project,
            source_seo_snapshot=context_snapshot,
            source_seo_opportunity_snapshot=opportunity_snapshot,
            brief_key=campaign.campaign_key,
            title="FAQ brief",
            output_type=GeneratedContent.OutputType.ARTICLE,
            priority_score=90,
            brief_json={"primary_keyword": "used car dealership Nairobi faq"},
        )
        draft = GeneratedContent.objects.create(
            project=project,
            source_audit_run=audit_run,
            source_seo_snapshot=context_snapshot,
            source_seo_opportunity_snapshot=opportunity_snapshot,
            source_editorial_task=task,
            output_type=GeneratedContent.OutputType.ARTICLE,
            title="FAQ draft",
            target_keywords=["used car dealership Nairobi faq"],
            body="FAQ body",
            cta="CTA",
        )
        BacklinkProspect.objects.create(
            project=project,
            domain="example.org",
            homepage_url="https://example.org/",
            prospect_url="https://example.org/resources/faq/",
            title="FAQ resource",
            target_asset_title="FAQ asset",
            target_asset_type="faq",
            target_asset_url="https://example.com/faq/",
            suggested_anchor_text="used car dealership Nairobi faq",
        )

        campaigns = sync_project_campaign_chain(project)
        items = build_campaign_workspace_items(project, campaigns=campaigns)

        task.refresh_from_db()
        draft.refresh_from_db()
        campaign.refresh_from_db()
        prospect = BacklinkProspect.objects.get(project=project)
        self.assertEqual(task.seo_campaign, campaign)
        self.assertEqual(draft.source_seo_campaign, campaign)
        self.assertEqual(prospect.seo_campaign, campaign)
        self.assertEqual(campaign.validation_status, SEOCampaign.ValidationStatus.VALIDATED)
        self.assertEqual(campaign.latest_validation_audit_run, audit_run)
        self.assertEqual(campaign.metadata["chain_summary"]["backlink_prospect_count"], 1)
        self.assertEqual(items[0]["latest_draft"], draft)


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
        self.assertContains(response, "Evidence confidence")
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

    def test_workspace_seo_uses_selected_project(self):
        second_request = AuditRequest.objects.create(
            company_name="Second Project",
            email="seo@example.com",
            website="https://second-example.com",
        )
        second_run = AuditRun.objects.create(
            audit_request=second_request,
            normalized_domain="second-example.com",
            start_url="https://second-example.com/",
            overall_score=69,
            status=AuditRun.Status.COMPLETED,
            summary={},
        )
        second_project = ClientProject.objects.create(
            owner=self.user,
            audit_request=second_request,
            latest_audit_run=second_run,
            name="Second Project",
            website="https://second-example.com",
            normalized_domain="second-example.com",
            contact_email="seo@example.com",
            latest_score=69,
            location="Mombasa, Kenya",
            target_goal="Increase bookings",
            primary_service="Airport transfers",
        )
        SEOProjectProfile.objects.create(
            project=second_project,
            business_type="local_service",
            location="Mombasa, Kenya",
            target_goal="Increase bookings",
            primary_service="Airport transfers",
        )
        self.client.force_login(self.user)
        session = self.client.session
        session["active_workspace_project_id"] = second_project.pk
        session.save()

        response = self.client.get(reverse("seo:workspace-seo"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Second Project")
        self.assertEqual(response.context["project"].pk, second_project.pk)

    def test_workspace_seo_get_prefills_from_project_onboarding_fields(self):
        self.project.business_type = "automotive"
        self.project.location = "Nairobi, Kenya"
        self.project.target_goal = "Increase qualified leads"
        self.project.primary_service = "Used car sales"
        self.project.save(
            update_fields=["business_type", "location", "target_goal", "primary_service", "updated_at"]
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("seo:workspace-seo"))

        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertEqual(form.initial["business_type"], "automotive")
        self.assertEqual(form.initial["location"], "Nairobi, Kenya")
        self.assertEqual(form.initial["target_goal"], "Increase qualified leads")
        self.assertEqual(form.initial["primary_service"], "Used car sales")

    def test_workspace_seo_renders_competitor_trace(self):
        profile = SEOProjectProfile.objects.create(
            project=self.project,
            business_type="automotive",
            location="Nairobi",
            target_goal="Increase qualified organic leads",
            primary_service="used car dealership",
        )
        SEOContextSnapshot.objects.create(
            project=self.project,
            profile=profile,
            source_audit_run=self.audit_run,
            output_json={
                "context": {
                    "industry_label": "Automotive",
                    "location": "Nairobi",
                    "target_goal": "Increase qualified organic leads",
                    "goal_focus": "commercial and local intent queries",
                },
                "benchmark_summary": {"available_competitors": 1, "average_relevance": 8.6},
                "competitor_trace": [
                    {
                        "competitor_id": 99,
                        "domain": "competitor.com",
                        "url": "https://competitor.com/",
                        "source_label": "SERP Discovery",
                        "final_decision_label": "Suppressed",
                        "included": False,
                        "review_decision": "suppressed",
                        "review_label": "Suppressed",
                        "review_note": "Wrong location",
                        "fit": {
                            "best_page_score": 3,
                            "matching_pages": 0,
                            "reason": "Low topic and local relevance for the declared business niche.",
                            "match_signals": ["topic:cars"],
                            "penalty_signals": ["foreign_location_conflict"],
                        },
                        "queries": ["used car dealership Nairobi"],
                        "average_relevance": 4.2,
                        "page_count": 2,
                        "sample_titles": ["Used Cars Austin"],
                    }
                ],
                "competitors": [],
            },
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("seo:workspace-seo"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Benchmark Decision Trace")
        self.assertContains(response, "competitor.com")
        self.assertContains(response, "Wrong location")
        self.assertContains(response, "Page-to-Page Comparison")

    def test_workspace_seo_renders_history_sections(self):
        profile = SEOProjectProfile.objects.create(
            project=self.project,
            business_type="automotive",
            location="Nairobi",
            target_goal="Increase qualified organic leads",
            primary_service="used car dealership",
        )
        SEOContextSnapshot.objects.create(
            project=self.project,
            profile=profile,
            source_audit_run=self.audit_run,
            output_json={
                "context": {
                    "industry_label": "Automotive",
                    "location": "Nairobi",
                    "target_goal": "Increase qualified organic leads",
                    "goal_focus": "commercial and local intent queries",
                },
                "benchmark_summary": {
                    "available_competitors": 1,
                    "included_competitors": 1,
                    "filtered_out_competitors": 1,
                    "average_relevance": 8.1,
                },
                "discovery": {"queries": ["used car dealership Nairobi"]},
                "competitor_trace": [
                    {
                        "competitor_id": 11,
                        "domain": "competitor.com",
                        "url": "https://competitor.com/",
                        "source_label": "SERP Discovery",
                        "final_decision_label": "Accepted",
                        "included": True,
                        "review_decision": "auto",
                        "review_label": "Automatic",
                        "review_note": "",
                        "fit": {
                            "best_page_score": 8,
                            "matching_pages": 2,
                            "reason": "2 page(s) matched the declared niche and location.",
                            "match_signals": ["topic:cars"],
                            "penalty_signals": [],
                        },
                        "queries": ["used car dealership Nairobi"],
                        "average_relevance": 8.1,
                        "page_count": 3,
                        "sample_titles": ["Used Cars Nairobi"],
                    }
                ],
                "competitor_patterns": [],
                "page_comparisons": [],
                "competitors": [],
            },
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("seo:workspace-seo"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "SERP Evidence History")
        self.assertContains(response, "Competitor Trend Watch")
        self.assertContains(response, "competitor.com")

    def test_workspace_seo_campaign_update_persists_status_due_date_and_owner(self):
        campaign = SEOCampaign.objects.create(
            project=self.project,
            campaign_key="faq-used-car-dealership-nairobi-faq",
            title="Upgrade FAQ coverage",
            page_type="faq",
            target_keyword="used car dealership Nairobi faq",
            related_page_urls=["https://example.com/faq/"],
            success_criteria=["Re-run SEO refresh and audit validation after implementation."],
            priority_score=88,
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("seo:workspace-seo-campaign-update", args=[campaign.pk]),
            {
                "status": SEOCampaign.Status.IN_PROGRESS,
                "due_date": "2026-04-15",
                "note": "FAQ rewrite in progress",
                "assign_to_me": "1",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("seo:workspace-seo"))
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, SEOCampaign.Status.IN_PROGRESS)
        self.assertEqual(str(campaign.due_date), "2026-04-15")
        self.assertEqual(campaign.owner, self.user)
        self.assertEqual(campaign.metadata.get("note"), "FAQ rewrite in progress")

    def test_workspace_seo_view_renders_campaign_chain_context(self):
        profile = SEOProjectProfile.objects.create(
            project=self.project,
            business_type="automotive",
            location="Nairobi",
            target_goal="Increase qualified organic leads",
            primary_service="used car dealership",
            target_audience="price-sensitive car buyers",
        )
        context_snapshot = SEOContextSnapshot.objects.create(
            project=self.project,
            profile=profile,
            source_audit_run=self.audit_run,
            output_json={
                "context": {"project": "Northwind"},
                "benchmark_summary": {},
                "competitor_trace": [],
                "competitor_patterns": [],
                "page_comparisons": [],
                "competitors": [],
                "discovery": {},
                "audit_snapshot": {},
                "site_structure": {},
                "keyword_clusters": {},
                "recommendations": [],
            },
        )
        opportunity_snapshot = SEOOpportunitySnapshot.objects.create(
            project=self.project,
            profile=profile,
            source_audit_run=self.audit_run,
            source_context_snapshot=context_snapshot,
            output_json={
                "execution_queue": [],
                "value_summary": {},
                "keyword_opportunities": [],
                "page_map": [],
            },
        )
        campaign = SEOCampaign.objects.create(
            project=self.project,
            source_context_snapshot=context_snapshot,
            source_opportunity_snapshot=opportunity_snapshot,
            campaign_key="faq-used-car-dealership-nairobi-faq",
            title="Upgrade FAQ coverage",
            page_type="faq",
            target_keyword="used car dealership Nairobi faq",
            related_page_urls=["https://example.com/faq/"],
            success_criteria=["Re-run the audit after publishing the changes."],
            status=SEOCampaign.Status.IN_PROGRESS,
        )
        task = ContentEditorialTask.objects.create(
            project=self.project,
            source_seo_snapshot=context_snapshot,
            source_seo_opportunity_snapshot=opportunity_snapshot,
            seo_campaign=campaign,
            brief_key=campaign.campaign_key,
            title="FAQ brief",
            output_type=GeneratedContent.OutputType.ARTICLE,
            priority_score=80,
            brief_json={"primary_keyword": "used car dealership Nairobi faq"},
        )
        draft = GeneratedContent.objects.create(
            project=self.project,
            source_audit_run=self.audit_run,
            source_seo_snapshot=context_snapshot,
            source_seo_opportunity_snapshot=opportunity_snapshot,
            source_seo_campaign=campaign,
            source_editorial_task=task,
            output_type=GeneratedContent.OutputType.ARTICLE,
            title="FAQ draft",
            target_keywords=["used car dealership Nairobi faq"],
            body="FAQ body",
            cta="CTA",
        )
        task.latest_generated_content = draft
        task.save(update_fields=["latest_generated_content", "updated_at"])
        BacklinkProspect.objects.create(
            project=self.project,
            seo_campaign=campaign,
            domain="example.org",
            homepage_url="https://example.org/",
            prospect_url="https://example.org/resources/faq/",
            title="FAQ resource",
            target_asset_title="FAQ asset",
            target_asset_type="faq",
            target_asset_url="https://example.com/faq/",
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("seo:workspace-seo"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Campaigns Advanced")
        self.assertContains(response, "Editorial brief")
        self.assertContains(response, "Open linked draft")
        self.assertContains(response, "Outreach chain")

    def test_workspace_seo_export_json_returns_stakeholder_payload(self):
        profile = SEOProjectProfile.objects.create(
            project=self.project,
            business_type="automotive",
            location="Nairobi",
            target_goal="Increase qualified organic leads",
            primary_service="used car dealership",
            target_audience="price-sensitive car buyers",
        )
        context_snapshot = SEOContextSnapshot.objects.create(
            project=self.project,
            profile=profile,
            source_audit_run=self.audit_run,
            output_json={
                "context": {"industry_label": "Automotive", "location": "Nairobi"},
                "benchmark_summary": {"available_competitors": 2, "average_relevance": 8.4},
                "competitor_trace": [],
                "competitor_patterns": [],
                "page_comparisons": [],
                "competitors": [],
                "discovery": {"queries": ["used car dealership Nairobi"]},
                "audit_snapshot": {},
                "site_structure": {},
                "keyword_clusters": {},
                "recommendations": [],
            },
        )
        opportunity_snapshot = SEOOpportunitySnapshot.objects.create(
            project=self.project,
            profile=profile,
            source_audit_run=self.audit_run,
            source_context_snapshot=context_snapshot,
            output_json={
                "value_summary": {"execution_items": 1},
                "keyword_opportunities": [{"keyword": "used car dealership Nairobi"}],
                "page_map": [],
                "execution_queue": [{"title": "Upgrade FAQ coverage"}],
            },
        )
        SEOCampaign.objects.create(
            project=self.project,
            source_context_snapshot=context_snapshot,
            source_opportunity_snapshot=opportunity_snapshot,
            campaign_key="faq-used-car-dealership-nairobi-faq",
            title="Upgrade FAQ coverage",
            page_type="faq",
            target_keyword="used car dealership Nairobi faq",
            related_page_urls=["https://example.com/faq/"],
            success_criteria=["Re-run the audit after publishing the changes."],
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("seo:workspace-seo-export-json"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["project"]["domain"], "example.com")
        self.assertEqual(payload["benchmark_summary"]["available_competitors"], 2)
        self.assertEqual(payload["campaigns"][0]["title"], "Upgrade FAQ coverage")

    @override_settings(AUDIT_TIER_ENFORCEMENT=True)
    def test_workspace_seo_exports_and_share_spend_credits_once_per_artifact(self):
        authority_plan = WorkspacePlan.objects.get(slug="authority")
        WorkspaceSubscription.objects.create(
            user=self.user,
            plan=authority_plan,
            status=WorkspaceSubscription.Status.ACTIVE,
        )
        profile = SEOProjectProfile.objects.create(
            project=self.project,
            business_type="automotive",
            location="Nairobi",
            target_goal="Increase qualified organic leads",
            primary_service="used car dealership",
            target_audience="price-sensitive car buyers",
        )
        context_snapshot = SEOContextSnapshot.objects.create(
            project=self.project,
            profile=profile,
            source_audit_run=self.audit_run,
            output_json={
                "context": {"industry_label": "Automotive", "location": "Nairobi"},
                "benchmark_summary": {"available_competitors": 2, "average_relevance": 8.4},
                "competitor_trace": [],
                "competitor_patterns": [],
                "page_comparisons": [],
                "competitors": [],
                "discovery": {"queries": ["used car dealership Nairobi"]},
                "audit_snapshot": {},
                "site_structure": {},
                "keyword_clusters": {},
                "recommendations": [],
            },
        )
        opportunity_snapshot = SEOOpportunitySnapshot.objects.create(
            project=self.project,
            profile=profile,
            source_audit_run=self.audit_run,
            source_context_snapshot=context_snapshot,
            output_json={
                "value_summary": {"execution_items": 1},
                "keyword_opportunities": [{"keyword": "used car dealership Nairobi"}],
                "page_map": [],
                "execution_queue": [{"title": "Upgrade FAQ coverage"}],
            },
        )
        self.client.force_login(self.user)

        json_response = self.client.get(reverse("seo:workspace-seo-export-json"))
        repeat_json_response = self.client.get(reverse("seo:workspace-seo-export-json"))
        pdf_response = self.client.get(reverse("seo:workspace-seo-report-pdf"))
        share_response = self.client.post(reverse("seo:workspace-seo-share-create"))
        repeat_share_response = self.client.post(reverse("seo:workspace-seo-share-create"))

        self.assertEqual(json_response.status_code, 200)
        self.assertEqual(repeat_json_response.status_code, 200)
        self.assertEqual(pdf_response.status_code, 200)
        self.assertEqual(share_response.status_code, 302)
        self.assertEqual(repeat_share_response.status_code, 302)
        self.assertEqual(
            WorkspaceCreditLedger.objects.filter(user=self.user, category=WorkspaceCreditLedger.Category.EXPORT).count(),
            2,
        )
        self.assertEqual(
            WorkspaceCreditLedger.objects.filter(user=self.user, category=WorkspaceCreditLedger.Category.SHARE).count(),
            1,
        )
        self.assertEqual(
            UsageRecord.objects.get(user=self.user, metric=UsageRecord.Metric.EXPORT).quantity,
            2,
        )

    def test_workspace_seo_share_create_and_shared_report_render(self):
        profile = SEOProjectProfile.objects.create(
            project=self.project,
            business_type="automotive",
            location="Nairobi",
            target_goal="Increase qualified organic leads",
            primary_service="used car dealership",
            target_audience="price-sensitive car buyers",
        )
        context_snapshot = SEOContextSnapshot.objects.create(
            project=self.project,
            profile=profile,
            source_audit_run=self.audit_run,
            output_json={
                "context": {"industry_label": "Automotive", "location": "Nairobi"},
                "benchmark_summary": {"available_competitors": 2, "average_relevance": 8.4},
                "competitor_trace": [],
                "competitor_patterns": [],
                "page_comparisons": [],
                "competitors": [],
                "discovery": {"queries": ["used car dealership Nairobi"]},
                "audit_snapshot": {},
                "site_structure": {},
                "keyword_clusters": {},
                "recommendations": [],
            },
        )
        opportunity_snapshot = SEOOpportunitySnapshot.objects.create(
            project=self.project,
            profile=profile,
            source_audit_run=self.audit_run,
            source_context_snapshot=context_snapshot,
            output_json={
                "value_summary": {"execution_items": 1},
                "keyword_opportunities": [{"keyword": "used car dealership Nairobi"}],
                "page_map": [],
                "execution_queue": [{"title": "Upgrade FAQ coverage"}],
            },
        )
        self.client.force_login(self.user)

        response = self.client.post(reverse("seo:workspace-seo-share-create"))

        self.assertEqual(response.status_code, 302)
        share_link = SEOShareLink.objects.get(project=self.project)
        shared_response = self.client.get(reverse("seo:shared-seo-report", args=[share_link.token]))
        self.assertEqual(shared_response.status_code, 200)
        self.assertContains(shared_response, "Shared SEO Report")
        self.assertContains(shared_response, 'content="noindex, nofollow"', html=False)

        pdf_response = self.client.get(reverse("seo:shared-seo-report-pdf", args=[share_link.token]))
        self.assertEqual(pdf_response.status_code, 200)
        self.assertEqual(pdf_response["Content-Type"], "application/pdf")

    def test_workspace_seo_competitor_review_updates_metadata(self):
        competitor = SEOCompetitor.objects.create(
            project=self.project,
            homepage_url="https://competitor.com/",
            normalized_domain="competitor.com",
            label="competitor.com",
            source=SEOCompetitor.Source.SERP,
            is_active=True,
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("seo:workspace-seo-competitor-review", args=[competitor.pk]),
            {"decision": "pinned", "note": "Exact Nairobi market competitor"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("seo:workspace-seo"))
        competitor.refresh_from_db()
        self.assertEqual(competitor.metadata["review"]["decision"], "pinned")
        self.assertEqual(competitor.metadata["review"]["note"], "Exact Nairobi market competitor")

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
    def setUp(self):
        cache.clear()

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

    def test_build_discovery_queries_prefers_venue_intent_for_event_focused_hospitality(self):
        profile = SEOProjectProfile(
            business_type="hotel",
            location="Machakos, Kenya",
            target_goal="Increase quality leads",
            primary_service="events gardens",
            target_audience="people looking for events gardens in machakos",
        )

        queries = build_discovery_queries(profile)

        self.assertIn("events gardens Machakos, Kenya", queries)
        self.assertIn("event venue Machakos, Kenya", queries)
        self.assertIn("wedding venue Machakos, Kenya", queries)
        self.assertNotIn("rooms in Machakos, Kenya", queries)

    def test_build_discovery_routes_varies_by_business_type(self):
        profile = SEOProjectProfile(
            business_type="local_service",
            location="Nairobi",
            target_goal="Increase qualified leads",
            primary_service="event venue",
            target_audience="event planners",
        )

        routes = build_discovery_routes(profile)
        families = [item["family_key"] for item in routes]

        self.assertIn("benchmark_competitors", families)
        self.assertIn("citation_sources", families)
        self.assertIn("market_surfaces", families)
        self.assertIn("backlink_prospects", families)
        citation_route = next(item for item in routes if item["family_key"] == "citation_sources")
        self.assertTrue(any("directory" in query or "reviews" in query for query in citation_route["queries"]))

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
        def fake_serp_payload(query, location=""):
            if any(token in query for token in ("directory", "reviews", "listing", "guide", "resources", "association")):
                return {"organic_results": [], "local_results": []}
            if "best" in query:
                return {
                    "organic_results": [
                        {
                            "position": 3,
                            "title": "Best Used Cars Nairobi",
                            "link": "https://competitor-a.com/pricing/",
                            "snippet": "Pricing for used cars",
                        }
                    ],
                    "local_results": [],
                }
            return {
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
            }

        mocked_serp_fetch.side_effect = fake_serp_payload

        discovery = discover_serp_competitors(project, profile)

        self.assertTrue(discovery["enabled"])
        self.assertGreaterEqual(len(discovery["queries"]), 2)
        benchmark_route = next(item for item in discovery["routing_policy"]["routes"] if item["family_key"] == "benchmark_competitors")
        self.assertEqual(len(benchmark_route["queries"]), 2)
        self.assertEqual(discovery["competitors"][0]["normalized_domain"], "competitor-a.com")
        self.assertEqual(discovery["competitors"][0]["query_count"], 2)
        self.assertEqual(discovery["competitors"][0]["best_position"], 1)
        self.assertTrue(discovery["competitors"][0]["average_relevance"] >= 4)

    @override_settings(
        SERP_DISCOVERY_ENABLED=True,
        SERP_DISCOVERY_PROVIDER="serpapi",
        SERPAPI_API_KEY="test-key",
        SERP_DISCOVERY_QUERY_LIMIT=1,
        SERP_DISCOVERY_RESULTS_PER_QUERY=6,
    )
    @patch("apps.seo.discovery.fetch_serpapi_results")
    def test_discover_serp_competitors_buckets_non_peer_surfaces(self, mocked_serp_fetch):
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
            business_type="local_service",
            location="Nairobi",
            target_goal="Increase qualified leads",
            primary_service="event venue",
            target_audience="event planners",
        )
        mocked_serp_fetch.return_value = {
            "organic_results": [
                {
                    "position": 1,
                    "title": "Premier Event Venue Nairobi",
                    "link": "https://venue-example.co.ke/",
                    "snippet": "Event venue in Nairobi for weddings and conferences.",
                },
                {
                    "position": 2,
                    "title": "Nairobi venues on Tripadvisor",
                    "link": "https://www.tripadvisor.com/Attractions-g294207-Activities-Nairobi.html",
                    "snippet": "Compare venues and hotels in Nairobi.",
                },
                {
                    "position": 3,
                    "title": "Event venues near you | Yelp",
                    "link": "https://www.yelp.com/search?find_desc=Event+Venue&find_loc=Nairobi",
                    "snippet": "Local business listings and reviews.",
                },
                {
                    "position": 4,
                    "title": "Association guide to event venues in Nairobi",
                    "link": "https://eventsassociation.or.ke/guides/nairobi-event-venues/",
                    "snippet": "Guide to planning venues and vendors in Nairobi.",
                },
            ],
            "local_results": [],
        }

        discovery = discover_serp_competitors(project, profile)

        self.assertEqual(discovery["competitors"][0]["normalized_domain"], "venue-example.co.ke")
        self.assertEqual(discovery["market_surfaces"][0]["normalized_domain"], "www.tripadvisor.com")
        self.assertEqual(discovery["citation_sources"][0]["normalized_domain"], "www.yelp.com")
        self.assertEqual(discovery["backlink_prospects"][0]["normalized_domain"], "eventsassociation.or.ke")
        self.assertEqual(discovery["routing_policy"]["business_type"], "local_service")
        self.assertIn("market_surfaces", discovery["routing_policy"]["source_families"])
        self.assertTrue(any(route["family_key"] == "market_surfaces" for route in discovery["routing_policy"]["routes"]))
        self.assertIn("market_surfaces", discovery["market_surfaces"][0]["source_families"])

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
        self.assertIn("competitor-c.com", domains)

    @override_settings(
        SERP_DISCOVERY_ENABLED=True,
        SERP_DISCOVERY_PROVIDER="serpapi",
        SERPAPI_API_KEY="test-key",
        SERP_DISCOVERY_QUERY_LIMIT=1,
        SERP_DISCOVERY_RESULTS_PER_QUERY=5,
    )
    @patch("apps.seo.discovery.fetch_serpapi_results")
    def test_discover_serp_competitors_keeps_local_peer_sites_for_local_service_queries(self, mocked_serp_fetch):
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
            business_type="local_service",
            location="Machakos, Kenya",
            target_goal="Increase qualified leads",
            primary_service="events gardens",
            target_audience="people looking for events gardens in machakos",
        )
        mocked_serp_fetch.return_value = {
            "organic_results": [],
            "local_results": {
                "places": [
                    {
                        "position": 1,
                        "title": "Zamar Springs Gardens",
                        "website": "https://zamar-example.co.ke/",
                        "description": "Venue for weddings and conferences in Machakos.",
                        "address": "Machakos, Kenya",
                        "type": "Event venue",
                    },
                    {
                        "position": 2,
                        "title": "Kai Safari Gardens",
                        "website": "https://kai-example.co.ke/",
                        "description": "Gardens and event space in Machakos.",
                        "address": "Machakos, Kenya",
                        "type": "Wedding venue",
                    },
                ]
            },
        }

        discovery = discover_serp_competitors(project, profile)

        domains = [item["normalized_domain"] for item in discovery["competitors"]]
        self.assertIn("zamar-example.co.ke", domains)
        self.assertIn("kai-example.co.ke", domains)

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
    @patch("apps.seo.discovery.fetch_serpapi_results")
    def test_discover_serp_competitors_filters_hospitality_aggregators_for_event_venue_profiles(self, mocked_serp_fetch):
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
            business_type="hotel",
            location="Machakos, Kenya",
            target_goal="Increase quality leads",
            primary_service="events gardens",
            target_audience="people looking for events gardens in machakos",
        )
        mocked_serp_fetch.return_value = {
            "organic_results": [
                {
                    "position": 1,
                    "title": "Zamar Springs Gardens | Event Venue in Machakos",
                    "link": "https://zamar-example.co.ke/events-gardens/",
                    "snippet": "Event venue and gardens in Machakos for weddings and conferences.",
                },
                {
                    "position": 2,
                    "title": "Hotels in Machakos - search by Trivago",
                    "link": "https://www.trivago.com/en-KE/lm/hotels-machakos-kenya",
                    "snippet": "Compare hotel prices in Machakos.",
                },
                {
                    "position": 3,
                    "title": "Machakos Hotels | KAYAK",
                    "link": "https://www.kayak.com/Machakos-Hotels.12345.hotel.ksp",
                    "snippet": "Search and compare Machakos hotels.",
                },
            ],
            "local_results": [],
        }

        discovery = discover_serp_competitors(project, profile)

        domains = [item["normalized_domain"] for item in discovery["competitors"]]
        self.assertIn("zamar-example.co.ke", domains)
        self.assertNotIn("www.trivago.com", domains)
        self.assertNotIn("www.kayak.com", domains)

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

    @override_settings(
        SERP_DISCOVERY_ENABLED=True,
        SERP_DISCOVERY_PROVIDER="serpapi",
        SERPAPI_API_KEY="test-key",
        SERP_PROVIDER_COOLDOWN_SECONDS=60,
    )
    @patch("apps.seo.discovery.fetch_serpapi_results")
    def test_fetch_search_results_disables_serpapi_after_429(self, mocked_serpapi):
        cache.clear()
        response = requests.Response()
        response.status_code = 429
        error = requests.HTTPError("429 Client Error: Too Many Requests")
        error.response = response
        mocked_serpapi.side_effect = error

        runtime_state = {"disabled_providers": set()}
        first = fetch_search_results("events gardens Machakos, Kenya", location="Machakos, Kenya", runtime_state=runtime_state)
        second = fetch_search_results("hotel Machakos, Kenya", location="Machakos, Kenya", runtime_state=runtime_state)

        self.assertEqual(mocked_serpapi.call_count, 1)
        self.assertEqual(first["errors"][0]["provider"], "serpapi")
        self.assertTrue(second["providers_exhausted"])
        self.assertIn("cooled down", second["errors"][0]["message"])

    @override_settings(
        SERP_DISCOVERY_ENABLED=True,
        SERP_DISCOVERY_PROVIDER="serpapi,duckduckgo",
        SERPAPI_API_KEY="test-key",
        SERP_DISCOVERY_QUERY_LIMIT=4,
        SERP_PROVIDER_COOLDOWN_SECONDS=60,
        SERP_DUCKDUCKGO_COOLDOWN_SECONDS=60,
    )
    @patch("apps.seo.discovery.fetch_duckduckgo_results", side_effect=requests.Timeout("duckduckgo timeout"))
    @patch("apps.seo.discovery.fetch_serpapi_results")
    def test_discover_serp_competitors_stops_repeating_provider_failures(self, mocked_serpapi, mocked_duckduckgo):
        cache.clear()
        response = requests.Response()
        response.status_code = 429
        error = requests.HTTPError("429 Client Error: Too Many Requests")
        error.response = response
        mocked_serpapi.side_effect = error

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
            business_type="hotel",
            location="Machakos, Kenya",
            primary_service="events gardens",
            target_goal="Increase bookings",
            target_audience="travellers and event planners",
        )

        discovery = discover_serp_competitors(project, profile)

        self.assertEqual(mocked_serpapi.call_count, 1)
        self.assertEqual(mocked_duckduckgo.call_count, 1)
        self.assertEqual(discovery["competitors"], [])
        self.assertLessEqual(len(discovery["errors"]), 4)
