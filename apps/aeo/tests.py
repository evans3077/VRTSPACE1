from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.leads.models import AuditRequest, ClientProject, UsageRecord
from apps.seo.models import SEOProjectProfile
from apps.tools.models import AuditPage, AuditRun

from .models import AEOAudit, AIRecommendation
from .services import build_aeo_payload, create_aeo_audit


class AEOServiceTests(TestCase):
    def test_build_aeo_payload_returns_scores_and_recommendations(self):
        audit_run = AuditRun.objects.create(
            normalized_domain="example.com",
            start_url="https://example.com/",
            overall_score=72,
            on_page_score=60,
            content_score=68,
            aeo_score=55,
            status=AuditRun.Status.COMPLETED,
            summary={"context_analysis": {}},
        )
        AuditPage.objects.create(
            audit_run=audit_run,
            url="https://example.com/",
            status_code=200,
            h1="Example heading",
            meta_description="Example meta description",
            word_count=220,
            schema_count=1,
            has_faq_schema=True,
        )
        profile = SEOProjectProfile(
            business_type="automotive",
            location="Nairobi",
            target_goal="Increase qualified organic leads",
            primary_service="used car dealership",
        )

        payload = build_aeo_payload(
            audit_run=audit_run,
            profile=profile,
            target_keyword="best used car dealership in Nairobi",
        )

        self.assertIn("scores", payload)
        self.assertIn("recommendations", payload)
        self.assertGreater(payload["scores"]["visibility_score"], 0)
        self.assertTrue(payload["recommendations"])
        self.assertIn("Nairobi", payload["recommendations"][0]["example_rewrite"])
        self.assertIn("root_cause_label", payload["recommendations"][0])
        self.assertGreater(payload["recommendations"][0]["evidence_score"], 0)
        self.assertTrue(payload["recommendations"][0]["where_to_apply"])

    def test_create_aeo_audit_persists_recommendation_records(self):
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
            on_page_score=61,
            content_score=66,
            aeo_score=58,
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
        SEOProjectProfile.objects.create(
            project=project,
            business_type="automotive",
            location="Nairobi",
            target_goal="Increase qualified organic leads",
            primary_service="used car dealership",
        )

        aeo_audit = create_aeo_audit(project=project, target_keyword="used car dealership Nairobi")

        self.assertIsInstance(aeo_audit, AEOAudit)
        self.assertGreater(AIRecommendation.objects.filter(aeo_audit=aeo_audit).count(), 0)


class WorkspaceAEOViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="aeo@example.com",
            email="aeo@example.com",
            password="strongpass123",
        )
        audit_request = AuditRequest.objects.create(
            company_name="Northwind",
            email="aeo@example.com",
            website="https://example.com",
        )
        self.audit_run = AuditRun.objects.create(
            audit_request=audit_request,
            normalized_domain="example.com",
            start_url="https://example.com/",
            overall_score=77,
            on_page_score=63,
            content_score=71,
            aeo_score=57,
            status=AuditRun.Status.COMPLETED,
            summary={},
        )
        AuditPage.objects.create(
            audit_run=self.audit_run,
            url="https://example.com/",
            status_code=200,
            h1="Example heading",
            meta_description="Example meta description",
            word_count=240,
        )
        self.project = ClientProject.objects.create(
            owner=self.user,
            audit_request=audit_request,
            latest_audit_run=self.audit_run,
            name="Northwind",
            website="https://example.com",
            normalized_domain="example.com",
            contact_email="aeo@example.com",
            latest_score=77,
        )
        SEOProjectProfile.objects.create(
            project=self.project,
            business_type="automotive",
            location="Nairobi",
            target_goal="Increase qualified organic leads",
            primary_service="used car dealership",
        )

    def test_workspace_aeo_view_renders(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("aeo:workspace-aeo"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Generate AEO snapshot")

    def test_workspace_aeo_post_creates_snapshot_and_usage_record(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("aeo:workspace-aeo"),
            {"target_keyword": "used car dealership Nairobi"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(AEOAudit.objects.count(), 1)
        self.assertTrue(AIRecommendation.objects.exists())
        self.assertEqual(
            UsageRecord.objects.get(user=self.user, metric=UsageRecord.Metric.AEO_AUDIT).quantity,
            1,
        )
        self.assertContains(response, "What AI systems need from this site")
        self.assertContains(response, "Evidence confidence")

    def test_workspace_aeo_uses_selected_project(self):
        second_request = AuditRequest.objects.create(
            company_name="Second Project",
            email="aeo@example.com",
            website="https://second-example.com",
        )
        second_run = AuditRun.objects.create(
            audit_request=second_request,
            normalized_domain="second-example.com",
            start_url="https://second-example.com/",
            overall_score=71,
            on_page_score=60,
            content_score=65,
            aeo_score=54,
            status=AuditRun.Status.COMPLETED,
            summary={},
        )
        AuditPage.objects.create(
            audit_run=second_run,
            url="https://second-example.com/",
            status_code=200,
            h1="Second heading",
            meta_description="Second description",
            word_count=180,
        )
        second_project = ClientProject.objects.create(
            owner=self.user,
            audit_request=second_request,
            latest_audit_run=second_run,
            name="Second Project",
            website="https://second-example.com",
            normalized_domain="second-example.com",
            contact_email="aeo@example.com",
            latest_score=71,
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

        response = self.client.get(reverse("aeo:workspace-aeo"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Second Project")
        self.assertEqual(response.context["project"].pk, second_project.pk)
