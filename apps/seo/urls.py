from django.urls import path

from .views import WorkspaceBacklinkProspectUpdateView, WorkspaceSEOView

app_name = "seo"

urlpatterns = [
    path("workspace/seo/", WorkspaceSEOView.as_view(), name="workspace-seo"),
    path(
        "workspace/seo/backlinks/<int:pk>/update/",
        WorkspaceBacklinkProspectUpdateView.as_view(),
        name="workspace-backlink-prospect-update",
    ),
]
