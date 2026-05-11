"""Core business logic for the affiliate program.

Kept in one module to mirror the rest of the codebase (apps/leads/billing.py,
apps/tools/services.py). Anything that touches Stripe Connect, commission math,
attribution, or fraud lives here.
"""
from __future__ import annotations

import logging
import secrets
from datetime import timedelta
from decimal import Decimal
from typing import Optional

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from django.utils.text import slugify

from .models import (
    Affiliate,
    AffiliateApplication,
    CommissionLedger,
    Payout,
    ReferralAttribution,
    ReferralClick,
)

logger = logging.getLogger(__name__)

STRIPE_API_BASE = "https://api.stripe.com/v1"
SLUG_MAX_LENGTH = 64


class AffiliateError(Exception):
    """Raised for any affiliate-program business rule violation."""


# ---------------------------------------------------------------------------
# Slug + identity helpers
# ---------------------------------------------------------------------------


def generate_unique_slug(seed: str) -> str:
    """Slugify the seed and append digits if collisions exist."""
    base = slugify(seed)[:SLUG_MAX_LENGTH - 6] or "partner"
    candidate = base
    suffix = 1
    while Affiliate.objects.filter(slug=candidate).exists():
        candidate = f"{base}-{suffix}"
        suffix += 1
        if suffix > 999:
            candidate = f"{base}-{secrets.token_hex(3)}"
            break
    return candidate[:SLUG_MAX_LENGTH]


def _email_domain(email: str) -> str:
    if not email or "@" not in email:
        return ""
    return email.split("@", 1)[1].strip().lower()


def _client_ip(request) -> Optional[str]:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip() or None
    return request.META.get("REMOTE_ADDR") or None


# ---------------------------------------------------------------------------
# Click tracking
# ---------------------------------------------------------------------------


def record_click(affiliate: Affiliate, request, landing_path: str = "") -> ReferralClick:
    """Persist a click + stamp the referral cookie. Called from /r/<slug>/."""
    ua = (request.META.get("HTTP_USER_AGENT") or "")[:512]
    referer = (request.META.get("HTTP_REFERER") or "")[:512]
    return ReferralClick.objects.create(
        affiliate=affiliate,
        ip_address=_client_ip(request),
        user_agent=ua,
        referer=referer,
        landing_path=landing_path[:512] if landing_path else "",
    )


def cookie_max_age_seconds() -> int:
    return int(timedelta(days=settings.AFFILIATE_COOKIE_MAX_AGE_DAYS).total_seconds())


# ---------------------------------------------------------------------------
# Attribution at signup time
# ---------------------------------------------------------------------------


def _check_fraud_signals(affiliate: Affiliate, user, signup_ip: Optional[str]) -> tuple[str, str]:
    """Return (fraud_flag, fraud_note) for this attribution candidate."""
    aff_email = (affiliate.contact_email or "").lower()
    user_email = (getattr(user, "email", "") or "").lower()
    if aff_email and user_email and _email_domain(aff_email) == _email_domain(user_email):
        return (
            ReferralAttribution.FraudFlag.SAME_DOMAIN,
            f"Referred email shares domain with affiliate ({_email_domain(aff_email)}).",
        )

    if signup_ip:
        recent_clicks = ReferralClick.objects.filter(
            affiliate=affiliate,
            ip_address=signup_ip,
            created_at__gte=timezone.now() - timedelta(days=settings.AFFILIATE_COOKIE_MAX_AGE_DAYS),
        ).exists()
        # If the affiliate itself ever clicked from this IP we don't know,
        # but a same-IP signup is worth a human glance.
        if recent_clicks:
            # Only flag — don't block.
            return (
                ReferralAttribution.FraudFlag.SAME_IP,
                f"Signup IP {signup_ip} matched a prior click on this affiliate's link.",
            )
    return (ReferralAttribution.FraudFlag.NONE, "")


def attribute_signup(
    *,
    user,
    affiliate_slug: str,
    signup_ip: Optional[str] = None,
    click: Optional[ReferralClick] = None,
) -> Optional[ReferralAttribution]:
    """Link a freshly-created user to the affiliate from their referral cookie.

    Idempotent — returns the existing attribution if one already exists.
    Returns None if the slug doesn't resolve to an active affiliate.
    """
    if not affiliate_slug:
        return None

    affiliate = Affiliate.objects.filter(
        slug=affiliate_slug,
        status=Affiliate.Status.ACTIVE,
    ).first()
    if not affiliate:
        return None

    existing = ReferralAttribution.objects.filter(user=user).first()
    if existing:
        return existing

    fraud_flag, fraud_note = _check_fraud_signals(affiliate, user, signup_ip)
    if fraud_flag == ReferralAttribution.FraudFlag.SAME_DOMAIN:
        logger.info(
            "Affiliate self-referral blocked: affiliate=%s user=%s domain=%s",
            affiliate.slug,
            getattr(user, "email", ""),
            _email_domain(getattr(user, "email", "") or ""),
        )
        return None

    attribution = ReferralAttribution.objects.create(
        affiliate=affiliate,
        user=user,
        click=click,
        signup_ip=signup_ip,
        fraud_flag=fraud_flag,
        fraud_note=fraud_note,
    )
    try:
        from .notifications import notify_new_signup
        notify_new_signup(attribution)
    except Exception:
        logger.exception("notify_new_signup failed for attribution %s", attribution.pk)
    return attribution


# ---------------------------------------------------------------------------
# Commission calculation
# ---------------------------------------------------------------------------


def _release_at() -> timezone.datetime:
    return timezone.now() + timedelta(days=settings.AFFILIATE_PAYOUT_HOLD_DAYS)


def _calc_commission_cents(gross_cents: int, rate_pct: int) -> int:
    if gross_cents <= 0 or rate_pct <= 0:
        return 0
    # Bankers' math via Decimal — cents-precise, no float drift.
    amount = (Decimal(gross_cents) * Decimal(rate_pct)) / Decimal(100)
    return int(amount.quantize(Decimal("1")))


def record_commission_for_payment(
    *,
    user,
    stripe_event_id: str,
    gross_amount_cents: int,
    currency: str = "usd",
    is_first_payment: bool,
    stripe_invoice_id: str = "",
    stripe_charge_id: str = "",
    metadata: Optional[dict] = None,
) -> Optional[CommissionLedger]:
    """Create a CommissionLedger entry if the user has a clean attribution.

    Idempotent on stripe_event_id (unique). Returns None if no attribution
    exists or the attribution is flagged for rejection.
    """
    if not stripe_event_id:
        raise AffiliateError("stripe_event_id is required for commission recording.")
    if gross_amount_cents <= 0:
        return None

    attribution = (
        ReferralAttribution.objects
        .select_related("affiliate")
        .filter(user=user)
        .first()
    )
    if not attribution:
        return None
    if attribution.fraud_flag == ReferralAttribution.FraudFlag.REJECTED:
        return None
    affiliate = attribution.affiliate
    if affiliate.status not in {Affiliate.Status.ACTIVE, Affiliate.Status.SUSPENDED}:
        # Revoked → no commission. Suspended → still record, but flag will keep them off payout.
        return None

    existing = CommissionLedger.objects.filter(stripe_event_id=stripe_event_id).first()
    if existing:
        return existing

    if is_first_payment:
        kind = CommissionLedger.Kind.FIRST_PAYMENT
        rate = settings.AFFILIATE_COMMISSION_FIRST_PAYMENT_PCT
    else:
        kind = CommissionLedger.Kind.RECURRING
        rate = settings.AFFILIATE_COMMISSION_RECURRING_PCT

    commission_cents = _calc_commission_cents(gross_amount_cents, rate)
    if commission_cents <= 0:
        return None

    initial_status = CommissionLedger.Status.PENDING
    if (
        attribution.fraud_flag != ReferralAttribution.FraudFlag.NONE
        or affiliate.status == Affiliate.Status.SUSPENDED
    ):
        initial_status = CommissionLedger.Status.ON_HOLD

    commission = CommissionLedger.objects.create(
        affiliate=affiliate,
        attribution=attribution,
        referred_user=user,
        kind=kind,
        status=initial_status,
        gross_amount_cents=gross_amount_cents,
        commission_rate_pct=rate,
        commission_amount_cents=commission_cents,
        currency=currency,
        stripe_event_id=stripe_event_id,
        stripe_invoice_id=stripe_invoice_id,
        stripe_charge_id=stripe_charge_id,
        release_at=_release_at(),
        metadata=metadata or {},
    )

    if is_first_payment and not attribution.first_payment_at:
        attribution.first_payment_at = timezone.now()
        attribution.save(update_fields=["first_payment_at", "updated_at"])

    try:
        from .notifications import notify_commission_earned
        notify_commission_earned(commission)
    except Exception:
        logger.exception("notify_commission_earned failed for commission %s", commission.pk)

    return commission


# ---------------------------------------------------------------------------
# Stripe Connect (Express accounts)
# ---------------------------------------------------------------------------


def _stripe_post(path: str, data: dict, *, stripe_account: str = "") -> dict:
    if not settings.STRIPE_ENABLED:
        raise AffiliateError("Stripe billing is not configured.")
    headers = {}
    if stripe_account:
        headers["Stripe-Account"] = stripe_account
    response = requests.post(
        f"{STRIPE_API_BASE}{path}",
        auth=(settings.STRIPE_SECRET_KEY, ""),
        data=data,
        headers=headers,
        timeout=20,
    )
    if response.status_code >= 400:
        raise AffiliateError(f"Stripe error: {response.text[:300]}")
    return response.json()


def _stripe_get(path: str) -> dict:
    if not settings.STRIPE_ENABLED:
        raise AffiliateError("Stripe billing is not configured.")
    response = requests.get(
        f"{STRIPE_API_BASE}{path}",
        auth=(settings.STRIPE_SECRET_KEY, ""),
        timeout=20,
    )
    if response.status_code >= 400:
        raise AffiliateError(f"Stripe error: {response.text[:300]}")
    return response.json()


def ensure_stripe_connect_account(affiliate: Affiliate) -> str:
    """Create an Express account for the affiliate if one doesn't exist."""
    if affiliate.stripe_connect_account_id:
        return affiliate.stripe_connect_account_id
    payload = {
        "type": "express",
        "email": affiliate.contact_email,
        "capabilities[transfers][requested]": "true",
        "metadata[affiliate_slug]": affiliate.slug,
        "metadata[affiliate_id]": str(affiliate.pk),
    }
    data = _stripe_post("/accounts", payload)
    account_id = data.get("id", "")
    if not account_id:
        raise AffiliateError("Stripe did not return an account id.")
    affiliate.stripe_connect_account_id = account_id
    affiliate.save(update_fields=["stripe_connect_account_id", "updated_at"])
    return account_id


def build_connect_onboarding_link(affiliate: Affiliate, *, return_url: str, refresh_url: str) -> str:
    """Generate a Stripe-hosted onboarding link for the affiliate."""
    account_id = ensure_stripe_connect_account(affiliate)
    data = _stripe_post(
        "/account_links",
        {
            "account": account_id,
            "type": "account_onboarding",
            "return_url": return_url,
            "refresh_url": refresh_url,
        },
    )
    url = data.get("url", "")
    if not url:
        raise AffiliateError("Stripe did not return an onboarding URL.")
    return url


def refresh_connect_account_status(affiliate: Affiliate) -> Affiliate:
    """Pull the latest account state from Stripe and update local flags."""
    if not affiliate.stripe_connect_account_id:
        return affiliate
    data = _stripe_get(f"/accounts/{affiliate.stripe_connect_account_id}")
    payouts_enabled = bool(data.get("payouts_enabled"))
    details_submitted = bool(data.get("details_submitted"))
    affiliate.stripe_connect_payouts_enabled = payouts_enabled
    affiliate.stripe_connect_onboarded = details_submitted
    affiliate.save(
        update_fields=[
            "stripe_connect_payouts_enabled",
            "stripe_connect_onboarded",
            "updated_at",
        ]
    )
    return affiliate


def create_stripe_transfer(payout: Payout) -> Payout:
    """Issue a Stripe Connect transfer for an aggregated payout."""
    if not payout.affiliate.can_receive_payouts:
        raise AffiliateError("Affiliate is not eligible to receive payouts yet.")
    if payout.amount_cents <= 0:
        raise AffiliateError("Payout amount must be greater than zero.")

    idempotency_key = f"payout-{payout.pk}"
    response = requests.post(
        f"{STRIPE_API_BASE}/transfers",
        auth=(settings.STRIPE_SECRET_KEY, ""),
        data={
            "amount": payout.amount_cents,
            "currency": payout.currency,
            "destination": payout.affiliate.stripe_connect_account_id,
            "metadata[payout_id]": str(payout.pk),
            "metadata[affiliate_slug]": payout.affiliate.slug,
        },
        headers={"Idempotency-Key": idempotency_key},
        timeout=20,
    )
    if response.status_code >= 400:
        payout.status = Payout.Status.FAILED
        payout.error_message = response.text[:500]
        payout.save(update_fields=["status", "error_message", "updated_at"])
        raise AffiliateError(f"Stripe transfer failed: {response.text[:300]}")
    data = response.json()
    payout.stripe_transfer_id = data.get("id", "")
    payout.stripe_destination_account = data.get("destination", "")
    payout.status = Payout.Status.PAID
    payout.completed_at = timezone.now()
    payout.metadata = data
    payout.save(
        update_fields=[
            "stripe_transfer_id",
            "stripe_destination_account",
            "status",
            "completed_at",
            "metadata",
            "updated_at",
        ]
    )
    return payout


# ---------------------------------------------------------------------------
# Payout processing
# ---------------------------------------------------------------------------


def releasable_commissions_qs(affiliate: Optional[Affiliate] = None):
    qs = CommissionLedger.objects.filter(
        status=CommissionLedger.Status.PENDING,
        release_at__lte=timezone.now(),
    )
    if affiliate is not None:
        qs = qs.filter(affiliate=affiliate)
    return qs


@transaction.atomic
def assemble_payout_for_affiliate(affiliate: Affiliate) -> Optional[Payout]:
    """Bundle all releasable commissions for one affiliate into a single Payout."""
    qs = (
        releasable_commissions_qs(affiliate)
        .select_for_update(skip_locked=True)
    )
    commissions = list(qs)
    if not commissions:
        return None
    if not affiliate.can_receive_payouts:
        # Mark them approved-but-unpaid so they don't keep cycling.
        for c in commissions:
            c.status = CommissionLedger.Status.APPROVED
        CommissionLedger.objects.bulk_update(commissions, ["status"])
        return None

    total = sum(c.commission_amount_cents for c in commissions)
    currency = commissions[0].currency
    payout = Payout.objects.create(
        affiliate=affiliate,
        amount_cents=total,
        currency=currency,
        status=Payout.Status.QUEUED,
    )
    for c in commissions:
        c.payout = payout
        c.status = CommissionLedger.Status.APPROVED
    CommissionLedger.objects.bulk_update(commissions, ["payout", "status"])
    return payout


def process_payout(payout: Payout) -> Payout:
    """Push a queued payout through Stripe and mark linked commissions paid."""
    if payout.status != Payout.Status.QUEUED:
        return payout
    payout.status = Payout.Status.PROCESSING
    payout.initiated_at = timezone.now()
    payout.save(update_fields=["status", "initiated_at", "updated_at"])
    try:
        create_stripe_transfer(payout)
    except AffiliateError:
        raise
    now = timezone.now()
    payout.commissions.update(status=CommissionLedger.Status.PAID, paid_at=now)
    try:
        from .notifications import notify_payout_sent
        notify_payout_sent(payout)
    except Exception:
        logger.exception("notify_payout_sent failed for payout %s", payout.pk)
    return payout


# ---------------------------------------------------------------------------
# Affiliate provisioning (admin-side)
# ---------------------------------------------------------------------------


@transaction.atomic
def create_affiliate(
    *,
    display_name: str,
    contact_email: str,
    slug: Optional[str] = None,
    application: Optional[AffiliateApplication] = None,
    created_by=None,
) -> Affiliate:
    User = get_user_model()
    contact_email = contact_email.strip().lower()
    if not contact_email:
        raise AffiliateError("contact_email is required.")
    if not display_name.strip():
        raise AffiliateError("display_name is required.")

    user, _created = User.objects.get_or_create(
        email=contact_email,
        defaults={"username": contact_email[:150]},
    )
    if hasattr(user, "is_affiliate"):
        user.is_affiliate = True
        user.save(update_fields=["is_affiliate"])

    if Affiliate.objects.filter(user=user).exists():
        raise AffiliateError("This user already has an affiliate profile.")

    resolved_slug = slug.strip() if slug else generate_unique_slug(display_name)
    if Affiliate.objects.filter(slug=resolved_slug).exists():
        raise AffiliateError(f"Slug '{resolved_slug}' is already taken.")

    affiliate = Affiliate.objects.create(
        user=user,
        slug=resolved_slug,
        display_name=display_name.strip(),
        contact_email=contact_email,
        status=Affiliate.Status.PENDING,
        invited_at=timezone.now(),
    )
    if application:
        application.status = AffiliateApplication.Status.APPROVED
        application.reviewed_at = timezone.now()
        application.reviewed_by = created_by
        application.affiliate = affiliate
        application.save(
            update_fields=[
                "status",
                "reviewed_at",
                "reviewed_by",
                "affiliate",
                "updated_at",
            ]
        )
    return affiliate


def activate_affiliate(affiliate: Affiliate) -> Affiliate:
    affiliate.status = Affiliate.Status.ACTIVE
    affiliate.activated_at = timezone.now()
    affiliate.save(update_fields=["status", "activated_at", "updated_at"])
    return affiliate


def suspend_affiliate(affiliate: Affiliate, *, note: str = "") -> Affiliate:
    affiliate.status = Affiliate.Status.SUSPENDED
    affiliate.suspended_at = timezone.now()
    if note:
        affiliate.notes = (affiliate.notes + "\n" if affiliate.notes else "") + note
    affiliate.save(update_fields=["status", "suspended_at", "notes", "updated_at"])
    return affiliate


# ---------------------------------------------------------------------------
# Portal aggregates
# ---------------------------------------------------------------------------


def portal_summary(affiliate: Affiliate) -> dict:
    """Roll-up numbers shown on the affiliate's dashboard."""
    commissions = CommissionLedger.objects.filter(affiliate=affiliate)
    pending = commissions.filter(
        status__in=[
            CommissionLedger.Status.PENDING,
            CommissionLedger.Status.ON_HOLD,
        ]
    ).aggregate(total=Sum("commission_amount_cents"))["total"] or 0
    approved = commissions.filter(
        status=CommissionLedger.Status.APPROVED
    ).aggregate(total=Sum("commission_amount_cents"))["total"] or 0
    paid = commissions.filter(
        status=CommissionLedger.Status.PAID
    ).aggregate(total=Sum("commission_amount_cents"))["total"] or 0

    clicks_total = ReferralClick.objects.filter(affiliate=affiliate).count()
    signups_total = ReferralAttribution.objects.filter(affiliate=affiliate).count()
    paid_signups_total = ReferralAttribution.objects.filter(
        affiliate=affiliate,
        first_payment_at__isnull=False,
    ).count()

    last_30 = timezone.now() - timedelta(days=30)
    clicks_30 = ReferralClick.objects.filter(affiliate=affiliate, created_at__gte=last_30).count()
    signups_30 = ReferralAttribution.objects.filter(affiliate=affiliate, created_at__gte=last_30).count()
    paid_30 = ReferralAttribution.objects.filter(
        affiliate=affiliate,
        first_payment_at__gte=last_30,
    ).count()

    return {
        "earnings": {
            "pending_cents": pending,
            "approved_cents": approved,
            "paid_cents": paid,
            "total_cents": pending + approved + paid,
        },
        "funnel_all_time": {
            "clicks": clicks_total,
            "signups": signups_total,
            "paid": paid_signups_total,
        },
        "funnel_30d": {
            "clicks": clicks_30,
            "signups": signups_30,
            "paid": paid_30,
        },
    }
