from django.urls import path

from .views import (
    SEOCampaignActionPackView,
    SharedSEOReportPdfView,
    SharedSEOReportView,
    WorkspaceBacklinkProspectUpdateView,
    WorkspaceClinicalDataView,
    WorkspaceEntityConfidenceView,
    WorkspaceGEOShootoutView,
    WorkspaceGSCCallbackView,
    WorkspaceGSCConnectView,
    WorkspaceGSCDataView,
    WorkspaceGSCDisconnectView,
    WorkspaceIndexingPingView,
    WorkspaceSEOExportJsonView,
    WorkspaceSEOPromoteToPromptView,
    WorkspaceSEOReportPdfView,
    WorkspaceSEOCampaignUpdateView,
    WorkspaceSEOCompetitorReviewView,
    WorkspaceSEOShareCreateView,
    WorkspaceSEOView,
)

app_name = "seo"

urlpatterns = [
    path("workspace/seo/", WorkspaceSEOView.as_view(), name="workspace-seo"),
    path("workspace/seo/report.pdf", WorkspaceSEOReportPdfView.as_view(), name="workspace-seo-report-pdf"),
    path("workspace/seo/export.json", WorkspaceSEOExportJsonView.as_view(), name="workspace-seo-export-json"),
    path("workspace/seo/share/", WorkspaceSEOShareCreateView.as_view(), name="workspace-seo-share-create"),
    path("workspace/seo/promote-to-prompt/", WorkspaceSEOPromoteToPromptView.as_view(), name="workspace-seo-promote-to-prompt"),
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
        "workspace/seo/campaigns/<int:pk>/action-pack/",
        SEOCampaignActionPackView.as_view(),
        name="campaign-action-pack",
    ),
    path(
        "workspace/seo/backlinks/<int:pk>/update/",
        WorkspaceBacklinkProspectUpdateView.as_view(),
        name="workspace-backlink-prospect-update",
    ),
    path("share/seo/<slug:token>/", SharedSEOReportView.as_view(), name="shared-seo-report"),
    path("share/seo/<slug:token>/report.pdf", SharedSEOReportPdfView.as_view(), name="shared-seo-report-pdf"),
    # Phase 12: Clinical Intelligence actions
    path("workspace/seo/geo-shootout/", WorkspaceGEOShootoutView.as_view(), name="workspace-geo-shootout"),
    path("workspace/seo/clinical-data/", WorkspaceClinicalDataView.as_view(), name="workspace-clinical-data"),
    path("workspace/seo/entity-confidence/", WorkspaceEntityConfidenceView.as_view(), name="workspace-entity-confidence"),
    path("workspace/seo/indexing-ping/", WorkspaceIndexingPingView.as_view(), name="workspace-indexing-ping"),
    # Phase 12: Google Search Console OAuth
    path("workspace/seo/gsc/connect/", WorkspaceGSCConnectView.as_view(), name="workspace-gsc-connect"),
    path("workspace/seo/gsc/callback/", WorkspaceGSCCallbackView.as_view(), name="workspace-gsc-callback"),
    path("workspace/seo/gsc/disconnect/", WorkspaceGSCDisconnectView.as_view(), name="workspace-gsc-disconnect"),
    path("workspace/seo/gsc/data/", WorkspaceGSCDataView.as_view(), name="workspace-gsc-data"),
]
