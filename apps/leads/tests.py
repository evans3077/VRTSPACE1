from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.core.plan_catalog import get_plan_definition
from apps.tools.models import AuditRun

from .billing import (
    build_plan_cards,
    estimate_credit_cost,
    get_credit_balance_summary,
    get_total_credit_balance_summary,
    spend_action_credits,
    spend_credits,
    sync_workspace_plan_catalog,
)
from .models import AuditRequest, ClientProject, Lead, WorkspaceCreditLedger, WorkspacePlan, WorkspaceSubscription
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


class WorkspaceCreditSystemTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="billing-user",
            email="billing@example.com",
            password="pass1234",
        )
        sync_workspace_plan_catalog()

    def test_build_plan_cards_includes_free_and_credit_metadata(self):
        cards = build_plan_cards(self.user)

        self.assertTrue(any(card["slug"] == "free" for card in cards))
        starter = next(card for card in cards if card["slug"] == "starter")
        self.assertEqual(starter["credits"]["workspace"], 50)

    def test_spend_credits_creates_workspace_grant_and_action_debit_entries(self):
        starter = WorkspacePlan.objects.get(slug="starter")
        WorkspaceSubscription.objects.create(
            user=self.user,
            plan=starter,
            status=WorkspaceSubscription.Status.ACTIVE,
        )

        spend_credits(self.user, "seo", amount=1, note="SEO refresh")

        self.assertEqual(
            WorkspaceCreditLedger.objects.filter(user=self.user).count(),
            2,
        )
        balance = get_total_credit_balance_summary(self.user)
        self.assertEqual(balance["granted"], get_plan_definition("starter")["credits"]["workspace"])
        self.assertEqual(balance["used"], 1)
        self.assertEqual(balance["remaining"], 49)

    def test_estimate_credit_cost_scales_with_project_complexity(self):
        audit_request = AuditRequest.objects.create(
            company_name="Northwind",
            email="ops@example.com",
            website="https://northwind.example.com",
        )
        audit_run = AuditRun.objects.create(
            audit_request=audit_request,
            normalized_domain="northwind.example.com",
            start_url="https://northwind.example.com",
            pages_crawled=60,
        )
        project = ClientProject.objects.create(
            audit_request=audit_request,
            latest_audit_run=audit_run,
            name="Northwind",
            website="https://northwind.example.com",
            normalized_domain="northwind.example.com",
            contact_email="ops@example.com",
        )

        audit_cost = estimate_credit_cost("audit", project=project)
        seo_cost = estimate_credit_cost("seo", project=project)

        self.assertGreaterEqual(audit_cost["amount"], 5)
        self.assertGreater(seo_cost["amount"], audit_cost["amount"])
        self.assertTrue(seo_cost["uses_existing_audit"])

    def test_spend_action_credits_persists_complexity_metadata(self):
        starter = WorkspacePlan.objects.get(slug="starter")
        subscription = WorkspaceSubscription.objects.create(
            user=self.user,
            plan=starter,
            status=WorkspaceSubscription.Status.ACTIVE,
        )
        audit_request = AuditRequest.objects.create(
            company_name="Northwind",
            email="ops@example.com",
            website="https://northwind.example.com",
        )
        audit_run = AuditRun.objects.create(
            audit_request=audit_request,
            normalized_domain="northwind.example.com",
            start_url="https://northwind.example.com",
            pages_crawled=18,
        )
        project = ClientProject.objects.create(
            audit_request=audit_request,
            latest_audit_run=audit_run,
            owner=self.user,
            name="Northwind",
            website="https://northwind.example.com",
            normalized_domain="northwind.example.com",
            contact_email="ops@example.com",
        )

        entry, estimate = spend_action_credits(
            self.user,
            "seo",
            project=project,
            note="SEO refresh",
            reference_key="test-seo-refresh",
        )

        self.assertEqual(entry.subscription, subscription)
        self.assertEqual(entry.metadata["estimated_cost"], estimate["amount"])
        self.assertIn("cost_reason", entry.metadata)
