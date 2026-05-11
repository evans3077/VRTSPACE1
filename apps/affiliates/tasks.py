"""Celery tasks for the affiliate program.

`process_affiliate_payouts` runs on a weekly schedule. It finds every
affiliate with releasable commissions (PENDING + release_at <= now),
bundles them into a Payout row, and pushes a Stripe Connect transfer.
"""
from __future__ import annotations

import logging

from celery import shared_task
from django.db import transaction

from .models import Affiliate, CommissionLedger, Payout
from .services import (
    AffiliateError,
    assemble_payout_for_affiliate,
    process_payout,
    releasable_commissions_qs,
)

logger = logging.getLogger(__name__)


@shared_task(name="affiliates.process_affiliate_payouts")
def process_affiliate_payouts():
    """Find every affiliate with cleared commissions, bundle, and pay out."""
    affiliate_ids = (
        releasable_commissions_qs()
        .values_list("affiliate_id", flat=True)
        .distinct()
    )
    summary = {
        "affiliates_processed": 0,
        "payouts_created": 0,
        "payouts_paid": 0,
        "payouts_failed": 0,
        "amount_paid_cents": 0,
    }
    for aff_id in affiliate_ids:
        summary["affiliates_processed"] += 1
        try:
            payout = process_affiliate(aff_id)
        except Exception:
            logger.exception("Unhandled error processing affiliate payouts: id=%s", aff_id)
            summary["payouts_failed"] += 1
            continue
        if not payout:
            continue
        summary["payouts_created"] += 1
        if payout.status == Payout.Status.PAID:
            summary["payouts_paid"] += 1
            summary["amount_paid_cents"] += payout.amount_cents
        elif payout.status == Payout.Status.FAILED:
            summary["payouts_failed"] += 1
    logger.info("Affiliate payout sweep complete: %s", summary)
    return summary


def process_affiliate(affiliate_id: int):
    affiliate = Affiliate.objects.filter(pk=affiliate_id).first()
    if not affiliate:
        return None
    with transaction.atomic():
        payout = assemble_payout_for_affiliate(affiliate)
    if not payout:
        return None
    try:
        return process_payout(payout)
    except AffiliateError as exc:
        logger.warning(
            "Stripe transfer failed for affiliate %s payout %s: %s",
            affiliate.slug,
            payout.pk,
            exc,
        )
        # Free the commissions to retry next sweep.
        CommissionLedger.objects.filter(payout=payout).update(
            payout=None,
            status=CommissionLedger.Status.PENDING,
        )
        return payout


@shared_task(name="affiliates.refresh_connect_statuses")
def refresh_connect_statuses():
    """Periodically pull latest Connect account state for pending affiliates."""
    from .services import refresh_connect_account_status

    pending = Affiliate.objects.filter(
        stripe_connect_account_id__gt="",
    ).exclude(stripe_connect_payouts_enabled=True)
    refreshed = 0
    for affiliate in pending.iterator():
        try:
            refresh_connect_account_status(affiliate)
            refreshed += 1
        except AffiliateError:
            continue
    return {"refreshed": refreshed}
