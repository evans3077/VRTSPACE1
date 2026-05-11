from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import TimestampedModel


class Affiliate(TimestampedModel):
    """A vetted partner who earns commission for referred paid signups."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending onboarding"
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        REVOKED = "revoked", "Revoked"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="affiliate_profile",
    )
    slug = models.SlugField(
        max_length=64,
        unique=True,
        help_text="Public referral handle used in /r/<slug>/ URLs.",
    )
    display_name = models.CharField(max_length=120)
    contact_email = models.EmailField()
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
    )
    stripe_connect_account_id = models.CharField(max_length=120, blank=True)
    stripe_connect_onboarded = models.BooleanField(default=False)
    stripe_connect_payouts_enabled = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    invited_at = models.DateTimeField(null=True, blank=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    suspended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("display_name",)

    def __str__(self):
        return f"{self.display_name} (/r/{self.slug}/)"

    @property
    def is_active(self):
        return self.status == self.Status.ACTIVE

    @property
    def can_receive_payouts(self):
        return (
            self.is_active
            and self.stripe_connect_onboarded
            and self.stripe_connect_payouts_enabled
            and bool(self.stripe_connect_account_id)
        )


class ReferralClick(TimestampedModel):
    """Every visit to /r/<slug>/ — the click-funnel top metric."""

    affiliate = models.ForeignKey(
        Affiliate,
        on_delete=models.CASCADE,
        related_name="clicks",
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True)
    referer = models.CharField(max_length=512, blank=True)
    landing_path = models.CharField(max_length=512, blank=True)
    country = models.CharField(max_length=2, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["affiliate", "-created_at"]),
        ]

    def __str__(self):
        return f"Click → {self.affiliate.slug} @ {self.created_at:%Y-%m-%d}"


class ReferralAttribution(TimestampedModel):
    """Links a signed-up user to the affiliate that referred them."""

    class FraudFlag(models.TextChoices):
        NONE = "none", "Clean"
        SAME_DOMAIN = "same_domain", "Same email domain as affiliate"
        SAME_IP = "same_ip", "Same IP as affiliate"
        MANUAL_REVIEW = "manual_review", "Flagged for manual review"
        REJECTED = "rejected", "Rejected"

    affiliate = models.ForeignKey(
        Affiliate,
        on_delete=models.CASCADE,
        related_name="attributions",
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="referral_attribution",
    )
    click = models.ForeignKey(
        ReferralClick,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="attributions",
    )
    signup_ip = models.GenericIPAddressField(null=True, blank=True)
    fraud_flag = models.CharField(
        max_length=24,
        choices=FraudFlag.choices,
        default=FraudFlag.NONE,
    )
    fraud_note = models.CharField(max_length=255, blank=True)
    first_payment_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["affiliate", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.user} ← {self.affiliate.slug}"


class CommissionLedger(TimestampedModel):
    """Each commission line — one per qualifying Stripe payment event."""

    class Kind(models.TextChoices):
        FIRST_PAYMENT = "first_payment", "First payment"
        RECURRING = "recurring", "Recurring"
        ADJUSTMENT = "adjustment", "Adjustment"
        REVERSAL = "reversal", "Reversal"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending hold"
        APPROVED = "approved", "Approved for payout"
        PAID = "paid", "Paid"
        VOIDED = "voided", "Voided"
        ON_HOLD = "on_hold", "On hold for review"

    affiliate = models.ForeignKey(
        Affiliate,
        on_delete=models.PROTECT,
        related_name="commissions",
    )
    attribution = models.ForeignKey(
        ReferralAttribution,
        on_delete=models.PROTECT,
        related_name="commissions",
    )
    referred_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="generated_commissions",
    )
    kind = models.CharField(max_length=16, choices=Kind.choices)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
    )
    gross_amount_cents = models.PositiveIntegerField(
        help_text="Stripe payment amount in cents (what the customer paid).",
    )
    commission_rate_pct = models.PositiveSmallIntegerField(
        help_text="Rate applied (e.g. 25 for first payment, 15 for recurring).",
    )
    commission_amount_cents = models.PositiveIntegerField(
        help_text="Commission owed in cents (gross × rate).",
    )
    currency = models.CharField(max_length=8, default="usd")
    stripe_event_id = models.CharField(max_length=120, unique=True)
    stripe_invoice_id = models.CharField(max_length=120, blank=True)
    stripe_charge_id = models.CharField(max_length=120, blank=True)
    release_at = models.DateTimeField(
        help_text="When the 30-day hold clears and the commission becomes payable.",
    )
    paid_at = models.DateTimeField(null=True, blank=True)
    payout = models.ForeignKey(
        "Payout",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="commissions",
    )
    note = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["affiliate", "status"]),
            models.Index(fields=["status", "release_at"]),
        ]

    def __str__(self):
        return f"{self.affiliate.slug} · {self.get_kind_display()} · {self.commission_amount_cents}c"

    @property
    def is_releasable(self):
        if self.status != self.Status.PENDING:
            return False
        return timezone.now() >= self.release_at


class Payout(TimestampedModel):
    """Aggregated Stripe Connect transfer to an affiliate."""

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        PROCESSING = "processing", "Processing"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"
        CANCELED = "canceled", "Canceled"

    affiliate = models.ForeignKey(
        Affiliate,
        on_delete=models.PROTECT,
        related_name="payouts",
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.QUEUED,
    )
    amount_cents = models.PositiveIntegerField()
    currency = models.CharField(max_length=8, default="usd")
    stripe_transfer_id = models.CharField(max_length=120, blank=True)
    stripe_destination_account = models.CharField(max_length=120, blank=True)
    error_message = models.TextField(blank=True)
    initiated_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["affiliate", "status"]),
        ]

    def __str__(self):
        return f"Payout {self.affiliate.slug} · {self.amount_cents}c · {self.status}"


class AffiliateApplication(TimestampedModel):
    """Public submissions from people who want to join the affiliate program."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    class AudienceSize(models.TextChoices):
        UNDER_1K = "under_1k", "Under 1,000"
        TO_10K = "1k_10k", "1,000 – 10,000"
        TO_100K = "10k_100k", "10,000 – 100,000"
        OVER_100K = "over_100k", "100,000+"

    name = models.CharField(max_length=160)
    email = models.EmailField()
    website_or_handle = models.CharField(max_length=255)
    audience_size = models.CharField(
        max_length=24,
        choices=AudienceSize.choices,
        blank=True,
    )
    promotion_plan = models.TextField(blank=True)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
    )
    review_notes = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_affiliate_applications",
    )
    affiliate = models.ForeignKey(
        Affiliate,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="application",
    )
    submission_context = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.name} ({self.email}) — {self.get_status_display()}"


def default_release_at():
    return timezone.now() + timedelta(days=settings.AFFILIATE_PAYOUT_HOLD_DAYS)
