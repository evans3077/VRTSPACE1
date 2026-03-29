from django.urls import path

from .views import (
    AgencyAuditDetailView,
    AuditResultDetailView,
    GoogleOAuthCallbackView,
    GoogleOAuthStartView,
    ProjectDashboardDetailView,
    PublicAuditCreateView,
    WorkspaceDashboardView,
    WorkspaceLoginView,
    WorkspaceLogoutView,
    WorkspaceSignupView,
)

app_name = "tools"

urlpatterns = [
    path("tools/free-seo-audit/", PublicAuditCreateView.as_view(), name="free-seo-audit"),
    path("tools/audits/<int:pk>/", AuditResultDetailView.as_view(), name="audit-result"),
    path("tools/agency/audits/<int:pk>/", AgencyAuditDetailView.as_view(), name="agency-audit"),
    path("tools/agency/projects/<int:pk>/", ProjectDashboardDetailView.as_view(), name="project-dashboard"),
    path("workspace/start/", WorkspaceSignupView.as_view(), name="workspace-signup"),
    path("workspace/login/", WorkspaceLoginView.as_view(), name="workspace-login"),
    path("workspace/logout/", WorkspaceLogoutView.as_view(), name="workspace-logout"),
    path("auth/google/start/", GoogleOAuthStartView.as_view(), name="google-oauth-start"),
    path("auth/google/callback/", GoogleOAuthCallbackView.as_view(), name="google-oauth-callback"),
    path("workspace/", WorkspaceDashboardView.as_view(), name="workspace-dashboard"),
]
