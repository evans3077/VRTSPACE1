from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.leads.models import AuditRequest, ClientProject
from apps.tools.models import AuditRun

from .models import Article, GeneratedContent, Service
from .services import apply_generated_content, create_generated_content, generate_content_payload


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

    def test_workspace_content_view_renders(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("content:workspace-content"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Generate draft")
        self.assertContains(response, "Northwind")

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
