import calendar
import hashlib
import hmac
import json
import time
from datetime import date
from datetime import datetime
from datetime import timezone as dt_timezone

import requests
from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from apps.core.site_content import PACKAGES
from apps.tools.models import AuditRun

from .models import ClientProject, UsageRecord, WorkspacePlan, WorkspaceSubscription


FREE_PLAN_CAPABILITIES = {
    "name": "Free",
    "slug": "free",
    "monthly_audits_limit": 1,
    "history_limit": 1,
    "premium_recommendation_limit": 3,
    "recurring_audits_enabled": False,
    "export_reports_enabled": False,
}

STRIPE_API_BASE = "https://api.stripe.com/v1"
ACTIVE_SUBSCRIPTION_STATUSES = {
    WorkspaceSubscription.Status.ACTIVE,
    WorkspaceSubscription.Status.TRIALING,
}


class BillingError(Exception):
    pass


def get_workspace_plans():
    return list(WorkspacePlan.objects.filter(is_active=True).order_by("sort_order", "name"))


def get_workspace_subscription(user):
    if not user or not getattr(user, "is_authenticated", False):
        return None
    return (
        WorkspaceSubscription.objects.select_related("plan")
        .filter(user=user)
        .first()
    )


def is_active_subscription(subscription):
    return bool(
        subscription
        and subscription.plan_id
        and subscription.status in ACTIVE_SUBSCRIPTION_STATUSES
    )


def get_effective_capabilities(user):
    subscription = get_workspace_subscription(user)
    if not is_active_subscription(subscription):
        return dict(FREE_PLAN_CAPABILITIES)

    plan = subscription.plan
    return {
        "name": plan.name,
        "slug": plan.slug,
        "monthly_audits_limit": plan.monthly_audits_limit,
        "history_limit": plan.history_limit,
        "premium_recommendation_limit": plan.premium_recommendation_limit,
        "recurring_audits_enabled": plan.recurring_audits_enabled,
        "export_reports_enabled": plan.export_reports_enabled,
    }


def get_billing_state(user):
    subscription = get_workspace_subscription(user)
    capabilities = get_effective_capabilities(user)
    usage = get_usage_summary(user)
    plans = build_plan_cards(user)
    return {
        "subscription": subscription,
        "capabilities": capabilities,
        "usage": usage,
        "plans": plans,
        "stripe_enabled": settings.STRIPE_ENABLED,
        "publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
    }


def build_plan_cards(user=None):
    package_map = {package["name"].lower(): package for package in PACKAGES}
    subscription = get_workspace_subscription(user) if user else None
    current_plan_slug = subscription.plan.slug if is_active_subscription(subscription) else ""
    cards = []
    for plan in get_workspace_plans():
        package = package_map.get(plan.slug, {})
        price_id = get_stripe_price_id(plan)
        cards.append(
            {
                "plan": plan,
                "name": plan.name,
                "slug": plan.slug,
                "label": package.get("label", ""),
                "price": package.get("price", plan.price_label),
                "features": package.get("features", []),
                "description": plan.description,
                "stripe_price_id": price_id,
                "is_current": plan.slug == current_plan_slug,
                "is_custom": plan.slug == "enterprise" or not price_id,
            }
        )
    return cards


def get_month_period_window(now=None):
    now = now or timezone.now()
    start = date(year=now.year, month=now.month, day=1)
    last_day = calendar.monthrange(now.year, now.month)[1]
    end = date(year=now.year, month=now.month, day=last_day)
    return start, end


def get_usage_record(user, metric, now=None):
    period_start, period_end = get_month_period_window(now=now)
    subscription = get_workspace_subscription(user)
    plan = subscription.plan if is_active_subscription(subscription) else None
    record, _created = UsageRecord.objects.get_or_create(
        user=user,
        metric=metric,
        period_start=period_start,
        period_end=period_end,
        defaults={"plan": plan},
    )
    if record.plan_id != getattr(plan, "id", None):
        record.plan = plan
        record.save(update_fields=["plan", "updated_at"])
    return record


def get_usage_summary(user):
    if not user or not getattr(user, "is_authenticated", False):
        return {}
    capabilities = get_effective_capabilities(user)
    usage_record = get_usage_record(user, UsageRecord.Metric.AUDIT_RUN)
    limit = capabilities["monthly_audits_limit"]
    return {
        "audit_runs_used": usage_record.quantity,
        "audit_runs_limit": limit,
        "audit_runs_remaining": None if limit is None else max(limit - usage_record.quantity, 0),
    }


def record_usage(user, metric, quantity=1):
    record = get_usage_record(user, metric)
    record.quantity += quantity
    record.save(update_fields=["quantity", "updated_at"])
    return record


def can_run_workspace_audit(user):
    capabilities = get_effective_capabilities(user)
    limit = capabilities["monthly_audits_limit"]
    if limit is None:
        return True, None
    usage = get_usage_summary(user)
    if usage["audit_runs_used"] >= limit:
        return False, usage
    return True, usage


def get_stripe_price_id(plan):
    if plan.stripe_price_id:
        return plan.stripe_price_id
    return settings.STRIPE_PRICE_IDS.get(plan.slug, "")


def validate_stripe_price_id(price_id, *, plan_name):
    if not price_id:
        raise BillingError(f"No Stripe price is configured for the {plan_name} plan.")
    if not price_id.startswith("price_"):
        raise BillingError(
            f"The Stripe price for the {plan_name} plan must be a Stripe Price ID starting with 'price_', not a literal amount or product ID."
        )
    return price_id


def get_plan_by_slug(slug):
    return WorkspacePlan.objects.filter(slug=slug, is_active=True).first()


def get_plan_for_price_id(price_id):
    if not price_id:
        return None
    return WorkspacePlan.objects.filter(
        Q(stripe_price_id=price_id) | Q(slug__in=[slug for slug, configured_price_id in settings.STRIPE_PRICE_IDS.items() if configured_price_id == price_id])
    ).order_by("sort_order").first()


def create_checkout_session(*, user, plan, success_url, cancel_url):
    if not settings.STRIPE_ENABLED:
        raise BillingError("Stripe billing is not configured.")

    price_id = validate_stripe_price_id(get_stripe_price_id(plan), plan_name=plan.name)

    subscription = get_workspace_subscription(user)
    customer_id = subscription.stripe_customer_id if subscription and subscription.stripe_customer_id else ""

    payload = {
        "mode": "subscription",
        "success_url": success_url,
        "cancel_url": cancel_url,
        "client_reference_id": str(user.pk),
        "customer_email": user.email,
        "line_items[0][price]": price_id,
        "line_items[0][quantity]": "1",
        "metadata[user_id]": str(user.pk),
        "metadata[plan_slug]": plan.slug,
    }
    if customer_id:
        payload["customer"] = customer_id
        payload.pop("customer_email", None)

    response = requests.post(
        f"{STRIPE_API_BASE}/checkout/sessions",
        auth=(settings.STRIPE_SECRET_KEY, ""),
        data=payload,
        timeout=20,
    )
    if response.status_code >= 400:
        raise BillingError(f"Stripe checkout session creation failed: {response.text[:200]}")

    data = response.json()
    subscription = subscription or WorkspaceSubscription.objects.create(user=user)
    subscription.plan = plan
    subscription.stripe_checkout_session_id = data.get("id", "")
    subscription.save(update_fields=["plan", "stripe_checkout_session_id", "updated_at"])
    return data


def create_billing_portal_session(*, subscription, return_url):
    if not settings.STRIPE_ENABLED:
        raise BillingError("Stripe billing is not configured.")
    if not subscription or not subscription.stripe_customer_id:
        raise BillingError("No Stripe customer is attached to this workspace yet.")

    response = requests.post(
        f"{STRIPE_API_BASE}/billing_portal/sessions",
        auth=(settings.STRIPE_SECRET_KEY, ""),
        data={
            "customer": subscription.stripe_customer_id,
            "return_url": return_url,
        },
        timeout=20,
    )
    if response.status_code >= 400:
        raise BillingError(f"Stripe billing portal creation failed: {response.text[:200]}")
    return response.json()


def verify_stripe_signature(payload, signature_header):
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise BillingError("Stripe webhook secret is not configured.")
    if not signature_header:
        raise BillingError("Missing Stripe signature header.")

    parts = {}
    for item in signature_header.split(","):
        key, _sep, value = item.partition("=")
        parts[key] = value

    timestamp = parts.get("t")
    received_signature = parts.get("v1")
    if not timestamp or not received_signature:
        raise BillingError("Invalid Stripe signature format.")

    expected_signature = hmac.new(
        settings.STRIPE_WEBHOOK_SECRET.encode("utf-8"),
        msg=f"{timestamp}.{payload.decode('utf-8')}".encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected_signature, received_signature):
        raise BillingError("Stripe signature verification failed.")

    if abs(time.time() - int(timestamp)) > 300:
        raise BillingError("Stripe signature timestamp is too old.")

    return json.loads(payload.decode("utf-8"))


def sync_subscription_from_checkout_session(session_data):
    user_id = session_data.get("client_reference_id") or session_data.get("metadata", {}).get("user_id")
    if not user_id:
        return None
    subscription = WorkspaceSubscription.objects.filter(user_id=user_id).select_related("plan").first()
    if not subscription:
        subscription = WorkspaceSubscription.objects.create(user_id=user_id)

    plan_slug = session_data.get("metadata", {}).get("plan_slug", "")
    plan = get_plan_by_slug(plan_slug) if plan_slug else subscription.plan
    subscription.plan = plan
    subscription.status = WorkspaceSubscription.Status.ACTIVE
    subscription.stripe_customer_id = session_data.get("customer", "") or subscription.stripe_customer_id
    subscription.stripe_subscription_id = session_data.get("subscription", "") or subscription.stripe_subscription_id
    subscription.stripe_checkout_session_id = session_data.get("id", "") or subscription.stripe_checkout_session_id
    subscription.metadata = session_data
    subscription.save()
    return subscription


def sync_subscription_from_stripe_subscription(subscription_data, event_id=""):
    customer_id = subscription_data.get("customer", "")
    stripe_subscription_id = subscription_data.get("id", "")
    if not customer_id and not stripe_subscription_id:
        return None

    subscription = (
        WorkspaceSubscription.objects.select_related("plan")
        .filter(
            Q(stripe_customer_id=customer_id) | Q(stripe_subscription_id=stripe_subscription_id)
        )
        .first()
    )
    if not subscription:
        return None

    plan = get_plan_for_price_id(
        (((subscription_data.get("items") or {}).get("data") or [{}])[0].get("price") or {}).get("id", "")
    )
    if plan:
        subscription.plan = plan
    subscription.status = subscription_data.get("status", WorkspaceSubscription.Status.INACTIVE)
    subscription.stripe_customer_id = customer_id or subscription.stripe_customer_id
    subscription.stripe_subscription_id = stripe_subscription_id or subscription.stripe_subscription_id
    current_period_end = subscription_data.get("current_period_end")
    if current_period_end:
        subscription.current_period_end = datetime.fromtimestamp(
            current_period_end,
            tz=dt_timezone.utc,
        )
    subscription.cancel_at_period_end = bool(subscription_data.get("cancel_at_period_end", False))
    subscription.last_webhook_event_id = event_id
    subscription.metadata = subscription_data
    subscription.save()
    return subscription


def handle_stripe_webhook_event(event):
    event_type = event.get("type", "")
    event_id = event.get("id", "")
    data = (event.get("data") or {}).get("object", {})

    if event_type == "checkout.session.completed":
        return sync_subscription_from_checkout_session(data)
    if event_type in {
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    }:
        return sync_subscription_from_stripe_subscription(data, event_id=event_id)
    return None


def get_limited_audit_history(project, user):
    audit_history = (
        project.audit_request.audit_runs.order_by("-created_at")
        if getattr(project, "audit_request_id", None)
        else AuditRun.objects.none()
    )
    if not settings.AUDIT_TIER_ENFORCEMENT:
        return audit_history, 0

    history_limit = get_effective_capabilities(user)["history_limit"]
    if history_limit is None:
        return audit_history, 0

    audit_history_list = list(audit_history)
    visible = audit_history_list[:history_limit]
    locked_count = max(len(audit_history_list) - len(visible), 0)
    return visible, locked_count


def get_limited_recommendations(recommendations, user):
    if not settings.AUDIT_TIER_ENFORCEMENT:
        return recommendations, 0
    limit = get_effective_capabilities(user)["premium_recommendation_limit"]
    if limit is None:
        return recommendations, 0
    visible = list(recommendations[:limit])
    locked_count = max(len(recommendations) - len(visible), 0)
    return visible, locked_count


def create_workspace_rerun_for_user(user, *, project=None):
    if project is None:
        project = (
            ClientProject.objects.select_related("audit_request", "latest_audit_run")
            .filter(owner=user)
            .order_by("-updated_at")
            .first()
        )
    elif project.owner_id != user.id:
        raise BillingError("That workspace project does not belong to this account.")

    if not project:
        raise BillingError("No workspace project is attached to this account yet.")

    allowed, usage = can_run_workspace_audit(user)
    if settings.AUDIT_TIER_ENFORCEMENT and not allowed:
        raise BillingError(
            f"Your current plan has reached its monthly audit limit ({usage['audit_runs_limit']})."
        )

    audit_run = AuditRun.objects.create(
        audit_request=project.audit_request,
        normalized_domain="pending",
        start_url=project.website,
    )
    record_usage(user, UsageRecord.Metric.AUDIT_RUN, quantity=1)
    return audit_run
