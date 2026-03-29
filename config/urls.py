from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.core.urls")),
    path("", include("apps.aeo.urls")),
    path("", include("apps.content.urls")),
    path("", include("apps.leads.urls")),
    path("", include("apps.seo.urls")),
    path("", include("apps.tools.urls")),
    path("", include("apps.analytics.urls")),
]
