from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.http import HttpResponse
from django.urls import include, path
from django.views.decorators.cache import cache_page

from apps.core.sitemaps import SITEMAPS


def sentry_debug(request):
    """Intentionally raises so Sentry can verify capture. Matches the URL
    Sentry's Django onboarding wizard suggests (``/sentry-debug/``) plus
    an underscore-prefixed alias for safer linking.

    The endpoint is freely accessible — that's how Sentry's docs design
    the verification flow. The only side effect is one captured event per
    request, which is bounded by Sentry's per-project rate limits."""
    # The classic division-by-zero — matches Sentry's wizard example.
    division_by_zero = 1 / 0
    return division_by_zero  # pragma: no cover — unreachable


def robots_txt(request):
    """Public robots.txt that points crawlers at the sitemap."""
    sitemap_url = request.build_absolute_uri("/sitemap.xml")
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /admin/\n"
        "Disallow: /workspace/\n"
        "Disallow: /share/\n"
        "Disallow: /tools/audits/\n"
        "Disallow: /auth/\n"
        "\n"
        f"Sitemap: {sitemap_url}\n"
    )
    return HttpResponse(body, content_type="text/plain")


urlpatterns = [
    path("admin/", admin.site.urls),

    # ── Public SEO infrastructure ─────────────────────────────
    path("robots.txt", robots_txt, name="robots-txt"),
    # ── Sentry verification routes ────────────────────────────────
    # `/sentry-debug/` matches Sentry's Django onboarding wizard exactly.
    # `/_sentry-debug/` kept as an alias so existing links keep working.
    path("sentry-debug/", sentry_debug, name="sentry-debug"),
    path("_sentry-debug/", sentry_debug, name="sentry-debug-alias"),
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
