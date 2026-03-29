from django.test import TestCase
from django.urls import reverse


class HomePageTests(TestCase):
    def test_home_page_renders_required_sections(self):
        response = self.client.get(reverse("core:home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "VRT SPACE AGENCY")
        self.assertContains(response, "VRT Authority Engine")
        self.assertContains(response, "Run Free Audit")
        self.assertContains(response, "Core Growth Modules")
        self.assertContains(response, "Starter")
        self.assertContains(response, "Product experience")
        self.assertContains(response, "User journey")
        self.assertContains(response, "?package=starter")
        self.assertContains(response, "Request custom build")

    def test_services_index_and_detail_pages_render(self):
        services_response = self.client.get(reverse("core:services"))
        detail_response = self.client.get(reverse("core:service-detail", kwargs={"slug": "seo-services"}))
        custom_detail_response = self.client.get(reverse("core:service-detail", kwargs={"slug": "website-development"}))

        self.assertEqual(services_response.status_code, 200)
        self.assertContains(services_response, "Browse the VRT SPACE growth system.")
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, "SEO Services")
        self.assertContains(detail_response, "Run Free Audit")
        self.assertEqual(custom_detail_response.status_code, 200)
        self.assertContains(custom_detail_response, "Request custom scope")
