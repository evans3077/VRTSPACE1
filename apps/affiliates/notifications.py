"""Transactional emails sent to affiliates.

Three events: new signup attributed, commission earned, payout sent.
Failures are logged but never re-raised — email is a side channel,
not a critical path.
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

from .models import Affiliate, CommissionLedger, Payout, ReferralAttribution

logger = logging.getLogger(__name__)


def _from_address() -> str:
    return getattr(
        settings,
        "AFFILIATE_PROGRAM_FROM_EMAIL",
        getattr(settings, "DEFAULT_FROM_EMAIL", "partners@vrtspace.agency"),
    )


def _send(*, subject: str, template: str, context: dict, to_email: str):
    if not to_email:
        return
    try:
        body = render_to_string(template, context)
        send_mail(
            subject=subject,
            message=body,
            from_email=_from_address(),
            recipient_list=[to_email],
            fail_silently=True,
        )
    except Exception:
        logger.exception("Affiliate notification failed: subject=%s to=%s", subject, to_email)


def _format_cents(cents: int) -> str:
    return f"${cents / 100:.2f}"


def notify_new_signup(attribution: ReferralAttribution) -> None:
    affiliate = attribution.affiliate
    _send(
        subject="A new signup just used your VRTSPACE referral link",
        template="affiliates/emails/new_signup.txt",
        context={
            "affiliate": affiliate,
            "attribution": attribution,
        },
        to_email=affiliate.contact_email,
    )


def notify_commission_earned(commission: CommissionLedger) -> None:
    affiliate = commission.affiliate
    _send(
        subject=f"You earned {_format_cents(commission.commission_amount_cents)} on VRTSPACE",
        template="affiliates/emails/commission_earned.txt",
        context={
            "affiliate": affiliate,
            "commission": commission,
            "amount_display": _format_cents(commission.commission_amount_cents),
            "release_date": commission.release_at,
        },
        to_email=affiliate.contact_email,
    )


def notify_affiliate_welcome(affiliate: Affiliate, login_url: str, referral_url: str) -> None:
    _send(
        subject="Welcome to the VRT SPACE Partner Program",
        template="affiliates/emails/affiliate_welcome.txt",
        context={
            "affiliate": affiliate,
            "login_url": login_url,
            "referral_url": referral_url,
            "referral_code": affiliate.slug,
        },
        to_email=affiliate.contact_email,
    )


def notify_payout_sent(payout: Payout) -> None:
    affiliate = payout.affiliate
    _send(
        subject=f"Your VRTSPACE payout of {_format_cents(payout.amount_cents)} is on its way",
        template="affiliates/emails/payout_sent.txt",
        context={
            "affiliate": affiliate,
            "payout": payout,
            "amount_display": _format_cents(payout.amount_cents),
        },
        to_email=affiliate.contact_email,
    )
