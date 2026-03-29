from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.leads.models import AuditRequest, ClientProject
from apps.seo.models import SEOContextSnapshot, SEOOpportunitySnapshot, SEOProjectProfile
from apps.tools.models import AuditRun

from .models import Article, ContentEditorialTask, GeneratedContent, Service
from .services import (
    apply_generated_content,
    build_seo_content_briefs,
    create_generated_content,
    generate_content_payload,
    sync_project_editorial_tasks,
)


class GeneratedContentServiceTests(TestCase):
    def test_generate_content_payload_uses_audit_context_and_validation(self):
        audit_request = AuditRequest.objects.create(
            company_name="Northwind",
            email="ops@example.com",
            website="https://example.com",
        )
        audit_run = AuditRun.objects.create(
            audit_request=audit_request,
            normalized_domain="example.com",
            start_url="https://example.com/",
            overall_score=68,
            technical_score=61,
            on_page_score=59,
            content_score=72,
            aeo_score=64,
            summary={
                "recommendations": [
                    {"title": "Fix missing title tags"},
                    {"title": "Expand thin service copy"},
                ],
                "score_breakdown": {
                    "technical": {"label": "Technical", "score": 61},
                    "on_page": {"label": "On-page", "score": 59},
                    "content": {"label": "Content", "score": 72},
                },
                "product_modules": [{"title": "Content Intelligence"}],
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

        context, payload = generate_content_payload(
            project=project,
            output_type=GeneratedContent.OutputType.SERVICE_PAGE,
            input_data={
                "business_type": "auto dealership",
                "location": "Nairobi",
                "target_audience": "buyers comparing used vehicles",
                "page_goal": "book a consultation",
                "offer_summary": "used car sourcing support",
                "target_keywords": ["used car dealership Nairobi", "buy second hand cars Nairobi"],
                "search_intent": "commercial",
            },
        )

        self.assertEqual(context["domain"], "example.com")
        self.assertIn("Fix missing title tags", context["improvement_points"])
        self.assertEqual(payload["keywords_used"][0], "used car dealership Nairobi")
        self.assertTrue(payload["validation"]["passes"])
        self.assertEqual(payload["schema_json"]["@type"], "FAQPage")

    def test_build_seo_content_briefs_uses_latest_seo_queue(self):
        audit_request = AuditRequest.objects.create(
            company_name="Northwind",
            email="ops@example.com",
            website="https://example.com",
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
            target_goal="Increase qualified leads",
            primary_service="used car dealership",
            target_audience="price-sensitive car buyers",
        )
        seo_snapshot = SEOContextSnapshot.objects.create(
            project=project,
            profile=profile,
            source_audit_run=audit_run,
            output_json={
                "context": {
                    "business_type": "automotive",
                    "location": "Nairobi",
                    "target_goal": "Increase qualified leads",
                    "primary_service": "used car dealership",
                    "target_audience": "price-sensitive car buyers",
                },
                "site_structure": {
                    "pages": [
                        {"url": "https://example.com/", "title": "Home", "page_type": "home"},
                        {"url": "https://example.com/about/", "title": "About", "page_type": "about"},
                    ]
                },
            },
        )
        SEOOpportunitySnapshot.objects.create(
            project=project,
            profile=profile,
            source_audit_run=audit_run,
            source_context_snapshot=seo_snapshot,
            output_json={
                "keyword_opportunities": [
                    {
                        "keyword": "used car dealership Nairobi",
                        "target_page_type": "service",
                        "support_terms": ["buy used cars Nairobi"],
                        "intent": "Service Page",
                    }
                ],
                "page_map": [
                    {
                        "page_type": "service",
                        "page_type_label": "Service",
                        "status": "missing",
                        "target_keyword": "used car dealership Nairobi",
                        "reason": "Competitors have dedicated service pages and this site does not.",
                        "action": "Create a dedicated service page.",
                        "target_urls": [],
                        "competitor_evidence": [{"title": "Used Cars Nairobi", "url": "https://competitor.com/service/"}],
                    }
                ],
            },
        )

        briefs = build_seo_content_briefs(project)

        self.assertEqual(len(briefs), 1)
        self.assertEqual(briefs[0]["primary_keyword"], "used car dealership Nairobi")
        self.assertTrue(briefs[0]["title_options"])
        self.assertTrue(briefs[0]["outline_sections"])
        self.assertTrue(briefs[0]["faq_targets"])

    def test_sync_project_editorial_tasks_creates_and_updates_queue_items(self):
        audit_request = AuditRequest.objects.create(
            company_name="Northwind",
            email="ops@example.com",
            website="https://example.com",
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
            target_goal="Increase qualified leads",
            primary_service="used car dealership",
            target_audience="price-sensitive car buyers",
        )
        seo_snapshot = SEOContextSnapshot.objects.create(
            project=project,
            profile=profile,
            source_audit_run=audit_run,
            output_json={
                "context": {
                    "business_type": "automotive",
                    "location": "Nairobi",
                    "target_goal": "Increase qualified leads",
                    "primary_service": "used car dealership",
                    "target_audience": "price-sensitive car buyers",
                },
                "site_structure": {"pages": [{"url": "https://example.com/", "title": "Home", "page_type": "home"}]},
            },
        )
        SEOOpportunitySnapshot.objects.create(
            project=project,
            profile=profile,
            source_audit_run=audit_run,
            source_context_snapshot=seo_snapshot,
            output_json={
                "keyword_opportunities": [
                    {"keyword": "used car dealership Nairobi", "target_page_type": "service", "support_terms": ["buy used cars Nairobi"], "intent": "Service Page"}
                ],
                "page_map": [
                    {
                        "page_type": "service",
                        "page_type_label": "Service",
                        "status": "missing",
                        "priority_score": 91,
                        "target_keyword": "used car dealership Nairobi",
                        "reason": "Competitors have dedicated service pages and this site does not.",
                        "action": "Create a dedicated service page.",
                        "target_urls": [],
                        "competitor_evidence": [{"title": "Used Cars Nairobi", "url": "https://competitor.com/service/"}],
                    }
                ],
            },
        )

        tasks = sync_project_editorial_tasks(project)

        self.assertEqual(len(tasks), 1)
        task = ContentEditorialTask.objects.get(project=project)
        self.assertEqual(task.status, ContentEditorialTask.Status.QUEUED)
        self.assertEqual(task.priority_score, 91)

    @override_settings(
        CONTENT_REFINEMENT_PROVIDER="ollama",
        CONTENT_REFINEMENT_MODEL="llama3.1",
        CONTENT_REFINEMENT_ENABLED=True,
    )
    @patch(
        "apps.content.refinement._run_provider_prompt",
        return_value={
            "title_options": [
                "Best used car dealership in Nairobi",
                "Used car dealership Nairobi buying guide",
            ],
            "outline_sections": [
                {
                    "heading": "Buying criteria",
                    "instruction": "Show how price-sensitive buyers should compare stock quality, financing, and dealer trust signals.",
                }
            ],
            "faq_targets": [
                "What should buyers compare before choosing a used car dealership in Nairobi?",
                "How can buyers verify dealer trust signals in Nairobi?",
            ],
            "reason": "Competitors use dedicated commercial service pages with local buying criteria.",
            "action": "Create a service page that explains buying criteria, trust signals, and financing paths for Nairobi buyers.",
        },
    )
    def test_sync_project_editorial_tasks_applies_model_refinement_when_available(self, _provider_mock):
        audit_request = AuditRequest.objects.create(
            company_name="Northwind",
            email="ops@example.com",
            website="https://example.com",
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
            target_goal="Increase qualified leads",
            primary_service="used car dealership",
            target_audience="price-sensitive car buyers",
        )
        seo_snapshot = SEOContextSnapshot.objects.create(
            project=project,
            profile=profile,
            source_audit_run=audit_run,
            output_json={
                "context": {
                    "business_type": "automotive",
                    "location": "Nairobi",
                    "target_goal": "Increase qualified leads",
                    "primary_service": "used car dealership",
                    "target_audience": "price-sensitive car buyers",
                },
                "site_structure": {"pages": [{"url": "https://example.com/", "title": "Home", "page_type": "home"}]},
            },
        )
        SEOOpportunitySnapshot.objects.create(
            project=project,
            profile=profile,
            source_audit_run=audit_run,
            source_context_snapshot=seo_snapshot,
            output_json={
                "keyword_opportunities": [
                    {"keyword": "used car dealership Nairobi", "target_page_type": "service", "support_terms": ["buy used cars Nairobi"], "intent": "Service Page"}
                ],
                "page_map": [
                    {
                        "page_type": "service",
                        "page_type_label": "Service",
                        "status": "missing",
                        "priority_score": 91,
                        "target_keyword": "used car dealership Nairobi",
                        "reason": "Competitors have dedicated service pages and this site does not.",
                        "action": "Create a dedicated service page.",
                        "target_urls": [],
                        "competitor_evidence": [{"title": "Used Cars Nairobi", "url": "https://competitor.com/service/"}],
                    }
                ],
            },
        )

        sync_project_editorial_tasks(project)

        task = ContentEditorialTask.objects.get(project=project)
        self.assertTrue(task.metadata["brief_refinement"]["applied"])
        self.assertEqual(task.metadata["brief_refinement"]["provider"], "ollama")
        self.assertIn("Best used car dealership in Nairobi", task.brief_json["title_options"])

    @override_settings(
        CONTENT_REFINEMENT_PROVIDER="ollama",
        CONTENT_REFINEMENT_MODEL="llama3.1",
        CONTENT_REFINEMENT_ENABLED=True,
    )
    @patch(
        "apps.content.refinement._run_provider_prompt",
        return_value={
            "title": "Generic title",
            "meta_title": "Generic title",
            "meta_description": "Generic description",
            "content": "# Generic title\n\n## Section\nThis copy drops all keyword grounding and answer-first structure.",
            "faq_items": [{"question": "What now?", "answer": "Unknown."}],
            "cta": "Contact us",
        },
    )
    def test_generate_content_payload_falls_back_when_model_output_fails_validation(self, _provider_mock):
        audit_request = AuditRequest.objects.create(
            company_name="Northwind",
            email="ops@example.com",
            website="https://example.com",
        )
        audit_run = AuditRun.objects.create(
            audit_request=audit_request,
            normalized_domain="example.com",
            start_url="https://example.com/",
            overall_score=68,
            summary={
                "recommendations": [{"title": "Fix missing title tags"}],
                "score_breakdown": {"on_page": {"label": "On-page", "score": 59}},
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

        _, payload = generate_content_payload(
            project=project,
            output_type=GeneratedContent.OutputType.SERVICE_PAGE,
            input_data={
                "business_type": "auto dealership",
                "location": "Nairobi",
                "target_audience": "buyers comparing used vehicles",
                "page_goal": "book a consultation",
                "offer_summary": "used car sourcing support",
                "target_keywords": ["used car dealership Nairobi", "buy second hand cars Nairobi"],
                "search_intent": "commercial",
            },
        )

        self.assertFalse(payload["refinement"]["applied"])
        self.assertEqual(payload["refinement"]["fallback_reason"], "validation_failed")
        self.assertIn("used car dealership Nairobi", payload["content"])


class GeneratedContentViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="content@example.com",
            email="content@example.com",
            password="strongpass123",
        )
        audit_request = AuditRequest.objects.create(
            company_name="Northwind",
            email="content@example.com",
            website="https://example.com",
        )
        audit_run = AuditRun.objects.create(
            audit_request=audit_request,
            normalized_domain="example.com",
            start_url="https://example.com/",
            overall_score=77,
            summary={
                "recommendations": [{"title": "Tighten H1 coverage"}],
                "score_breakdown": {
                    "on_page": {"label": "On-page", "score": 63},
                },
            },
        )
        self.project = ClientProject.objects.create(
            owner=self.user,
            audit_request=audit_request,
            latest_audit_run=audit_run,
            name="Northwind",
            website="https://example.com",
            normalized_domain="example.com",
            contact_email="content@example.com",
            latest_score=77,
        )
        self.seo_profile = SEOProjectProfile.objects.create(
            project=self.project,
            business_type="automotive",
            location="Nairobi",
            target_goal="Increase qualified leads",
            primary_service="used car dealership",
            target_audience="buyers comparing used vehicles",
        )
        self.seo_snapshot = SEOContextSnapshot.objects.create(
            project=self.project,
            profile=self.seo_profile,
            source_audit_run=self.project.latest_audit_run,
            output_json={
                "context": {
                    "business_type": "automotive",
                    "location": "Nairobi",
                    "target_goal": "Increase qualified leads",
                    "primary_service": "used car dealership",
                    "target_audience": "buyers comparing used vehicles",
                },
                "site_structure": {
                    "pages": [
                        {"url": "https://example.com/", "title": "Home", "page_type": "home"},
                        {"url": "https://example.com/contact/", "title": "Contact", "page_type": "contact"},
                    ]
                },
            },
        )
        self.seo_opportunity_snapshot = SEOOpportunitySnapshot.objects.create(
            project=self.project,
            profile=self.seo_profile,
            source_audit_run=self.project.latest_audit_run,
            source_context_snapshot=self.seo_snapshot,
            output_json={
                "keyword_opportunities": [
                    {
                        "keyword": "used car dealership Nairobi",
                        "target_page_type": "service",
                        "support_terms": ["buy used cars Nairobi"],
                        "intent": "Service Page",
                    }
                ],
                "page_map": [
                    {
                        "page_type": "service",
                        "page_type_label": "Service",
                        "status": "missing",
                        "target_keyword": "used car dealership Nairobi",
                        "reason": "Competitors have dedicated service pages and this site does not.",
                        "action": "Create a dedicated service page.",
                        "target_urls": [],
                        "competitor_evidence": [{"title": "Used Cars Nairobi", "url": "https://competitor.com/service/"}],
                    }
                ],
            },
        )

    def test_workspace_content_view_renders(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("content:workspace-content"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Generate draft")
        self.assertContains(response, "Northwind")
        self.assertContains(response, "Editorial Queue")

    def test_workspace_content_create_persists_draft(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("content:workspace-content-generate"),
            {
                "output_type": GeneratedContent.OutputType.ARTICLE,
                "business_type": "auto dealership",
                "location": "Nairobi",
                "target_audience": "buyers comparing used vehicles",
                "page_goal": "book a consultation",
                "offer_summary": "used car sourcing support",
                "target_keywords": "used car dealership Nairobi, buy second hand cars Nairobi",
                "search_intent": "commercial",
            },
        )

        self.assertEqual(response.status_code, 302)
        draft = GeneratedContent.objects.get()
        self.assertEqual(draft.project, self.project)
        self.assertEqual(draft.created_by, self.user)
        self.assertEqual(draft.source_audit_run, self.project.latest_audit_run)
        self.assertIn("/workspace/content/", response["Location"])

    def test_workspace_content_generate_from_seo_brief(self):
        self.client.force_login(self.user)
        brief_key = build_seo_content_briefs(self.project)[0]["brief_key"]

        response = self.client.post(
            reverse("content:workspace-content-generate-from-seo"),
            {"brief_key": brief_key},
        )

        self.assertEqual(response.status_code, 302)
        draft = GeneratedContent.objects.latest("created_at")
        self.assertEqual(draft.source_seo_snapshot, self.seo_snapshot)
        self.assertEqual(draft.source_seo_opportunity_snapshot, self.seo_opportunity_snapshot)
        self.assertIsNotNone(draft.source_editorial_task)
        self.assertEqual(draft.source_editorial_task.status, ContentEditorialTask.Status.DRAFTED)
        self.assertTrue(draft.brief_json["title_options"])
        self.assertIn("used car dealership Nairobi", draft.body)

    def test_generated_content_detail_requires_owner(self):
        draft = create_generated_content(
            user=self.user,
            project=self.project,
            output_type=GeneratedContent.OutputType.ANSWER_BLOCK,
            input_data={
                "business_type": "auto dealership",
                "location": "Nairobi",
                "target_audience": "buyers comparing used vehicles",
                "page_goal": "book a consultation",
                "offer_summary": "used car sourcing support",
                "target_keywords": ["used car dealership Nairobi"],
                "search_intent": "commercial",
            },
        )
        other_user = get_user_model().objects.create_user(
            username="other@example.com",
            email="other@example.com",
            password="strongpass123",
        )
        self.client.force_login(other_user)

        response = self.client.get(reverse("content:workspace-content-detail", args=[draft.pk]))

        self.assertEqual(response.status_code, 404)

    def test_generated_content_update_saves_editor_changes(self):
        draft = create_generated_content(
            user=self.user,
            project=self.project,
            output_type=GeneratedContent.OutputType.ANSWER_BLOCK,
            input_data={
                "business_type": "auto dealership",
                "location": "Nairobi",
                "target_audience": "buyers comparing used vehicles",
                "page_goal": "book a consultation",
                "offer_summary": "used car sourcing support",
                "target_keywords": ["used car dealership Nairobi"],
                "search_intent": "commercial",
            },
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("content:workspace-content-update", args=[draft.pk]),
            {
                "title": "Updated draft title",
                "meta_title": "Updated meta title",
                "meta_description": "Updated meta description",
                "body": "auto dealership teams need a focused answer block.\n\nThis update is more specific.",
                "cta": "Review the implementation plan",
                "status": GeneratedContent.Status.REVIEWED,
            },
        )

        self.assertEqual(response.status_code, 302)
        draft.refresh_from_db()
        self.assertEqual(draft.title, "Updated draft title")
        self.assertEqual(draft.status, GeneratedContent.Status.REVIEWED)
        self.assertIn("Review the implementation plan", draft.output_json["cta"])

    def test_apply_generated_content_creates_article_or_service(self):
        article_draft = create_generated_content(
            user=self.user,
            project=self.project,
            output_type=GeneratedContent.OutputType.ARTICLE,
            input_data={
                "business_type": "auto dealership",
                "location": "Nairobi",
                "target_audience": "buyers comparing used vehicles",
                "page_goal": "book a consultation",
                "offer_summary": "used car sourcing support",
                "target_keywords": ["used car dealership Nairobi"],
                "search_intent": "commercial",
            },
        )
        service_draft = create_generated_content(
            user=self.user,
            project=self.project,
            output_type=GeneratedContent.OutputType.SERVICE_PAGE,
            input_data={
                "business_type": "auto dealership",
                "location": "Nairobi",
                "target_audience": "buyers comparing used vehicles",
                "page_goal": "book a consultation",
                "offer_summary": "used car sourcing support",
                "target_keywords": ["used car dealership Nairobi"],
                "search_intent": "commercial",
            },
        )

        apply_generated_content(article_draft)
        apply_generated_content(service_draft)

        article_draft.refresh_from_db()
        service_draft.refresh_from_db()
        self.assertEqual(article_draft.status, GeneratedContent.Status.APPLIED)
        self.assertIsInstance(article_draft.applied_article, Article)
        self.assertEqual(service_draft.status, GeneratedContent.Status.APPLIED)
        self.assertIsInstance(service_draft.applied_service, Service)

    def test_sync_editorial_queues_command_runs_for_projects_with_seo_profiles(self):
        call_command("sync_editorial_queues")
        self.assertTrue(ContentEditorialTask.objects.filter(project=self.project).exists())

    def test_generated_content_json_endpoint_returns_output_contract(self):
        draft = create_generated_content(
            user=self.user,
            project=self.project,
            output_type=GeneratedContent.OutputType.ARTICLE,
            input_data={
                "business_type": "auto dealership",
                "location": "Nairobi",
                "target_audience": "buyers comparing used vehicles",
                "page_goal": "book a consultation",
                "offer_summary": "used car sourcing support",
                "target_keywords": ["used car dealership Nairobi"],
                "search_intent": "commercial",
            },
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("content:workspace-content-json", args=[draft.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertIn("title", response.json())
        self.assertIn("faq_items", response.json())
