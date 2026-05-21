from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.http import HttpResponse
from django.urls import include, path
from django.views.decorators.cache import cache_page

from apps.core.sitemaps import SITEMAPS


def sentry_debug(request):
    """Staff-only endpoint that intentionally raises so we can verify
    Sentry is capturing exceptions. Returns 404 to non-staff to avoid
    leaking the endpoint."""
    from django.http import Http404
    if not (request.user.is_authenticated and request.user.is_staff):
        raise Http404("Not found.")
    # This raise is intentional — it should appear in Sentry within seconds.
    raise RuntimeError("Sentry debug test — captured at " + request.build_absolute_uri())


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
    # ── Internal: trigger a fake error to verify Sentry wiring ────
    path("_sentry-debug/", sentry_debug, name="sentry-debug"),
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
