"""Email notifications for lead/billing/credit events."""

from django.conf import settings
from django.core.mail import EmailMessage

from apps.tools.audit_exports import build_absolute_app_url


CREDIT_ALERT_HEADLINES = {
    50: "You've used 50% of this month's credits",
    75: "You've used 75% of this month's credits",
    90: "You're at 90% of this month's credits",
    100: "You've used all of this month's credits",
}

CREDIT_ALERT_BODY_LEAD = {
    50: "You're halfway through your monthly credit allowance. Plenty of headroom, but worth a glance to make sure your team's spend matches your priorities.",
    75: "Three quarters of your monthly credits are spent. Now is a good time to plan the rest of the month or top up if you expect more activity.",
    90: "You have only 10% of this month's credits left. Top up to keep audits, SEO refreshes, and AEO analyses running without interruption.",
    100: "You've used your full monthly credit allowance. Your subscription stays active, but new credit-spending actions are paused until you top up or your plan refreshes next cycle.",
}


def send_credit_alert_email(user, *, threshold_pct, balance, account_url=None):
    recipient = (getattr(user, "email", "") or "").strip()
    if not recipient:
        return 0

    if account_url is None:
        account_url = build_absolute_app_url("/account/#billing")

    headline = CREDIT_ALERT_HEADLINES.get(threshold_pct, f"You've used {threshold_pct}% of this month's credits")
    lead = CREDIT_ALERT_BODY_LEAD.get(threshold_pct, "")
    granted = balance.get("granted") or 0
    used = balance.get("used") or 0
    remaining = balance.get("remaining") or 0

    lines = [
        headline,
        "",
        lead,
        "",
        f"Used this cycle: {used}",
        f"Granted this cycle: {granted}",
        f"Remaining: {remaining}",
        "",
        f"Manage your plan or top up here: {account_url}",
    ]

    message = EmailMessage(
        subject=f"[VRT SPACE] {headline}",
        body="\n".join(lines),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[recipient],
    )
    message.send(fail_silently=False)
    return 1
