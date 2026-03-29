from django.urls import path

from .views import (
    WorkspaceGeneratedContentApplyView,
    WorkspaceGeneratedContentCreateView,
    WorkspaceGeneratedContentDetailView,
    WorkspaceGeneratedContentJsonView,
    WorkspaceGeneratedContentListView,
    WorkspaceGeneratedContentUpdateView,
)

app_name = "content"

urlpatterns = [
    path("workspace/content/", WorkspaceGeneratedContentListView.as_view(), name="workspace-content"),
    path("workspace/content/generate/", WorkspaceGeneratedContentCreateView.as_view(), name="workspace-content-generate"),
    path("workspace/content/<int:pk>/edit/", WorkspaceGeneratedContentUpdateView.as_view(), name="workspace-content-update"),
    path("workspace/content/<int:pk>/apply/", WorkspaceGeneratedContentApplyView.as_view(), name="workspace-content-apply"),
    path("workspace/content/<int:pk>/json/", WorkspaceGeneratedContentJsonView.as_view(), name="workspace-content-json"),
    path("workspace/content/<int:pk>/", WorkspaceGeneratedContentDetailView.as_view(), name="workspace-content-detail"),
]
