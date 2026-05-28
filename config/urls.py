from django.conf import settings
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import include, path
from django.views.decorators.cache import cache_page

from apps.core.sitemaps import SITEMAPS


def robots_txt(request):
    """
    Public robots.txt.

    Blocks crawlers from:
    - /admin/         — Django admin
    - /workspace/     — Authenticated workspace (all sub-paths)
    - /account/       — User account pages
    - /share/         — Ephemeral share links
    - /tools/audits/  — Per-user audit result pages
    - /auth/          — OAuth flows
    - /billing/       — Stripe webhook receiver

    Points crawlers at the sitemap and llms.txt for structured discovery.
    """
    sitemap_url = request.build_absolute_uri("/sitemap.xml")
    llms_url = request.build_absolute_uri("/llms.txt")
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /admin/\n"
        "Disallow: /workspace/\n"
        "Disallow: /account/\n"
        "Disallow: /share/\n"
        "Disallow: /tools/audits/\n"
        "Disallow: /auth/\n"
        "Disallow: /billing/\n"
        "\n"
        f"Sitemap: {sitemap_url}\n"
        f"# LLM-readable index: {llms_url}\n"
    )
    return HttpResponse(body, content_type="text/plain")


def llms_txt(request):
    """
    LLMs.txt — structured site description for AI/LLM crawlers.
    Follows the emerging llms.txt open standard:
    https://llmstxt.org/
    """
    base = request.build_absolute_uri("/").rstrip("/")
    body = f"""# VRT Space

> VRT Space is an AI-powered SEO and Answer Engine Optimisation (AEO) platform
> for digital agencies and in-house SEO teams. It tracks how brands appear in
> traditional search AND inside AI engines such as ChatGPT, Gemini, and
> Perplexity — then surfaces actionable execution plans to close the gap.

## Core capabilities

- **SEO audit** — technical, content, performance, and internal-linking health scores
- **AI Visibility (AEO)** — answer engine presence tracking across ChatGPT, Gemini, Perplexity
- **GEO Shootout** — prompt-level brand vs. competitor citation analysis
- **Content intelligence** — clinical-grade entity confidence and search-volume data
- **Agency dashboard** — multi-client health overview with score deltas and stale-audit alerts
- **Scheduled audits** — weekly/monthly automated refreshes with score-change notifications
- **Shared reports** — PDF and link-based client-facing audit exports

## Pricing

| Tier | Price/mo | Audits | Websites |
|------|----------|--------|----------|
| Free | $0 | 2 | 1 |
| Starter | $59 | 8 | 3 |
| Growth | $149 | 24 | 10 |
| Authority | $349 | 80 | 25 |

## Key pages

- Home: {base}/
- Pricing: {base}/packages/
- For agencies: {base}/for-agencies/
- Free AI visibility audit: {base}/tools/free-seo-audit/
- AEO content optimizer: {base}/aeo/content-optimizer/
- Blog: {base}/blog/
- Case studies: {base}/case-studies/
- Services: {base}/services/

## Authenticated workspace (not publicly indexable)

Users access their workspace at {base}/workspace/ after signup.
Individual audit results, project dashboards, SEO intelligence, and
AEO tracking are all behind authentication and are NOT indexed.

## Contact

For partnership, press, or API access enquiries: hello@vrtspace.com
"""
    return HttpResponse(body, content_type="text/plain; charset=utf-8")


urlpatterns = [
    path("admin/", admin.site.urls),

    # ── Public SEO infrastructure ─────────────────────────────
    path("robots.txt", robots_txt, name="robots-txt"),
    path("llms.txt", llms_txt, name="llms-txt"),
    path(
        "sitemap.xml",
        cache_page(60 * 60)(sitemap),
        {"sitemaps": SITEMAPS},
        name="sitemap",
    ),

    path("", include("apps.core.urls")),
    path("", include("apps.aeo.urls")),
    path("", include("apps.content.urls")),
    path("", include("apps.leads.urls")),
    path("", include("apps.seo.urls")),
    path("", include("apps.tools.urls")),
    path("", include("apps.analytics.urls")),
    path("", include("apps.affiliates.urls")),
    path("", include("apps.case_studies.urls")),
]


# ── Local-only preview routes for the branded 404 / 500 templates ────────────
# Django shows its yellow-page debug 404 when DEBUG=True, so the branded
# templates never fire in normal local dev. These preview URLs always render
# the templates with the right status code so you can iterate on them locally
# without flipping DEBUG. They're only registered when DEBUG=True, so they
# don't exist in production.
if settings.DEBUG:
    def _preview_404(request):
        return render(request, "404.html", status=404)

    def _preview_500(request):
        return render(request, "500.html", status=500)

    urlpatterns += [
        path("__preview/404/", _preview_404, name="preview-404"),
        path("__preview/500/", _preview_500, name="preview-500"),
    ]


# Django uses these module-level handler names when DEBUG=False to render the
# branded templates. They're already the default behavior, but pinning them
# here documents the contract.
handler404 = "django.views.defaults.page_not_found"
handler500 = "django.views.defaults.server_error"
