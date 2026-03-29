from django.urls import path

from .views import WorkspaceSEOView

app_name = "seo"

urlpatterns = [
    path("workspace/seo/", WorkspaceSEOView.as_view(), name="workspace-seo"),
]
