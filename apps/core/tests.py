from django.test import TestCase
from django.urls import reverse


class HomePageTests(TestCase):
    def test_home_page_renders_required_sections(self):
        response = self.client.get(reverse("core:home"))

        self.assertEqual(response.status_code, 200)
        # Brand + hero H1
        self.assertContains(response, "VRT SPACE AGENCY")
        self.assertContains(response, "Be the source behind the answer.")
        # Three-pillar showcase
        self.assertContains(response, "AI visibility. Backed by SEO. Built on audit.")
        self.assertContains(response, "AI Visibility")
        # Top-of-funnel CTA
        self.assertContains(response, "Run Free AI Visibility Audit")

    def test_services_index_and_detail_pages_render(self):
        services_response = self.client.get(reverse("core:services"))
        detail_response = self.client.get(reverse("core:service-detail", kwargs={"slug": "seo-analysis"}))
        audit_detail_response = self.client.get(reverse("core:service-detail", kwargs={"slug": "website-audit"}))

        self.assertEqual(services_response.status_code, 200)
        self.assertContains(services_response, "Three connected services")
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, "SEO Analysis")
        self.assertEqual(audit_detail_response.status_code, 200)
        self.assertContains(audit_detail_response, "Website Audit")

    def test_packages_page_renders_human_readable_plan_limits(self):
        response = self.client.get(reverse("core:packages"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pick the plan")
        # Plan slugs are always rendered
        self.assertContains(response, "Starter")
        self.assertContains(response, "Growth")
        self.assertContains(response, "Authority")
        # We never want raw HTML-attribute fragments leaking into rendered copy
        self.assertNotContains(response, "display&#x27;")
