from django.urls import path

from .views import (
    AEOAuditPollView,
    AEOIndexDetailView,
    AEOIndexHomeView,
    AEOShareView,
    WorkspaceAEOView,
)

app_name = "aeo"

urlpatterns = [
    path("workspace/aeo/", WorkspaceAEOView.as_view(), name="workspace-aeo"),
    path(
        "workspace/aeo/<int:pk>/status/",
        AEOAuditPollView.as_view(),
        name="workspace-aeo-poll",
    ),
    path(
        "aeo/share/<str:token>/",
        AEOShareView.as_view(),
        name="aeo-share",
    ),
    path("aeo-index/", AEOIndexHomeView.as_view(), name="aeo-index"),
    path(
        "aeo-index/<str:domain>/",
        AEOIndexDetailView.as_view(),
        name="aeo-index-detail",
    ),
]
