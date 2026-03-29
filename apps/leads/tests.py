from django.test import TestCase
from django.urls import reverse

from .models import AuditRequest, Lead


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
                "monthly_leads_goal": 60,
                "notes": "We want better rankings and AI citations across enterprise pages.",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(AuditRequest.objects.count(), 1)
        audit_request = AuditRequest.objects.get()
        self.assertEqual(audit_request.website, "https://northwind.example.com")
        self.assertEqual(audit_request.status, AuditRequest.Status.QUALIFIED)
