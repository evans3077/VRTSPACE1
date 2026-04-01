from django.urls import path

from .views import (
    WorkspaceBacklinkProspectUpdateView,
    WorkspaceSEOCampaignUpdateView,
    WorkspaceSEOCompetitorReviewView,
    WorkspaceSEOView,
)

app_name = "seo"

urlpatterns = [
    path("workspace/seo/", WorkspaceSEOView.as_view(), name="workspace-seo"),
    path(
        "workspace/seo/competitors/<int:pk>/review/",
        WorkspaceSEOCompetitorReviewView.as_view(),
        name="workspace-seo-competitor-review",
    ),
    path(
        "workspace/seo/campaigns/<int:pk>/update/",
        WorkspaceSEOCampaignUpdateView.as_view(),
        name="workspace-seo-campaign-update",
    ),
    path(
        "workspace/seo/backlinks/<int:pk>/update/",
        WorkspaceBacklinkProspectUpdateView.as_view(),
        name="workspace-backlink-prospect-update",
    ),
]
