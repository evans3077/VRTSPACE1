from django.test import TestCase
from django.urls import reverse

from apps.tools.models import AuditRun

from .models import AuditRequest, ClientProject, Lead
from .services import sync_client_project_from_audit_run


class LeadFlowTests(TestCase):
    def test_contact_form_creates_scored_lead(self):
        response = self.client.post(
            reverse("leads:contact"),
            {
                "name": "Jordan",
                "email": "jordan@example.com",
                "company": "Northwind",
                "website": "northwind.example.com",
                "interest_area": "aeo",
                "message": "We need a full rebuild of our service pages and AI visibility strategy.",
                "consent_to_contact": "on",
                "source_page": "/",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Lead.objects.count(), 1)
        self.assertGreaterEqual(Lead.objects.get().score, 50)
        self.assertEqual(Lead.objects.get().source_page, "/")

    def test_contact_form_captures_submission_context(self):
        response = self.client.post(
            reverse("leads:contact"),
            {
                "name": "Jordan",
                "email": "jordan@example.com",
                "company": "Northwind",
                "website": "northwind.example.com",
                "interest_area": "aeo",
                "message": "We need a full rebuild of our service pages and AI visibility strategy.",
                "consent_to_contact": "on",
                "source_page": "/pricing",
            },
            HTTP_CF_IPCOUNTRY="KE",
            HTTP_CF_REGION="Nairobi County",
            HTTP_REFERER="https://vrtspace.agency/pricing",
        )

        self.assertEqual(response.status_code, 302)
        lead = Lead.objects.get()
        self.assertEqual(lead.submission_context["country"], "KE")
        self.assertEqual(lead.submission_context["region"], "Nairobi County")
        self.assertEqual(lead.submission_context["source_page"], "/pricing")

    def test_invalid_contact_form_renders_home_with_errors(self):
        response = self.client.post(
            reverse("leads:contact"),
            {
                "name": "Jordan",
                "company": "Northwind",
                "interest_area": "aeo",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "This field is required.", status_code=400)

    def test_audit_request_normalizes_website_and_scores_request(self):
        response = self.client.post(
            reverse("leads:free-aeo-audit"),
            {
                "company_name": "Northwind",
                "email": "ops@example.com",
                "website": "northwind.example.com",
                "business_type": "automotive",
                "location": "Nairobi, Kenya",
                "target_goal": "Increase qualified leads",
                "primary_service": "Used car sales",
                "monthly_leads_goal": 60,
                "notes": "We want better rankings and AI citations across enterprise pages.",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(AuditRequest.objects.count(), 1)
        audit_request = AuditRequest.objects.get()
        self.assertEqual(audit_request.website, "https://northwind.example.com")
        self.assertEqual(audit_request.business_type, "automotive")
        self.assertEqual(audit_request.location, "Nairobi, Kenya")
        self.assertEqual(audit_request.target_goal, "Increase qualified leads")
        self.assertEqual(audit_request.primary_service, "Used car sales")
        self.assertEqual(audit_request.status, AuditRequest.Status.QUALIFIED)
        self.assertEqual(audit_request.submission_context, {})

    def test_sync_client_project_from_audit_run_creates_project_snapshot(self):
        audit_request = AuditRequest.objects.create(
            company_name="Northwind",
            email="ops@example.com",
            website="https://northwind.example.com",
            business_type="automotive",
            location="Nairobi, Kenya",
            target_goal="Increase qualified leads",
            primary_service="Used car sales",
            monthly_leads_goal=60,
            status=AuditRequest.Status.QUALIFIED,
        )
        audit_run = AuditRun.objects.create(
            audit_request=audit_request,
            normalized_domain="northwind.example.com",
            start_url="https://northwind.example.com",
            overall_score=82,
        )

        project = sync_client_project_from_audit_run(audit_run)

        self.assertEqual(project.audit_request, audit_request)
        self.assertEqual(project.latest_audit_run, audit_run)
        self.assertEqual(project.latest_score, 82)
        self.assertEqual(project.stage, project.Stage.PROPOSAL)
        self.assertEqual(project.business_type, "automotive")
        self.assertEqual(project.location, "Nairobi, Kenya")
        self.assertEqual(project.target_goal, "Increase qualified leads")
        self.assertEqual(project.primary_service, "Used car sales")

    def test_sync_client_project_updates_existing_project_context_from_new_audit(self):
        audit_request = AuditRequest.objects.create(
            company_name="Northwind",
            email="ops@example.com",
            website="https://northwind.example.com",
            business_type="automotive",
            location="Nairobi, Kenya",
            target_goal="Increase qualified leads",
            primary_service="Used car sales",
            monthly_leads_goal=60,
            status=AuditRequest.Status.NEW,
        )
        project = ClientProject.objects.create(
            audit_request=audit_request,
            name="Northwind",
            website="https://northwind.example.com",
            normalized_domain="northwind.example.com",
            contact_email="ops@example.com",
        )
        audit_run = AuditRun.objects.create(
            audit_request=audit_request,
            normalized_domain="northwind.example.com",
            start_url="https://northwind.example.com",
            overall_score=74,
        )

        refreshed_project = sync_client_project_from_audit_run(audit_run)

        self.assertEqual(refreshed_project.pk, project.pk)
        self.assertEqual(refreshed_project.business_type, "automotive")
        self.assertEqual(refreshed_project.location, "Nairobi, Kenya")
        self.assertEqual(refreshed_project.target_goal, "Increase qualified leads")
        self.assertEqual(refreshed_project.primary_service, "Used car sales")
