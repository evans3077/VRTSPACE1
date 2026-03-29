from django.contrib import admin

from .models import AuditRequest, Lead


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

# Register your models here.
