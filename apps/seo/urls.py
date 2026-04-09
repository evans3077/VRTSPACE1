from django.urls import path

from .views import (
    SharedSEOReportPdfView,
    SharedSEOReportView,
    WorkspaceBacklinkProspectUpdateView,
    WorkspaceSEOExportJsonView,
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
    path("share/seo/<slug:token>/", SharedSEOReportView.as_view(), name="shared-seo-report"),
    path("share/seo/<slug:token>/report.pdf", SharedSEOReportPdfView.as_view(), name="shared-seo-report-pdf"),
]
