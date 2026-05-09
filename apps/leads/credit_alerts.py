"""Credit usage alert thresholds and helpers.

Triggered server-side after a successful credit debit. Determines whether the
user has just crossed one of the workspace credit usage thresholds
(50/75/90/100%) for the current monthly period and records each alert
exactly once via the CreditAlert model's unique constraint.
"""

from django.db import IntegrityError, transaction

from .models import CreditAlert

ALERT_THRESHOLDS = (50, 75, 90, 100)


def get_credit_usage_percentage(balance):
    if not balance:
        return None
    if balance.get("unlimited"):
        return None
    granted = balance.get("granted") or 0
    used = balance.get("used") or 0
    if granted <= 0:
        return None
    pct = int((used * 100) // granted)
    return min(pct, 100)


def get_alert_band(percentage):
    if percentage is None:
        return None
    crossed = [t for t in ALERT_THRESHOLDS if percentage >= t]
    return max(crossed) if crossed else None


def evaluate_credit_alert_thresholds(user, *, balance, period_start, period_end):
    percentage = get_credit_usage_percentage(balance)
    if percentage is None:
        return []
    crossed = [t for t in ALERT_THRESHOLDS if percentage >= t]
    if not crossed:
        return []
    already_alerted = set(
        CreditAlert.objects.filter(
            user=user,
            period_start=period_start,
            threshold_pct__in=crossed,
        ).values_list("threshold_pct", flat=True)
    )
    return [t for t in crossed if t not in already_alerted]


def record_credit_alert(
    user,
    *,
    threshold_pct,
    balance,
    period_start,
    period_end,
    subscription=None,
    channel=CreditAlert.Channel.EMAIL,
    delivered=True,
    error_message="",
):
    try:
        with transaction.atomic():
            return CreditAlert.objects.create(
                user=user,
                subscription=subscription,
                period_start=period_start,
                period_end=period_end,
                threshold_pct=threshold_pct,
                used_at_alert=balance.get("used") or 0,
                granted_at_alert=balance.get("granted") or 0,
                channel=channel,
                delivered=delivered,
                error_message=error_message[:1000] if error_message else "",
            )
    except IntegrityError:
        return None
