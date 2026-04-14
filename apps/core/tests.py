from django.test import TestCase
from django.urls import reverse


class HomePageTests(TestCase):
    def test_home_page_renders_required_sections(self):
        response = self.client.get(reverse("core:home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "VRT SPACE AGENCY")
        self.assertContains(response, "Get found, fix what is blocking growth")
        self.assertContains(response, "Get Your Audit")
        self.assertContains(response, "Three clear ways we help businesses get found")
        self.assertContains(response, "Discover, audit, improve, grow.")
        self.assertContains(response, "Talk to us about the right next step.")

    def test_services_index_and_detail_pages_render(self):
        services_response = self.client.get(reverse("core:services"))
        detail_response = self.client.get(reverse("core:service-detail", kwargs={"slug": "seo"}))
        audit_detail_response = self.client.get(reverse("core:service-detail", kwargs={"slug": "audit"}))

        self.assertEqual(services_response.status_code, 200)
        self.assertContains(services_response, "Three focused ways we help businesses grow online.")
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, "SEO")
        self.assertContains(detail_response, "Get Your Audit")
        self.assertEqual(audit_detail_response.status_code, 200)
        self.assertContains(audit_detail_response, "Audit")

    def test_packages_page_renders_human_readable_plan_limits(self):
        response = self.client.get(reverse("core:packages"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Choose the level of support that fits your next stage.")
        self.assertContains(response, "Audit runs:")
        self.assertContains(response, "Saved runs:")
        self.assertNotContains(response, "display&#x27;")
