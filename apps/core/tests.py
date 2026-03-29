from django.test import TestCase
from django.urls import reverse


class HomePageTests(TestCase):
    def test_home_page_renders_required_sections(self):
        response = self.client.get(reverse("core:home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "VRT SPACE AGENCY")
        self.assertContains(response, "VRT Authority Engine")
        self.assertContains(response, "Request a Free AEO Audit")
        self.assertContains(response, "Core Revenue Services")
        self.assertContains(response, "Starter")
        self.assertContains(response, "Client experience")
        self.assertContains(response, "Engagement journey")

    def test_services_index_and_detail_pages_render(self):
        services_response = self.client.get(reverse("core:services"))
        detail_response = self.client.get(reverse("core:service-detail", kwargs={"slug": "seo-services"}))

        self.assertEqual(services_response.status_code, 200)
        self.assertContains(services_response, "Browse the VRT SPACE service system.")
        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, "SEO Services")
