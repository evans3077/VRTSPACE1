import logging
from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal

from django.core.mail import EmailMessage
from django.db import IntegrityError, transaction

logger = logging.getLogger(__name__)


def get_affiliate_by_code(code):
    from .models import Affiliate
    if not code:
        return None
    return Affiliate.objects.filter(code=code, is_active=True).first()


def record_affiliate_referral(user, ref_code):
    """
    Associate a newly registered user with the affiliate whose code they used.
    Idempotent — silently no-ops if the referral already exists or the code is invalid.
    """
    affiliate = get_affiliate_by_code(ref_code)
    if not affiliate:
        return None

    from .models import AffiliateReferral
    try:
        with transaction.atomic():
            referral = AffiliateReferral.objects.create(
                affiliate=affiliate,
                referred_user=user,
                ref_code_used=ref_code,
            )
        return referral
    except IntegrityError:
        return AffiliateReferral.objects.filter(referred_user=user).first()


def record_affiliate_commission(user, stripe_session_id, plan_slug, amount_cents, is_recurring=False):
    """
    Record a commission for the affiliate who referred this user.
    Uses stripe_session_id as the dedupe key — safe to call multiple times.
    Returns the AffiliateCommission or None if no referral exists.
    """
    from .models import AffiliateCommission, AffiliateReferral

    try:
        referral = AffiliateReferral.objects.select_related("affiliate").get(referred_user=user)
    except AffiliateReferral.DoesNotExist:
        return None

    affiliate = referral.affiliate
    rate = affiliate.commission_rate_recurring_pct if is_recurring else affiliate.commission_rate_first_pct
    commission_cents = int(Decimal(amount_cents) * rate / 100)

    now = datetime.now(tz=dt_timezone.utc)

    try:
        with transaction.atomic():
            commission = AffiliateCommission.objects.create(
                affiliate=affiliate,
                referral=referral,
                referred_user=user,
                stripe_checkout_session_id=stripe_session_id,
                plan_slug=plan_slug,
                amount_cents=amount_cents,
                commission_cents=commission_cents,
                commission_rate_pct=rate,
                is_recurring=is_recurring,
                period_year=now.year,
                period_month=now.month,
            )

        # Mark referral as converted on first payment
        if not is_recurring and not referral.converted_at:
            referral.converted_at = now
            referral.save(update_fields=["converted_at"])

        return commission
    except IntegrityError:
        return AffiliateCommission.objects.filter(stripe_checkout_session_id=stripe_session_id).first()


def get_monthly_statement_data(affiliate, year, month):
    """
    Aggregate commissions for a given affiliate and calendar month.
    Returns a dict suitable for the statement email.
    """
    from .models import AffiliateCommission, AffiliateReferral

    commissions = AffiliateCommission.objects.filter(
        affiliate=affiliate,
        period_year=year,
        period_month=month,
    ).select_related("referred_user")

    total_commission_cents = sum(c.commission_cents for c in commissions)
    signups_this_month = AffiliateReferral.objects.filter(
        affiliate=affiliate,
        created_at__year=year,
        created_at__month=month,
    ).count()
    conversions_this_month = sum(1 for c in commissions if not c.is_recurring)
    renewals_this_month = sum(1 for c in commissions if c.is_recurring)
    total_signups = AffiliateReferral.objects.filter(affiliate=affiliate).count()
    total_conversions = AffiliateReferral.objects.filter(
        affiliate=affiliate,
        converted_at__isnull=False,
    ).count()

    return {
        "affiliate": affiliate,
        "year": year,
        "month": month,
        "commissions": list(commissions),
        "signups_this_month": signups_this_month,
        "conversions_this_month": conversions_this_month,
        "renewals_this_month": renewals_this_month,
        "total_commission_cents": total_commission_cents,
        "total_commission_dollars": total_commission_cents / 100,
        "total_signups": total_signups,
        "total_conversions": total_conversions,
    }


def send_affiliate_monthly_statement(affiliate, year, month):
    """
    Email the monthly payout statement to the affiliate.
    """
    data = get_monthly_statement_data(affiliate, year, month)
    month_label = date(year, month, 1).strftime("%B %Y")
    total = data["total_commission_dollars"]

    subject = f"[VRT SPACE] Your {month_label} affiliate statement"

    lines = [
        f"Hi {affiliate.name},",
        "",
        f"Here's your affiliate summary for {month_label}.",
        "",
        "--- Activity ---",
        f"New sign-ups via your link: {data['signups_this_month']}",
        f"New paying conversions:      {data['conversions_this_month']}",
        f"Renewal commissions:         {data['renewals_this_month']}",
        "",
        "--- Earnings ---",
        f"Commissions this month:  ${total:.2f}",
        "",
        "--- All-time totals ---",
        f"Total sign-ups:    {data['total_signups']}",
        f"Total conversions: {data['total_conversions']}",
        "",
    ]

    if data["commissions"]:
        lines.append("--- Commission detail ---")
        for c in data["commissions"]:
            label = "renewal" if c.is_recurring else "new"
            plan = c.plan_slug.capitalize() if c.plan_slug else "plan"
            lines.append(
                f"  {plan} ({label})  ${c.amount_cents / 100:.2f} charged → "
                f"${c.commission_cents / 100:.2f} commission ({c.commission_rate_pct}%)"
            )
        lines.append("")

    lines += [
        "Payouts are processed manually at the end of each month. "
        "If you have questions reply to this email.",
        "",
        "Thank you for spreading the word,",
        "VRT SPACE team",
    ]

    body = "\n".join(lines)

    try:
        msg = EmailMessage(
            subject=subject,
            body=body,
            to=[affiliate.email],
        )
        msg.send()
        return True
    except Exception as exc:
        logger.error("Affiliate statement email failed for %s: %s", affiliate.code, exc)
        return False
