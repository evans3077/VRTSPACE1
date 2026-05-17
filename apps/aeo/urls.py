from django.urls import path

from .views import (
    AEOAuditPollView,
    AEOIndexDetailView,
    AEOIndexHomeView,
    AEOShareView,
    ContentOptimizerView,
    WorkspaceAEOView,
    WorkspacePromptDetailView,
    WorkspacePromptsView,
    WorkspaceShareOfVoiceView,
)

app_name = "aeo"

urlpatterns = [
    path("workspace/aeo/", WorkspaceAEOView.as_view(), name="workspace-aeo"),
    path(
        "workspace/aeo/<int:pk>/status/",
        AEOAuditPollView.as_view(),
        name="workspace-aeo-poll",
    ),
    path("workspace/prompts/", WorkspacePromptsView.as_view(), name="workspace-prompts"),
    path(
        "workspace/prompts/<int:pk>/",
        WorkspacePromptDetailView.as_view(),
        name="workspace-prompt-detail",
    ),
    path(
        "workspace/share-of-voice/",
        WorkspaceShareOfVoiceView.as_view(),
        name="workspace-share-of-voice",
    ),
    path(
        "aeo/share/<str:token>/",
        AEOShareView.as_view(),
        name="aeo-share",
    ),
    path("tools/ai-content-optimizer/", ContentOptimizerView.as_view(), name="content-optimizer"),
    path("aeo-index/", AEOIndexHomeView.as_view(), name="aeo-index"),
    path(
        "aeo-index/<str:domain>/",
        AEOIndexDetailView.as_view(),
        name="aeo-index-detail",
    ),
]
