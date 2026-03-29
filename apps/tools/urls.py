from django.urls import path

from .views import AgencyAuditDetailView, AuditResultDetailView, PublicAuditCreateView

app_name = "tools"

urlpatterns = [
    path("tools/free-seo-audit/", PublicAuditCreateView.as_view(), name="free-seo-audit"),
    path("tools/audits/<int:pk>/", AuditResultDetailView.as_view(), name="audit-result"),
    path("tools/agency/audits/<int:pk>/", AgencyAuditDetailView.as_view(), name="agency-audit"),
]
