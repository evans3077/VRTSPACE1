from django.test import TestCase
from django.urls import reverse


class HomePageTests(TestCase):
    def test_home_page_renders_required_sections(self):
        response = self.client.get(reverse("core:home"))

        self.assertEqual(response.status_code, 200)
        # Brand + hero H1
        self.assertContains(response, "VRT SPACE AGENCY")
        self.assertContains(response, "Understand Your Website, Fix What Matters")
        # Three-pillar showcase
        self.assertContains(response, "Audit first. Then SEO. Then AI visibility.")
        self.assertContains(response, "Website Audit")
        self.assertContains(response, "AI Visibility")
        # Pricing tier names
        self.assertContains(response, "Starter")
        # Top-of-funnel CTA
        self.assertContains(response, "Start Free Audit")

    def test_services_index_and_detail_pages_render(self):
        services_response = self.client.get(reverse("core:services"))
        detail_response = self.client.get(reverse("core:service-detail", kwargs={"slug": "seo-services"}))
        custom_detail_response = self.client.get(reverse("core:service-detail", kwargs={"slug": "website-development"}))

        self.assertEqual(services_response.status_code, 200)
        self.assertContains(services_response, "Three connected services")
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, "SEO Services")
        self.assertEqual(custom_detail_response.status_code, 200)
        self.assertContains(custom_detail_response, "Request custom scope")

    def test_packages_page_renders_human_readable_plan_limits(self):
        response = self.client.get(reverse("core:packages"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Choose a plan")
        # Plan slugs are always rendered
        self.assertContains(response, "Starter")
        self.assertContains(response, "Growth")
        self.assertContains(response, "Authority")
        # We never want raw HTML-attribute fragments leaking into rendered copy
        self.assertNotContains(response, "display&#x27;")
