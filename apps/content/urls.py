from django.urls import path

from .views import (
    WorkspaceGeneratedContentCreateView,
    WorkspaceGeneratedContentDetailView,
    WorkspaceGeneratedContentListView,
)

app_name = "content"

urlpatterns = [
    path("workspace/content/", WorkspaceGeneratedContentListView.as_view(), name="workspace-content"),
    path("workspace/content/generate/", WorkspaceGeneratedContentCreateView.as_view(), name="workspace-content-generate"),
    path("workspace/content/<int:pk>/", WorkspaceGeneratedContentDetailView.as_view(), name="workspace-content-detail"),
]
