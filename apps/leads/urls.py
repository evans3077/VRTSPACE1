from django.urls import path

from .views import AuditRequestCreateView, ContactLeadCreateView

app_name = "leads"

urlpatterns = [
    path("contact/", ContactLeadCreateView.as_view(), name="contact"),
    path("tools/free-aeo-audit/", AuditRequestCreateView.as_view(), name="free-aeo-audit"),
]
