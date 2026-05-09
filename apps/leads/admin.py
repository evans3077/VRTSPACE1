from django.contrib import admin

from .models import (
    Affiliate,
    AffiliateCommission,
    AffiliateReferral,
    AuditRequest,
    ClientProject,
    Lead,
    UsageRecord,
    WorkspaceCreditLedger,
    WorkspacePlan,
    WorkspaceSubscription,
)


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


@admin.register(WorkspacePlan)
class WorkspacePlanAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "price_label", "is_active", "sort_order")
    list_filter = ("is_active", "recurring_audits_enabled", "export_reports_enabled")
    search_fields = ("name", "slug", "stripe_price_id")


@admin.register(WorkspaceSubscription)
class WorkspaceSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "plan", "status", "current_period_end", "updated_at")
    list_filter = ("status", "plan")
    search_fields = ("user__username", "user__email", "stripe_customer_id", "stripe_subscription_id")
    autocomplete_fields = ("user", "plan")


@admin.register(UsageRecord)
class UsageRecordAdmin(admin.ModelAdmin):
    list_display = ("user", "metric", "quantity", "period_start", "period_end", "updated_at")
    list_filter = ("metric", "plan")
    search_fields = ("user__username", "user__email")
    autocomplete_fields = ("user", "plan")


@admin.register(WorkspaceCreditLedger)
class WorkspaceCreditLedgerAdmin(admin.ModelAdmin):
    list_display = ("user", "category", "kind", "delta", "period_start", "plan", "updated_at")
    list_filter = ("category", "kind", "plan")
    search_fields = ("user__username", "user__email", "reference_key", "note")
    autocomplete_fields = ("user", "plan", "subscription", "project")


@admin.register(Affiliate)
class AffiliateAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "email", "commission_rate_first_pct", "commission_rate_recurring_pct", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "email", "code")
    prepopulated_fields = {"code": ("name",)}


@admin.register(AffiliateReferral)
class AffiliateReferralAdmin(admin.ModelAdmin):
    list_display = ("affiliate", "referred_user", "ref_code_used", "converted_at", "created_at")
    list_filter = ("affiliate",)
    search_fields = ("referred_user__email", "ref_code_used", "affiliate__code")
    readonly_fields = ("created_at",)


@admin.register(AffiliateCommission)
class AffiliateCommissionAdmin(admin.ModelAdmin):
    list_display = (
        "affiliate", "referred_user", "plan_slug", "amount_cents", "commission_cents",
        "commission_rate_pct", "is_recurring", "period_year", "period_month", "paid_out",
    )
    list_filter = ("affiliate", "is_recurring", "paid_out", "period_year", "period_month")
    search_fields = ("affiliate__code", "referred_user__email", "stripe_checkout_session_id")
    readonly_fields = ("created_at",)
