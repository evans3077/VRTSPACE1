from django.contrib import admin

from .models import AuditRequest, ClientProject, Lead


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "interest_area", "score", "created_at")
    list_filter = ("interest_area", "consent_to_contact")
    search_fields = ("name", "email", "company")


@admin.register(AuditRequest)
class AuditRequestAdmin(admin.ModelAdmin):
    list_display = ("website", "email", "monthly_leads_goal", "score", "status")
    list_filter = ("status",)
    search_fields = ("website", "email", "company_name")


@admin.register(ClientProject)
class ClientProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "normalized_domain", "stage", "latest_score", "updated_at")
    list_filter = ("stage",)
    search_fields = ("name", "normalized_domain", "contact_email")
    autocomplete_fields = ("audit_request", "latest_audit_run")

# Register your models here.
