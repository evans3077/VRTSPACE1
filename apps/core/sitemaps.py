"""
Site-wide sitemap definitions.

Wired in config/urls.py at /sitemap.xml. Covers:
  - Static marketing pages (home, packages, blog index, case studies index,
    free tools, AEO index, for-agencies, services index)
  - Industry programmatic landing pages (/ai-visibility-for/<slug>/)
  - Dynamic published Articles
  - Dynamic CaseStudy entries
  - Static Service detail pages from the content app

Each sitemap class overrides get_urls() to use request.build_absolute_uri()
so we don't need the django.contrib.sites framework to resolve hostnames.
"""

from __future__ import annotations

from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from apps.case_studies.models import CaseStudy
from apps.content.models import Article
from apps.core.industry_pages import list_industry_pages


class _ProtocolMixin:
    """Make sitemaps default to https so search engines see the canonical URL."""
    protocol = "https"


class StaticSitemap(_ProtocolMixin, Sitemap):
    """All hand-built, indexable marketing pages."""

    changefreq = "weekly"
    priority = 0.8

    def items(self):
        return [
            "core:home",
            "core:packages",
            "core:for-agencies",
            "core:services",
            "content:blog-index",
            "case_studies:case-study-index",
            "aeo:content-optimizer",
            "aeo:aeo-index",
        ]

    def location(self, item):
        return reverse(item)


class IndustryLandingSitemap(_ProtocolMixin, Sitemap):
    """Programmatic /ai-visibility-for/<slug>/ pages."""

    changefreq = "monthly"
    priority = 0.7

    def items(self):
        return list_industry_pages()

    def location(self, item):
        return reverse("core:industry-landing", kwargs={"slug": item["slug"]})


class ArticleSitemap(_ProtocolMixin, Sitemap):
    """Published blog articles."""

    changefreq = "monthly"
    priority = 0.6

    def items(self):
        return Article.objects.filter(status=Article.Status.PUBLISHED).order_by(
            "-published_at", "-created_at"
        )

    def location(self, obj):
        return reverse("content:blog-detail", kwargs={"slug": obj.slug})

    def lastmod(self, obj):
        return obj.updated_at or obj.published_at or obj.created_at


class CaseStudySitemap(_ProtocolMixin, Sitemap):
    """Public case studies."""

    changefreq = "monthly"
    priority = 0.6

    def items(self):
        return CaseStudy.objects.all().order_by("-featured", "-created_at")

    def location(self, obj):
        return reverse("case_studies:case-study-detail", kwargs={"slug": obj.slug})

    def lastmod(self, obj):
        return obj.updated_at or obj.created_at


SITEMAPS = {
    "static": StaticSitemap,
    "industries": IndustryLandingSitemap,
    "articles": ArticleSitemap,
    "case_studies": CaseStudySitemap,
}
