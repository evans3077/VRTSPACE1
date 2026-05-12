from django.urls import path

from .views import (
    WorkspaceGeneratedContentApplyView,
    WorkspaceGeneratedContentCreateView,
    WorkspaceGeneratedContentDetailView,
    WorkspaceGeneratedContentFromSEOView,
    WorkspaceGeneratedContentJsonView,
    WorkspaceGeneratedContentListView,
    WorkspaceGeneratedContentUpdateView,
    WorkspaceEditorialQueueSyncView,
)
from .cms_views import (
    WorkspaceCMSCredentialView,
    WorkspaceEditorialTaskPushView,
)

app_name = "content"

urlpatterns = [
    path("workspace/content/", WorkspaceGeneratedContentListView.as_view(), name="workspace-content"),
    path("workspace/content/generate/", WorkspaceGeneratedContentCreateView.as_view(), name="workspace-content-generate"),
    path("workspace/content/generate-from-seo/", WorkspaceGeneratedContentFromSEOView.as_view(), name="workspace-content-generate-from-seo"),
    path("workspace/content/editorial-queue/sync/", WorkspaceEditorialQueueSyncView.as_view(), name="workspace-content-editorial-sync"),
    path("workspace/content/<int:pk>/edit/", WorkspaceGeneratedContentUpdateView.as_view(), name="workspace-content-update"),
    path("workspace/content/<int:pk>/apply/", WorkspaceGeneratedContentApplyView.as_view(), name="workspace-content-apply"),
    path("workspace/content/<int:pk>/json/", WorkspaceGeneratedContentJsonView.as_view(), name="workspace-content-json"),
    path("workspace/content/<int:pk>/", WorkspaceGeneratedContentDetailView.as_view(), name="workspace-content-detail"),
    path("workspace/cms/credentials/", WorkspaceCMSCredentialView.as_view(), name="workspace-cms-credentials"),
    path("workspace/content/tasks/<int:pk>/push/", WorkspaceEditorialTaskPushView.as_view(), name="workspace-content-task-push"),
]
