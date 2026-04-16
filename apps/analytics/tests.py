from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.leads.models import AuditRequest, ClientProject, Lead


class OperationsDashboardTests(TestCase):
    def test_staff_dashboard_renders_live_metrics(self):
        user = get_user_model().objects.create_user(
            username="ops",
            email="ops@example.com",
            password="testpass123",
            is_staff=True,
        )
        Lead.objects.create(
            name="Jordan",
            email="jordan@example.com",
            company="Northwind",
            website="https://northwind.example.com",
            interest_area=Lead.InterestArea.SEO,
            message="Need SEO support",
            score=80,
            submission_context={"country": "KE", "region": "Nairobi County"},
        )
        audit_request = AuditRequest.objects.create(
            company_name="Northwind",
            email="ops@example.com",
            website="https://northwind.example.com",
            monthly_leads_goal=40,
            score=80,
            status=AuditRequest.Status.QUALIFIED,
            submission_context={"country": "KE", "region": "Nairobi County"},
        )
        ClientProject.objects.create(
            audit_request=audit_request,
            name="Northwind",
            website="https://northwind.example.com",
            normalized_domain="northwind.example.com",
            contact_email="ops@example.com",
            latest_score=78,
        )

        self.client.force_login(user)
        response = self.client.get(reverse("analytics:operations-dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Live SaaS demand and inquiry visibility")
        self.assertContains(response, "Jordan")
        self.assertContains(response, "Northwind")
        self.assertContains(response, "KE")
        self.assertContains(response, "Nairobi County")
