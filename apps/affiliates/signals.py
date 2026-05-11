"""Decoupling layer between billing and affiliate-commission accrual.

The Stripe webhook handler in apps.leads.billing fires `payment_received`
after it has synced a successful invoice/checkout. The receiver here turns
that into a CommissionLedger entry if the paying user has an attribution.

Keeping this in a signal (vs. a direct import from billing.py) means the
affiliates app can be disabled without touching the billing code path.
"""
from __future__ import annotations

import logging

from django.contrib.auth import get_user_model
from django.dispatch import Signal, receiver

from .services import AffiliateError, record_commission_for_payment

logger = logging.getLogger(__name__)


# Fired by apps.leads.billing after a Stripe invoice/checkout payment succeeds.
# Sender: a string event source identifier (e.g. "stripe.invoice.payment_succeeded").
# Kwargs:
#   user_id:               int — workspace user that just paid
#   stripe_event_id:       str — webhook event id (idempotency key)
#   gross_amount_cents:    int — total amount paid in cents
#   currency:              str — ISO currency code, default "usd"
#   is_first_payment:      bool — True only for the user's first paid invoice
#   stripe_invoice_id:     str — optional
#   stripe_charge_id:      str — optional
#   metadata:              dict — optional event payload echo
payment_received = Signal()


@receiver(payment_received)
def _on_payment_received(sender, **kwargs):
    user_id = kwargs.get("user_id")
    stripe_event_id = kwargs.get("stripe_event_id") or ""
    gross = int(kwargs.get("gross_amount_cents") or 0)
    if not user_id or not stripe_event_id or gross <= 0:
        return

    User = get_user_model()
    user = User.objects.filter(pk=user_id).first()
    if not user:
        return

    try:
        record_commission_for_payment(
            user=user,
            stripe_event_id=stripe_event_id,
            gross_amount_cents=gross,
            currency=kwargs.get("currency") or "usd",
            is_first_payment=bool(kwargs.get("is_first_payment")),
            stripe_invoice_id=kwargs.get("stripe_invoice_id") or "",
            stripe_charge_id=kwargs.get("stripe_charge_id") or "",
            metadata=kwargs.get("metadata") or {},
        )
    except AffiliateError as exc:
        logger.warning(
            "Affiliate commission recording failed: user_id=%s event=%s err=%s",
            user_id,
            stripe_event_id,
            exc,
        )
    except Exception:
        logger.exception(
            "Unexpected error recording affiliate commission: user_id=%s event=%s",
            user_id,
            stripe_event_id,
        )
