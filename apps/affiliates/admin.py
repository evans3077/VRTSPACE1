from django.contrib import admin, messages
from django.utils.html import format_html

from .models import (
    Affiliate,
    AffiliateApplication,
    CommissionLedger,
    Payout,
    ReferralAttribution,
    ReferralClick,
)
from .services import (
    AffiliateError,
    activate_affiliate,
    create_affiliate,
    suspend_affiliate,
)
from .tasks import process_affiliate


@admin.register(Affiliate)
class AffiliateAdmin(admin.ModelAdmin):
    list_display = (
        "display_name",
        "slug",
        "status",
        "stripe_ready",
        "contact_email",
        "activated_at",
        "updated_at",
    )
    list_filter = ("status", "stripe_connect_payouts_enabled", "stripe_connect_onboarded")
    search_fields = ("display_name", "slug", "contact_email", "stripe_connect_account_id")
    readonly_fields = (
        "stripe_connect_account_id",
        "stripe_connect_onboarded",
        "stripe_connect_payouts_enabled",
        "invited_at",
        "activated_at",
        "suspended_at",
        "created_at",
        "updated_at",
    )
    autocomplete_fields = ("user",)
    actions = ("activate_affiliates", "suspend_affiliates", "run_payout_now")

    def get_readonly_fields(self, request, obj=None):
        if obj:
            # Editing — lock the linked user to prevent re-assignment
            return ("user",) + self.readonly_fields
        return self.readonly_fields

    @admin.display(description="Stripe", boolean=True)
    def stripe_ready(self, obj):
        return obj.can_receive_payouts

    @admin.action(description="Activate selected affiliates")
    def activate_affiliates(self, request, queryset):
        count = 0
        for affiliate in queryset:
            activate_affiliate(affiliate)
            count += 1
        self.message_user(request, f"Activated {count} affiliate(s).")

    @admin.action(description="Suspend selected affiliates")
    def suspend_affiliates(self, request, queryset):
        count = 0
        for affiliate in queryset:
            suspend_affiliate(affiliate, note="Suspended via admin bulk action.")
            count += 1
        self.message_user(request, f"Suspended {count} affiliate(s).", level=messages.WARNING)

    @admin.action(description="Run payout sweep for selected affiliates")
    def run_payout_now(self, request, queryset):
        processed = 0
        failed = 0
        for affiliate in queryset:
            try:
                payout = process_affiliate(affiliate.pk)
            except Exception as exc:  # noqa: BLE001
                failed += 1
                self.message_user(request, f"{affiliate.slug}: {exc}", level=messages.ERROR)
                continue
            if payout:
                processed += 1
        self.message_user(
            request,
            f"Processed {processed} payout(s). {failed} failed.",
            level=messages.SUCCESS if not failed else messages.WARNING,
        )


@admin.register(AffiliateApplication)
class AffiliateApplicationAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "audience_size", "status", "created_at")
    list_filter = ("status", "audience_size")
    search_fields = ("name", "email", "website_or_handle")
    readonly_fields = ("submission_context", "reviewed_at", "reviewed_by", "affiliate", "created_at", "updated_at")
    actions = ("approve_applications", "reject_applications")

    @admin.action(description="Approve and create affiliate accounts")
    def approve_applications(self, request, queryset):
        created = 0
        skipped = 0
        for application in queryset.filter(status=AffiliateApplication.Status.PENDING):
            try:
                create_affiliate(
                    display_name=application.name,
                    contact_email=application.email,
                    application=application,
                    created_by=request.user if request.user.is_authenticated else None,
                )
                created += 1
            except AffiliateError as exc:
                skipped += 1
                self.message_user(request, f"{application.email}: {exc}", level=messages.ERROR)
        self.message_user(
            request,
            f"Created {created} affiliate(s). Skipped {skipped}.",
            level=messages.SUCCESS if created else messages.WARNING,
        )

    @admin.action(description="Reject selected applications")
    def reject_applications(self, request, queryset):
        from django.utils import timezone
        count = queryset.filter(status=AffiliateApplication.Status.PENDING).update(
            status=AffiliateApplication.Status.REJECTED,
            reviewed_at=timezone.now(),
            reviewed_by=request.user if request.user.is_authenticated else None,
        )
        self.message_user(request, f"Rejected {count} application(s).")


@admin.register(ReferralClick)
class ReferralClickAdmin(admin.ModelAdmin):
    list_display = ("affiliate", "ip_address", "landing_path_short", "created_at")
    list_filter = ("affiliate",)
    search_fields = ("affiliate__slug", "ip_address", "user_agent", "landing_path")
    readonly_fields = ("affiliate", "ip_address", "user_agent", "referer", "landing_path", "country", "metadata", "created_at", "updated_at")

    @admin.display(description="Landing")
    def landing_path_short(self, obj):
        return (obj.landing_path or "/")[:60]


@admin.register(ReferralAttribution)
class ReferralAttributionAdmin(admin.ModelAdmin):
    list_display = ("user", "affiliate", "fraud_flag", "first_payment_at", "created_at")
    list_filter = ("fraud_flag", "affiliate")
    search_fields = ("user__email", "user__username", "affiliate__slug", "fraud_note")
    autocomplete_fields = ("user", "affiliate", "click")
    readonly_fields = ("created_at", "updated_at")


@admin.register(CommissionLedger)
class CommissionLedgerAdmin(admin.ModelAdmin):
    list_display = (
        "affiliate",
        "kind",
        "status",
        "commission_display",
        "release_at",
        "created_at",
    )
    list_filter = ("status", "kind", "affiliate")
    search_fields = ("affiliate__slug", "stripe_event_id", "stripe_invoice_id", "referred_user__email")
    autocomplete_fields = ("affiliate", "attribution", "referred_user", "payout")
    readonly_fields = (
        "stripe_event_id",
        "stripe_invoice_id",
        "stripe_charge_id",
        "gross_amount_cents",
        "commission_amount_cents",
        "commission_rate_pct",
        "release_at",
        "paid_at",
        "metadata",
        "created_at",
        "updated_at",
    )

    @admin.display(description="Commission")
    def commission_display(self, obj):
        return format_html("${:.2f}", obj.commission_amount_cents / 100)


@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = ("affiliate", "status", "amount_display", "stripe_transfer_id", "created_at")
    list_filter = ("status", "affiliate")
    search_fields = ("affiliate__slug", "stripe_transfer_id", "stripe_destination_account")
    autocomplete_fields = ("affiliate",)
    readonly_fields = (
        "stripe_transfer_id",
        "stripe_destination_account",
        "amount_cents",
        "currency",
        "error_message",
        "initiated_at",
        "completed_at",
        "metadata",
        "created_at",
        "updated_at",
    )

    @admin.display(description="Amount")
    def amount_display(self, obj):
        return format_html("${:.2f}", obj.amount_cents / 100)
