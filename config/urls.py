from django.conf import settings
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import include, path
from django.views.decorators.cache import cache_page

from apps.core.sitemaps import SITEMAPS


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
