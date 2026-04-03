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
from django.db.models import Sum
from django.db.models import Q
from django.utils import timezone

from apps.core.plan_catalog import (
    build_marketing_packages,
    build_workspace_plan_defaults,
    get_plan_definition,
    get_plan_definitions,
)
from apps.tools.models import AuditRun

from .models import (
    ClientProject,
    UsageRecord,
    WorkspaceCreditLedger,
    WorkspacePlan,
    WorkspaceSubscription,
)

STRIPE_API_BASE = "https://api.stripe.com/v1"
ACTIVE_SUBSCRIPTION_STATUSES = {
    WorkspaceSubscription.Status.ACTIVE,
    WorkspaceSubscription.Status.TRIALING,
}


class BillingError(Exception):
    pass


USAGE_LIMIT_MAP = {
    UsageRecord.Metric.AUDIT_RUN: "audit",
    UsageRecord.Metric.SEO_SNAPSHOT: "seo",
    UsageRecord.Metric.AEO_AUDIT: "aeo",
    UsageRecord.Metric.CONTENT_DRAFT: "content",
    UsageRecord.Metric.EXPORT: "export",
}

USAGE_METRIC_BY_CREDIT_CATEGORY = {value: key for key, value in USAGE_LIMIT_MAP.items()}


def _definition_to_capabilities(definition):
    definition = definition or get_plan_definition("free") or {}
    limits = dict(definition.get("limits", {}))
    features = dict(definition.get("feature_flags", {}))
    credits = dict(definition.get("credits", {}))
    return {
        "name": definition.get("name", "Free"),
        "slug": definition.get("slug", "free"),
        "label": definition.get("label", ""),
        "price_label": definition.get("price_label", ""),
        "description": definition.get("description", ""),
        "audience": definition.get("audience", ""),
        "upgrade_message": definition.get("upgrade_message", ""),
        "features": features,
        "limits": limits,
        "credits": credits,
        "monthly_audits_limit": limits.get("audit_runs"),
        "history_limit": limits.get("saved_history"),
        "premium_recommendation_limit": limits.get("premium_recommendations"),
        "recurring_audits_enabled": features.get("recurring_audits_enabled", False),
        "export_reports_enabled": features.get("export_reports_enabled", False),
        "email_reports_enabled": features.get("email_reports_enabled", False),
        "competitor_tracking_enabled": features.get("competitor_tracking_enabled", False),
        "stakeholder_sharing_enabled": features.get("stakeholder_sharing_enabled", False),
        "seo_workspace_enabled": features.get("seo_workspace_enabled", False),
        "aeo_workspace_enabled": features.get("aeo_workspace_enabled", False),
        "content_workspace_enabled": features.get("content_workspace_enabled", False),
        "backlink_workspace_enabled": features.get("backlink_workspace_enabled", False),
        "action_packs_enabled": features.get("action_packs_enabled", False),
        "campaign_tracking_enabled": features.get("campaign_tracking_enabled", False),
        "cross_module_summary_enabled": features.get("cross_module_summary_enabled", False),
    }


FREE_PLAN_CAPABILITIES = _definition_to_capabilities(get_plan_definition("free"))


def get_workspace_plans():
    return list(WorkspacePlan.objects.filter(is_active=True).order_by("sort_order", "name"))


def sync_workspace_plan_catalog():
    for definition in get_plan_definitions(include_free=False):
        WorkspacePlan.objects.update_or_create(
            slug=definition["slug"],
            defaults=build_workspace_plan_defaults(definition),
        )


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
    capabilities = _definition_to_capabilities(get_plan_definition(plan.slug))
    metadata = dict(plan.metadata or {})
    capabilities["name"] = plan.name
    capabilities["price_label"] = plan.price_label or capabilities.get("price_label", "")
    capabilities["description"] = plan.description or capabilities.get("description", "")
    capabilities["label"] = metadata.get("label", capabilities.get("label", ""))
    capabilities["audience"] = metadata.get("audience", capabilities.get("audience", ""))
    capabilities["upgrade_message"] = metadata.get("upgrade_message", capabilities.get("upgrade_message", ""))
    capabilities["features"] = {
        **capabilities.get("features", {}),
        **metadata.get("features", {}),
    }
    capabilities["limits"] = {
        **capabilities.get("limits", {}),
        **metadata.get("limits", {}),
    }
    capabilities["credits"] = {
        **capabilities.get("credits", {}),
        **metadata.get("credits", {}),
    }
    capabilities["monthly_audits_limit"] = plan.monthly_audits_limit
    capabilities["history_limit"] = plan.history_limit
    capabilities["premium_recommendation_limit"] = plan.premium_recommendation_limit
    capabilities["recurring_audits_enabled"] = plan.recurring_audits_enabled
    capabilities["export_reports_enabled"] = plan.export_reports_enabled
    capabilities["email_reports_enabled"] = plan.email_reports_enabled
    capabilities["competitor_tracking_enabled"] = plan.competitor_tracking_enabled
    capabilities["stakeholder_sharing_enabled"] = plan.stakeholder_sharing_enabled
    capabilities["limits"]["audit_runs"] = plan.monthly_audits_limit
    capabilities["limits"]["saved_history"] = plan.history_limit
    capabilities["limits"]["premium_recommendations"] = plan.premium_recommendation_limit
    capabilities["features"]["recurring_audits_enabled"] = plan.recurring_audits_enabled
    capabilities["features"]["export_reports_enabled"] = plan.export_reports_enabled
    capabilities["features"]["email_reports_enabled"] = plan.email_reports_enabled
    capabilities["features"]["competitor_tracking_enabled"] = plan.competitor_tracking_enabled
    capabilities["features"]["stakeholder_sharing_enabled"] = plan.stakeholder_sharing_enabled
    return capabilities


def get_billing_state(user):
    subscription = get_workspace_subscription(user)
    capabilities = get_effective_capabilities(user)
    usage = get_usage_summary(user)
    credit_summary = get_credit_summary(user)
    plans = build_plan_cards(user)
    return {
        "subscription": subscription,
        "capabilities": capabilities,
        "usage": usage,
        "credits": credit_summary,
        "plans": plans,
        "stripe_enabled": settings.STRIPE_ENABLED,
        "publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
    }


def build_plan_cards(user=None):
    subscription = get_workspace_subscription(user) if user else None
    current_plan_slug = subscription.plan.slug if is_active_subscription(subscription) else "free"
    plan_map = {plan.slug: plan for plan in get_workspace_plans()}
    cards = []
    for package in build_marketing_packages(include_free=True):
        plan = plan_map.get(package["slug"])
        price_id = get_stripe_price_id(plan) if plan else ""
        cards.append(
            {
                "plan": plan,
                "name": package["name"],
                "slug": package["slug"],
                "label": package.get("label", ""),
                "price": package.get("price", getattr(plan, "price_label", "")),
                "features": package.get("features", []),
                "limits_summary": package.get("limits_summary", []),
                "credits": package.get("credits", {}),
                "description": package.get("description", getattr(plan, "description", "")),
                "audience": package.get("audience", ""),
                "upgrade_message": package.get("upgrade_message", ""),
                "stripe_price_id": price_id,
                "is_current": package["slug"] == current_plan_slug,
                "is_custom": package.get("is_custom", False) or (bool(plan) and (plan.slug == "enterprise" or not price_id)),
                "is_free": package.get("is_free", False),
            }
        )
    return cards


def get_month_period_window(now=None):
    now = now or timezone.now()
    start = date(year=now.year, month=now.month, day=1)
    last_day = calendar.monthrange(now.year, now.month)[1]
    end = date(year=now.year, month=now.month, day=last_day)
    return start, end


def get_credit_record_window(now=None):
    return get_month_period_window(now=now)


def _get_credit_allowances(user):
    return dict(get_effective_capabilities(user).get("credits", {}))


def ensure_plan_credit_grants(user, now=None):
    if not user or not getattr(user, "is_authenticated", False):
        return
    period_start, period_end = get_credit_record_window(now=now)
    subscription = get_workspace_subscription(user)
    plan = subscription.plan if is_active_subscription(subscription) else None
    for category, amount in _get_credit_allowances(user).items():
        if amount in (0, None):
            continue
        existing = WorkspaceCreditLedger.objects.filter(
            user=user,
            category=category,
            kind=WorkspaceCreditLedger.Kind.GRANT,
            period_start=period_start,
            period_end=period_end,
        ).exists()
        if existing:
            continue
        WorkspaceCreditLedger.objects.create(
            user=user,
            plan=plan,
            subscription=subscription,
            category=category,
            kind=WorkspaceCreditLedger.Kind.GRANT,
            delta=amount,
            period_start=period_start,
            period_end=period_end,
            note="Monthly plan credit allocation",
            reference_key=f"plan-credit:{category}:{period_start.isoformat()}",
            metadata={"source": "monthly_plan_credit"},
        )


def get_credit_balance_summary(user, category, now=None):
    period_start, period_end = get_credit_record_window(now=now)
    if not user or not getattr(user, "is_authenticated", False):
        return {"granted": 0, "used": 0, "remaining": 0, "unlimited": False}

    ensure_plan_credit_grants(user, now=now)
    allowance = _get_credit_allowances(user).get(category)
    queryset = WorkspaceCreditLedger.objects.filter(
        user=user,
        category=category,
        period_start=period_start,
        period_end=period_end,
    )
    total = queryset.aggregate(total=Sum("delta")).get("total") or 0
    used = abs(
        queryset.filter(delta__lt=0).aggregate(total=Sum("delta")).get("total") or 0
    )
    usage_metric = USAGE_METRIC_BY_CREDIT_CATEGORY.get(category)
    if usage_metric:
        usage_record = get_usage_record(user, usage_metric, now=now)
        used = max(used, usage_record.quantity)
    if allowance is None:
        return {
            "granted": None,
            "used": used,
            "remaining": None,
            "unlimited": True,
        }
    granted = queryset.filter(delta__gt=0).aggregate(total=Sum("delta")).get("total") or 0
    return {
        "granted": granted,
        "used": used,
        "remaining": granted - used,
        "unlimited": False,
    }


def get_credit_summary(user, now=None):
    labels = {
        "audit": "Audit credits",
        "seo": "SEO credits",
        "aeo": "AEO credits",
        "content": "Content credits",
        "backlink": "Backlink credits",
        "export": "Export credits",
        "share": "Share credits",
    }
    summary = []
    for category, label in labels.items():
        allowance = _get_credit_allowances(user).get(category)
        if allowance is None and category not in _get_credit_allowances(user):
            continue
        balance = get_credit_balance_summary(user, category, now=now)
        summary.append(
            {
                "category": category,
                "label": label,
                **balance,
            }
        )
    return summary


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
    audit_usage = get_usage_record(user, UsageRecord.Metric.AUDIT_RUN)
    seo_usage = get_usage_record(user, UsageRecord.Metric.SEO_SNAPSHOT)
    aeo_usage = get_usage_record(user, UsageRecord.Metric.AEO_AUDIT)
    content_usage = get_usage_record(user, UsageRecord.Metric.CONTENT_DRAFT)
    export_usage = get_usage_record(user, UsageRecord.Metric.EXPORT)
    audit_limit = capabilities.get("credits", {}).get("audit")
    seo_limit = capabilities.get("credits", {}).get("seo")
    aeo_limit = capabilities.get("credits", {}).get("aeo")
    content_limit = capabilities.get("credits", {}).get("content")
    export_limit = capabilities.get("credits", {}).get("export")
    return {
        "audit_runs_used": audit_usage.quantity,
        "audit_runs_limit": audit_limit,
        "audit_runs_remaining": None if audit_limit is None else max(audit_limit - audit_usage.quantity, 0),
        "seo_snapshots_used": seo_usage.quantity,
        "seo_snapshots_limit": seo_limit,
        "aeo_audits_used": aeo_usage.quantity,
        "aeo_audits_limit": aeo_limit,
        "content_drafts_used": content_usage.quantity,
        "content_drafts_limit": content_limit,
        "exports_used": export_usage.quantity,
        "exports_limit": export_limit,
    }


def record_usage(user, metric, quantity=1):
    record = get_usage_record(user, metric)
    record.quantity += quantity
    record.save(update_fields=["quantity", "updated_at"])
    return record


def can_spend_credits(user, category, *, amount=1, now=None):
    balance = get_credit_balance_summary(user, category, now=now)
    if balance["unlimited"]:
        return True, balance
    return balance["remaining"] >= amount, balance


def spend_credits(user, category, *, amount=1, project=None, note="", reference_key="", metadata=None, now=None):
    metadata = metadata or {}
    allowed, balance = can_spend_credits(user, category, amount=amount, now=now)
    if settings.AUDIT_TIER_ENFORCEMENT and not allowed:
        raise BillingError(
            f"Your current plan does not have enough {category} credits remaining for this action."
        )

    period_start, period_end = get_credit_record_window(now=now)
    subscription = get_workspace_subscription(user)
    plan = subscription.plan if is_active_subscription(subscription) else None
    entry = WorkspaceCreditLedger.objects.create(
        user=user,
        plan=plan,
        subscription=subscription,
        project=project,
        category=category,
        kind=WorkspaceCreditLedger.Kind.DEBIT,
        delta=amount * -1,
        period_start=period_start,
        period_end=period_end,
        note=note[:255],
        reference_key=reference_key[:120],
        metadata=metadata,
    )
    return entry


def can_run_workspace_audit(user):
    return can_spend_credits(user, "audit", amount=1)


def can_access_audit_feature(user, feature_name):
    capabilities = get_effective_capabilities(user)
    if not settings.AUDIT_TIER_ENFORCEMENT:
        return True, capabilities
    if feature_name in capabilities:
        return bool(capabilities.get(feature_name)), capabilities
    return bool(capabilities.get("features", {}).get(feature_name)), capabilities


def can_access_workspace_feature(user, feature_name):
    return can_access_audit_feature(user, feature_name)


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

    allowed, balance = can_run_workspace_audit(user)
    if settings.AUDIT_TIER_ENFORCEMENT and not allowed:
        raise BillingError("Your current plan does not have enough audit credits remaining.")

    audit_run = AuditRun.objects.create(
        audit_request=project.audit_request,
        normalized_domain="pending",
        start_url=project.website,
    )
    spend_credits(
        user,
        "audit",
        amount=1,
        project=project,
        note="Workspace audit rerun",
        reference_key=f"audit-run:{audit_run.pk}",
        metadata={"remaining_before": balance.get("remaining")},
    )
    record_usage(user, UsageRecord.Metric.AUDIT_RUN, quantity=1)
    return audit_run
