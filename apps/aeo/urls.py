from django.urls import path

from .views import (
    AEOAuditPollView,
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
]
