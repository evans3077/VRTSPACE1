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


# ─── P3 — Team membership invite emails ────────────────────────────────────

ROLE_SUBJECT_VERB = {
    "owner": "as a workspace owner",
    "member": "as a workspace member",
    "client": "with read-only access",
}


def send_membership_invite_email(membership, *, accept_url, inviter_name=""):
    """Send the accept-invite link (OWNER/MEMBER) or read-only share link (CLIENT).

    Returns 1 on success, 0 if no recipient address is available. Never raises
    — invites must still be created even if SMTP is mid-incident.
    """
    recipient = (membership.invited_email or "").strip()
    if not recipient:
        return 0

    project = membership.project
    project_name = project.name if project else "your workspace"
    role = (membership.role or "").lower()
    role_phrase = ROLE_SUBJECT_VERB.get(role, "as a collaborator")
    inviter = inviter_name or "Your VRT SPACE colleague"

    if role == "client":
        subject = f"[VRT SPACE] You have a read-only share for {project_name}"
        lines = [
            f"{inviter} has shared a read-only snapshot of '{project_name}' with you.",
            "",
            "Use this link any time to view the latest audit results and top recommendations:",
            accept_url,
            "",
            "No signup required — the link itself is your credential. Treat it like a password.",
        ]
    else:
        subject = f"[VRT SPACE] Invite to join {project_name}"
        lines = [
            f"{inviter} has invited you to join '{project_name}' on VRT SPACE {role_phrase}.",
            "",
            "Click here to accept and open the workspace (you may be asked to sign in or sign up first):",
            accept_url,
            "",
            "If you weren't expecting this, you can ignore the message — the invite expires after 30 days.",
        ]

    try:
        EmailMessage(
            subject=subject,
            body="\n".join(lines),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient],
        ).send(fail_silently=True)
        return 1
    except Exception:
        return 0
