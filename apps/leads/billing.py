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
WORKSPACE_CREDIT_CATEGORY = "workspace"
CREDIT_ACTIVITY_LABELS = {
    "audit": "Audit runs this month",
    "seo": "SEO context refreshes",
    "aeo": "AEO analyses",
    "content": "Content drafts",
    "backlink": "Backlink work",
    "export": "Report exports",
    "share": "Stakeholder shares",
}
ACTION_FEATURE_LABELS = {
    "recurring_audits_enabled": "Recurring audits",
    "export_reports_enabled": "Advanced exports",
    "email_reports_enabled": "Email delivery",
    "stakeholder_sharing_enabled": "Stakeholder sharing",
    "seo_workspace_enabled": "SEO workspace",
    "aeo_workspace_enabled": "AEO workspace",
    "content_workspace_enabled": "Content workspace",
    "backlink_workspace_enabled": "Backlink workspace",
    "action_packs_enabled": "Action packs",
    "campaign_tracking_enabled": "Campaign tracking",
    "cross_module_summary_enabled": "Cross-module summaries",
}
AUDIT_RESULT_PROFILES = {
    "free": {
        "label": "Starter diagnosis",
        "summary": "Clear enough to confirm the main blockers, but intentionally shaped to push the next decision instead of dumping everything.",
        "top_issue_limit": 3,
        "quick_win_limit": 3,
        "featured_recommendation_limit": 3,
        "secondary_recommendation_limit": 0,
        "performance_metric_limit": 3,
        "score_breakdown_keys": ["technical", "seo", "performance", "aeo"],
        "technical_page_limit": 0,
        "show_context_analysis": False,
        "show_custom_work_items": False,
        "show_secondary_recommendations": False,
    },
    "starter": {
        "label": "Action-ready audit",
        "summary": "Detailed enough to act on the audit inside the workspace, without exposing the full operating depth reserved for larger plans.",
        "top_issue_limit": 4,
        "quick_win_limit": 4,
        "featured_recommendation_limit": 5,
        "secondary_recommendation_limit": 3,
        "performance_metric_limit": 4,
        "score_breakdown_keys": ["technical", "seo", "performance", "aeo", "content", "internal_linking"],
        "technical_page_limit": 5,
        "show_context_analysis": False,
        "show_custom_work_items": True,
        "show_secondary_recommendations": True,
    },
    "growth": {
        "label": "Growth planning layer",
        "summary": "Designed for teams who need deeper audit context, broader score visibility, and enough evidence to keep execution moving.",
        "top_issue_limit": 6,
        "quick_win_limit": 6,
        "featured_recommendation_limit": 6,
        "secondary_recommendation_limit": 6,
        "performance_metric_limit": 6,
        "score_breakdown_keys": None,
        "technical_page_limit": 12,
        "show_context_analysis": True,
        "show_custom_work_items": True,
        "show_secondary_recommendations": True,
    },
    "authority": {
        "label": "Full audit depth",
        "summary": "The deepest audit layer with broader evidence, technical footprint, and the clearest handoff into execution workflows.",
        "top_issue_limit": None,
        "quick_win_limit": None,
        "featured_recommendation_limit": None,
        "secondary_recommendation_limit": None,
        "performance_metric_limit": None,
        "score_breakdown_keys": None,
        "technical_page_limit": None,
        "show_context_analysis": True,
        "show_custom_work_items": True,
        "show_secondary_recommendations": True,
    },
    "enterprise": {
        "label": "Custom audit depth",
        "summary": "Reserved for custom environments that need the full audit surface and broader operational context.",
        "top_issue_limit": None,
        "quick_win_limit": None,
        "featured_recommendation_limit": None,
        "secondary_recommendation_limit": None,
        "performance_metric_limit": None,
        "score_breakdown_keys": None,
        "technical_page_limit": None,
        "show_context_analysis": True,
        "show_custom_work_items": True,
        "show_secondary_recommendations": True,
    },
}


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


def _get_current_plan_slug(user):
    subscription = get_workspace_subscription(user)
    if not is_active_subscription(subscription):
        return "free"
    return subscription.plan.slug


def _get_current_plan_sort_order(user):
    definition = get_plan_definition(_get_current_plan_slug(user)) or {}
    return definition.get("sort_order", 0)


def _plan_supports_requirements(definition, *, feature_name=None, required_credits=0):
    if feature_name and not definition.get("feature_flags", {}).get(feature_name, False):
        return False
    allowance = definition.get("credits", {}).get(WORKSPACE_CREDIT_CATEGORY)
    if required_credits and allowance is not None and allowance < required_credits:
        return False
    return True


def get_next_plan_for_action(user, *, feature_name=None, required_credits=0):
    current_sort_order = _get_current_plan_sort_order(user)
    for definition in get_plan_definitions(include_free=True):
        if definition.get("sort_order", 0) <= current_sort_order:
            continue
        if _plan_supports_requirements(
            definition,
            feature_name=feature_name,
            required_credits=required_credits,
        ):
            return definition
    return None


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
    definition = get_plan_definition(plan.slug)
    if not definition:
        capabilities = _definition_to_capabilities(None)
        metadata = dict(plan.metadata or {})
        capabilities["name"] = plan.name or capabilities.get("name", "Free")
        capabilities["price_label"] = plan.price_label or capabilities.get("price_label", "")
        capabilities["description"] = plan.description or capabilities.get("description", "")
        capabilities["label"] = metadata.get("label", capabilities.get("label", ""))
        capabilities["audience"] = metadata.get("audience", capabilities.get("audience", ""))
        capabilities["upgrade_message"] = metadata.get("upgrade_message", capabilities.get("upgrade_message", ""))
        capabilities["features"] = {
            **metadata.get("features", {}),
            **capabilities.get("features", {}),
        }
        capabilities["limits"] = {
            **metadata.get("limits", {}),
            **capabilities.get("limits", {}),
        }
        capabilities["credits"] = {
            **metadata.get("credits", {}),
            **capabilities.get("credits", {}),
        }
        return capabilities

    capabilities = _definition_to_capabilities(definition)
    metadata = dict(plan.metadata or {})
    capabilities["name"] = definition.get("name", capabilities.get("name", "Free"))
    capabilities["price_label"] = definition.get("price_label", capabilities.get("price_label", ""))
    capabilities["description"] = definition.get("description", capabilities.get("description", ""))
    capabilities["label"] = definition.get("label", metadata.get("label", capabilities.get("label", "")))
    capabilities["audience"] = definition.get("audience", metadata.get("audience", capabilities.get("audience", "")))
    capabilities["upgrade_message"] = definition.get(
        "upgrade_message",
        metadata.get("upgrade_message", capabilities.get("upgrade_message", "")),
    )
    capabilities["features"] = {
        **metadata.get("features", {}),
        **capabilities.get("features", {}),
    }
    capabilities["limits"] = {
        **metadata.get("limits", {}),
        **capabilities.get("limits", {}),
    }
    capabilities["credits"] = {
        **metadata.get("credits", {}),
        **capabilities.get("credits", {}),
    }
    capabilities["monthly_audits_limit"] = capabilities["limits"].get("audit_runs")
    capabilities["history_limit"] = capabilities["limits"].get("saved_history")
    capabilities["premium_recommendation_limit"] = capabilities["limits"].get("premium_recommendations")
    capabilities["recurring_audits_enabled"] = capabilities["features"].get("recurring_audits_enabled", False)
    capabilities["export_reports_enabled"] = capabilities["features"].get("export_reports_enabled", False)
    capabilities["email_reports_enabled"] = capabilities["features"].get("email_reports_enabled", False)
    capabilities["competitor_tracking_enabled"] = capabilities["features"].get("competitor_tracking_enabled", False)
    capabilities["stakeholder_sharing_enabled"] = capabilities["features"].get("stakeholder_sharing_enabled", False)
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
        "credit_overview": get_total_credit_balance_summary(user),
        "credit_activity": get_credit_activity_summary(user),
        "recent_credit_entries": get_recent_credit_entries(user),
        "plans": plans,
        "stripe_enabled": settings.STRIPE_ENABLED,
        "publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
    }


def build_plan_cards(user=None):
    subscription = get_workspace_subscription(user) if user else None
    current_plan_slug = subscription.plan.slug if is_active_subscription(subscription) else "free"
    definition_map = {item["slug"]: item for item in get_plan_definitions(include_free=True)}
    current_sort_order = definition_map.get(current_plan_slug, {}).get("sort_order", 0)
    plan_map = {plan.slug: plan for plan in get_workspace_plans()}
    cards = []
    for package in build_marketing_packages(include_free=True):
        plan = plan_map.get(package["slug"])
        price_id = get_stripe_price_id(plan) if plan else ""
        package_sort_order = definition_map.get(package["slug"], {}).get("sort_order", 0)
        is_current = package["slug"] == current_plan_slug
        action_label = ""
        action_direction = ""
        if is_current:
            action_label = "Current plan"
            action_direction = "current"
        elif package.get("is_custom", False) or (bool(plan) and (plan.slug == "enterprise" or not price_id)):
            action_label = "Request custom scope"
            action_direction = "custom"
        elif package.get("is_free", False):
            action_label = "Move to Free"
            action_direction = "move"
        elif package_sort_order > current_sort_order:
            action_label = f"Upgrade to {package['name']}"
            action_direction = "upgrade"
        else:
            action_label = f"Move to {package['name']}"
            action_direction = "move"
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
                "is_current": is_current,
                "is_custom": package.get("is_custom", False) or (bool(plan) and (plan.slug == "enterprise" or not price_id)),
                "is_free": package.get("is_free", False),
                "action_label": action_label,
                "action_direction": action_direction,
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


def _get_workspace_credit_allowance(user):
    allowances = _get_credit_allowances(user)
    if WORKSPACE_CREDIT_CATEGORY in allowances:
        return allowances.get(WORKSPACE_CREDIT_CATEGORY)

    if not allowances:
        return 0

    if any(value is None for value in allowances.values()):
        return None

    return sum(value for value in allowances.values() if isinstance(value, (int, float)))


def ensure_plan_credit_grants(user, now=None):
    if not user or not getattr(user, "is_authenticated", False):
        return
    period_start, period_end = get_credit_record_window(now=now)
    subscription = get_workspace_subscription(user)
    plan = subscription.plan if is_active_subscription(subscription) else None
    amount = _get_workspace_credit_allowance(user)
    if amount in (0, None):
        return
    granted_total = (
        WorkspaceCreditLedger.objects.filter(
            user=user,
            category=WORKSPACE_CREDIT_CATEGORY,
            kind=WorkspaceCreditLedger.Kind.GRANT,
            period_start=period_start,
            period_end=period_end,
        ).aggregate(total=Sum("delta")).get("total")
        or 0
    )
    grant_delta = amount - granted_total
    if grant_delta <= 0:
        return
    existing = WorkspaceCreditLedger.objects.filter(
        user=user,
        category=WORKSPACE_CREDIT_CATEGORY,
        kind=WorkspaceCreditLedger.Kind.GRANT,
        period_start=period_start,
        period_end=period_end,
    ).exists()
    WorkspaceCreditLedger.objects.create(
        user=user,
        plan=plan,
        subscription=subscription,
        category=WORKSPACE_CREDIT_CATEGORY,
        kind=WorkspaceCreditLedger.Kind.GRANT,
        delta=grant_delta,
        period_start=period_start,
        period_end=period_end,
        note="Monthly workspace credit allocation" if not existing else "Workspace credit adjustment after plan change",
        reference_key=(
            f"plan-credit:{WORKSPACE_CREDIT_CATEGORY}:{period_start.isoformat()}"
            if not existing
            else f"plan-credit-adjustment:{WORKSPACE_CREDIT_CATEGORY}:{period_start.isoformat()}:{grant_delta}"
        ),
        metadata={
            "source": "monthly_plan_credit" if not existing else "plan_credit_adjustment",
            "target_allowance": amount,
            "granted_before": granted_total,
        },
    )


def _get_shadow_usage_amount(entry):
    if entry.delta < 0:
        return abs(entry.delta)
    return int((entry.metadata or {}).get("shadow_amount") or 0)


def _iter_period_usage_entries(user, *, now=None):
    period_start, period_end = get_credit_record_window(now=now)
    return WorkspaceCreditLedger.objects.filter(
        user=user,
        period_start=period_start,
        period_end=period_end,
    ).select_related("project")


def get_total_credit_balance_summary(user, now=None):
    if not user or not getattr(user, "is_authenticated", False):
        return {"granted": 0, "used": 0, "remaining": 0, "unlimited": False}

    ensure_plan_credit_grants(user, now=now)
    allowance = _get_workspace_credit_allowance(user)
    queryset = _iter_period_usage_entries(user, now=now)
    granted = queryset.filter(delta__gt=0).aggregate(total=Sum("delta")).get("total") or 0
    used = sum(_get_shadow_usage_amount(entry) for entry in queryset)
    overage = max(used - granted, 0)
    if allowance is None:
        return {
            "granted": None,
            "used": used,
            "remaining": None,
            "unlimited": True,
            "overage": 0,
            "is_testing_mode": not settings.AUDIT_TIER_ENFORCEMENT,
        }
    return {
        "granted": granted,
        "used": used,
        "remaining": max(granted - used, 0),
        "unlimited": False,
        "overage": overage,
        "is_testing_mode": not settings.AUDIT_TIER_ENFORCEMENT,
    }


def get_credit_balance_summary(user, category, now=None):
    period_start, period_end = get_credit_record_window(now=now)
    if not user or not getattr(user, "is_authenticated", False):
        return {"granted": 0, "used": 0, "remaining": 0, "unlimited": False}

    ensure_plan_credit_grants(user, now=now)
    if category == WORKSPACE_CREDIT_CATEGORY:
        return get_total_credit_balance_summary(user, now=now)

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
    balance = get_total_credit_balance_summary(user, now=now)
    return [
        {
            "category": WORKSPACE_CREDIT_CATEGORY,
            "label": "Workspace credits",
            **balance,
        }
    ]


def get_credit_activity_summary(user, now=None):
    if not user or not getattr(user, "is_authenticated", False):
        return []

    used_by_category = {}
    for entry in _iter_period_usage_entries(user, now=now):
        if entry.category == WORKSPACE_CREDIT_CATEGORY:
            continue
        used_by_category[entry.category] = used_by_category.get(entry.category, 0) + _get_shadow_usage_amount(entry)
    summary = []
    for category, label in CREDIT_ACTIVITY_LABELS.items():
        summary.append(
            {
                "category": category,
                "label": label,
                "used": used_by_category.get(category, 0),
            }
        )
    return summary


def get_recent_credit_entries(user, limit=8, now=None):
    if not user or not getattr(user, "is_authenticated", False):
        return []
    entries = (
        _iter_period_usage_entries(user, now=now)
        .order_by("-created_at")
    )
    recent = []
    for entry in entries:
        amount = _get_shadow_usage_amount(entry)
        if amount <= 0:
            continue
        recent.append(
            {
                "category": entry.category,
                "label": CREDIT_ACTIVITY_LABELS.get(entry.category, entry.category.title()),
                "amount": amount,
                "note": entry.note,
                "project_name": entry.project.name if entry.project_id else "",
                "created_at": entry.created_at,
                "is_estimated": bool((entry.metadata or {}).get("shadow_mode")),
            }
        )
        if len(recent) >= limit:
            break
    return recent


def get_existing_credit_entry(user, category, reference_key, *, now=None):
    if not reference_key:
        return None
    period_start, period_end = get_credit_record_window(now=now)
    return (
        WorkspaceCreditLedger.objects.filter(
            user=user,
            category=category,
            kind=WorkspaceCreditLedger.Kind.DEBIT,
            reference_key=reference_key,
            period_start=period_start,
            period_end=period_end,
        )
        .order_by("-created_at")
        .first()
    )


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
    limits = capabilities.get("limits", {})
    audit_limit = limits.get("audit_runs")
    seo_limit = limits.get("seo_refreshes")
    aeo_limit = limits.get("aeo_analyses")
    content_limit = limits.get("content_drafts")
    export_limit = limits.get("exports")
    site_limit = limits.get("tracked_sites")
    site_count = ClientProject.objects.filter(owner=user).count()
    return {
        "plan_slug": capabilities.get("slug", "free"),
        "plan_name": capabilities.get("name", "Free"),
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
        "tracked_sites_used": site_count,
        "tracked_sites_limit": site_limit,
        "tracked_sites_remaining": None if site_limit is None else max(site_limit - site_count, 0),
        "tracked_competitors_limit": limits.get("tracked_competitors"),
    }


def record_usage(user, metric, quantity=1):
    record = get_usage_record(user, metric)
    record.quantity += quantity
    record.save(update_fields=["quantity", "updated_at"])
    return record


def can_spend_credits(user, category, *, amount=1, now=None):
    balance = get_total_credit_balance_summary(user, now=now)
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
    shadow_mode = not settings.AUDIT_TIER_ENFORCEMENT
    delta = amount * -1 if not shadow_mode else 0
    entry = WorkspaceCreditLedger.objects.create(
        user=user,
        plan=plan,
        subscription=subscription,
        project=project,
        category=category,
        kind=WorkspaceCreditLedger.Kind.DEBIT,
        delta=delta,
        period_start=period_start,
        period_end=period_end,
        note=note[:255],
        reference_key=reference_key[:120],
        metadata={
            **metadata,
            "shadow_mode": shadow_mode,
            "shadow_amount": amount if shadow_mode else 0,
        },
    )
    return entry


def _get_project_complexity_band(project):
    latest_audit = getattr(project, "latest_audit_run", None) if project else None
    pages_crawled = getattr(latest_audit, "pages_crawled", 0) or 0
    if pages_crawled <= 10:
        return 1, pages_crawled or 10
    if pages_crawled <= 35:
        return 2, pages_crawled
    if pages_crawled <= 75:
        return 3, pages_crawled
    return 4, pages_crawled


def estimate_credit_cost(category, *, project=None, payload=None):
    payload = payload or {}
    band, page_count = _get_project_complexity_band(project)
    competitor_count = 0
    if getattr(project, "pk", None):
        competitor_count = project.seo_competitors.filter(is_active=True).count()

    if category == "audit":
        amount = min(8, 2 + band)
        reason = f"Site size and crawl depth around {page_count} pages."
    elif category == "seo":
        amount = min(10, 3 + band + (1 if competitor_count >= 3 else 0) + (1 if competitor_count >= 6 else 0))
        reason = f"Uses the latest audit plus competitor benchmarking depth across {competitor_count or 0} tracked competitors."
    elif category == "aeo":
        amount = min(6, 1 + band)
        reason = "Runs on the current audit and business context without requiring another crawl."
    elif category == "content":
        output_type = str(payload.get("output_type", "")).strip().lower()
        output_weights = {
            "answer_block": 1,
            "service_page": 2,
            "landing_page": 2,
            "article": 3,
        }
        amount = min(7, output_weights.get(output_type, 2) + max(band - 1, 0))
        reason = f"Depends on draft type ({output_type or 'standard'}) and the audit-backed context size."
    elif category == "backlink":
        amount = min(10, 3 + band)
        reason = "Prospecting cost scales with benchmark depth and supporting asset discovery."
    else:
        amount = 1
        reason = "Lightweight action against existing workspace data."

    return {
        "category": category,
        "amount": amount,
        "band": band,
        "page_count": page_count,
        "reason": reason,
        "uses_existing_audit": category in {"seo", "aeo", "content", "backlink"},
    }


def spend_action_credits(
    user,
    category,
    *,
    project=None,
    payload=None,
    note="",
    reference_key="",
    metadata=None,
    now=None,
    reuse_reference=False,
):
    estimate = estimate_credit_cost(category, project=project, payload=payload)
    existing_entry = None
    if reuse_reference and reference_key:
        existing_entry = get_existing_credit_entry(
            user,
            category,
            reference_key,
            now=now,
        )
        if existing_entry:
            estimate["reused_existing_charge"] = True
            return existing_entry, estimate
    metadata = {
        **(metadata or {}),
        "estimated_cost": estimate["amount"],
        "complexity_band": estimate["band"],
        "page_count": estimate["page_count"],
        "cost_reason": estimate["reason"],
        "uses_existing_audit": estimate["uses_existing_audit"],
    }
    entry = spend_credits(
        user,
        category,
        amount=estimate["amount"],
        project=project,
        note=note,
        reference_key=reference_key,
        metadata=metadata,
        now=now,
    )
    return entry, estimate


def build_credit_action_guide(project, user=None):
    actions = [
        {
            "slug": "audit",
            "label": "Run another audit",
            "next_step": "Use this only when you need a fresh crawl or want to validate improvements.",
        },
        {
            "slug": "seo",
            "label": "Go deeper with SEO",
            "next_step": "Reuses the latest audit and adds competitor-backed search intelligence.",
        },
        {
            "slug": "aeo",
            "label": "Check AEO",
            "next_step": "Reuses the same audit and business context for answer-engine visibility.",
        },
        {
            "slug": "content",
            "label": "Create content from the findings",
            "next_step": "Turns the current audit and SEO context into a draft or editorial task.",
        },
    ]
    guide = []
    for item in actions:
        estimate = estimate_credit_cost(item["slug"], project=project)
        action_state = (
            build_action_access_context(user, item["slug"], project=project)
            if user
            else {}
        )
        guide.append(
            {
                **item,
                "credits": estimate["amount"],
                "reason": estimate["reason"],
                "uses_existing_audit": estimate["uses_existing_audit"],
                "state": action_state,
            }
        )
    return guide


def build_action_access_context(user, category, *, project=None, feature_name=None, label=None, payload=None):
    estimate = estimate_credit_cost(category, project=project, payload=payload)
    balance = get_total_credit_balance_summary(user)
    required_credits = estimate["amount"]
    included_in_plan = True
    if feature_name:
        capabilities = get_effective_capabilities(user)
        included_in_plan = bool(capabilities.get("features", {}).get(feature_name, False))
    feature_allowed, _capabilities = (
        can_access_workspace_feature(user, feature_name)
        if feature_name
        else (True, get_effective_capabilities(user))
    )
    credit_allowed, _ = can_spend_credits(user, category, amount=required_credits)
    current_plan_slug = _get_current_plan_slug(user)
    current_plan_definition = get_plan_definition(current_plan_slug) or {}
    next_plan = None
    blocked_message = ""
    if settings.AUDIT_TIER_ENFORCEMENT:
        if feature_name and not feature_allowed:
            next_plan = get_next_plan_for_action(
                user,
                feature_name=feature_name,
                required_credits=required_credits,
            )
            feature_label = ACTION_FEATURE_LABELS.get(feature_name, label or category.title())
            blocked_message = f"{feature_label} is not included on the current plan."
        elif not credit_allowed:
            next_plan = get_next_plan_for_action(user, required_credits=required_credits)
            remaining_label = "Unlimited" if balance["unlimited"] else balance["remaining"]
            blocked_message = (
                f"This action usually needs {required_credits} workspace credits. "
                f"The current balance is {remaining_label}."
            )
    next_unlock_message = ""
    if next_plan:
        unlock_parts = [f"{next_plan['name']} unlocks this workflow"]
        if feature_name and not included_in_plan:
            unlock_parts.append(f"and adds {ACTION_FEATURE_LABELS.get(feature_name, 'the required workflow').lower()}")
        if next_plan.get("credits", {}).get(WORKSPACE_CREDIT_CATEGORY) is None:
            unlock_parts.append("with unlimited workspace credits")
        else:
            unlock_parts.append(
                f"with {next_plan.get('credits', {}).get(WORKSPACE_CREDIT_CATEGORY, 0)} workspace credits each cycle"
            )
        next_unlock_message = " ".join(unlock_parts) + "."
    elif not settings.AUDIT_TIER_ENFORCEMENT and feature_name and not included_in_plan:
        future_plan = get_next_plan_for_action(
            user,
            feature_name=feature_name,
            required_credits=required_credits,
        )
        if future_plan:
            next_unlock_message = (
                f"Visible in developer preview. {future_plan['name']} is the first plan that officially includes this workflow."
            )

    return {
        "category": category,
        "label": label or CREDIT_ACTIVITY_LABELS.get(category, category.title()),
        "feature_name": feature_name or "",
        "feature_allowed": feature_allowed,
        "included_in_plan": included_in_plan,
        "credit_allowed": credit_allowed,
        "available": (feature_allowed and credit_allowed) or not settings.AUDIT_TIER_ENFORCEMENT,
        "credits": required_credits,
        "reason": estimate["reason"],
        "uses_existing_audit": estimate["uses_existing_audit"],
        "remaining": balance["remaining"],
        "granted": balance["granted"],
        "used": balance["used"],
        "unlimited": balance["unlimited"],
        "blocked_message": blocked_message,
        "next_unlock_message": next_unlock_message,
        "current_plan_slug": current_plan_slug,
        "current_plan_name": current_plan_definition.get("name", "Free"),
        "next_plan_slug": next_plan.get("slug", "") if next_plan else "",
        "next_plan_name": next_plan.get("name", "") if next_plan else "",
        "next_plan_price": next_plan.get("price_label", "") if next_plan else "",
        "direct_checkout_available": bool(next_plan and next_plan.get("slug") not in {"", "free", "enterprise"}),
    }


def _get_next_plan_with_more_limit(user, limit_key, current_limit):
    current_sort_order = _get_current_plan_sort_order(user)
    for definition in get_plan_definitions(include_free=True):
        if definition.get("sort_order", 0) <= current_sort_order:
            continue
        next_limit = definition.get("limits", {}).get(limit_key)
        if current_limit is None:
            continue
        if next_limit is None or next_limit > current_limit:
            return definition
    return None


def get_workspace_capacity_summary(user):
    if not user or not getattr(user, "is_authenticated", False):
        return {
            "sites_used": 0,
            "sites_limit": 0,
            "sites_remaining": 0,
            "tracked_competitors_limit": 0,
        }

    capabilities = get_effective_capabilities(user)
    limits = capabilities.get("limits", {})
    site_limit = limits.get("tracked_sites")
    sites_used = ClientProject.objects.filter(owner=user).count()
    return {
        "sites_used": sites_used,
        "sites_limit": site_limit,
        "sites_remaining": None if site_limit is None else max(site_limit - sites_used, 0),
        "tracked_competitors_limit": limits.get("tracked_competitors"),
    }


def can_create_workspace_project(user, *, normalized_domain=""):
    if not user or not getattr(user, "is_authenticated", False):
        return True, {
            "sites_used": 0,
            "sites_limit": None,
            "sites_remaining": None,
            "existing_project": False,
            "blocked_message": "",
            "next_unlock_message": "",
        }

    capabilities = get_effective_capabilities(user)
    capacity = get_workspace_capacity_summary(user)
    existing_project = False
    if normalized_domain:
        existing_project = ClientProject.objects.filter(
            owner=user,
            normalized_domain=normalized_domain,
        ).exists()

    allowed = existing_project or capacity["sites_limit"] is None or capacity["sites_used"] < capacity["sites_limit"]
    blocked_message = ""
    next_unlock_message = ""
    next_plan = None
    if settings.AUDIT_TIER_ENFORCEMENT and not allowed:
        next_plan = _get_next_plan_with_more_limit(
            user,
            "tracked_sites",
            capacity["sites_limit"],
        )
        blocked_message = (
            f"The {capabilities.get('name', 'current')} plan tracks up to "
            f"{capacity['sites_limit']} website{'' if capacity['sites_limit'] == 1 else 's'}."
        )
        if next_plan:
            next_limit = next_plan.get("limits", {}).get("tracked_sites")
            next_unlock_message = (
                f"{next_plan['name']} raises that capacity to "
                f"{'Unlimited' if next_limit is None else next_limit} tracked websites."
            )

    return allowed or not settings.AUDIT_TIER_ENFORCEMENT, {
        **capacity,
        "existing_project": existing_project,
        "blocked_message": blocked_message,
        "next_unlock_message": next_unlock_message,
        "next_plan_slug": next_plan.get("slug", "") if next_plan else "",
        "next_plan_name": next_plan.get("name", "") if next_plan else "",
        "next_plan_price": next_plan.get("price_label", "") if next_plan else "",
    }


def get_audit_result_profile(user=None):
    if user and getattr(user, "is_authenticated", False):
        slug = get_effective_capabilities(user).get("slug", "free")
    else:
        slug = "free"
    profile = AUDIT_RESULT_PROFILES.get(slug, AUDIT_RESULT_PROFILES["free"])
    return {"slug": slug, **profile}


def build_audit_run_access_context(user, *, project=None):
    capabilities = get_effective_capabilities(user)
    usage = get_usage_summary(user)
    estimate = estimate_credit_cost("audit", project=project)
    credit_allowed, balance = can_spend_credits(user, "audit", amount=estimate["amount"])
    usage_remaining = usage.get("audit_runs_remaining")
    usage_allowed = usage_remaining is None or usage_remaining > 0
    next_plan = None
    blocked_message = ""

    if settings.AUDIT_TIER_ENFORCEMENT:
        if not usage_allowed:
            next_plan = _get_next_plan_with_more_limit(
                user,
                "audit_runs",
                usage.get("audit_runs_limit"),
            )
            blocked_message = (
                f"You have used all {usage.get('audit_runs_limit', 0)} audits included in "
                f"the {capabilities.get('name', 'current')} plan for this cycle."
            )
        elif not credit_allowed:
            next_plan = get_next_plan_for_action(user, required_credits=estimate["amount"])
            remaining_label = "Unlimited" if balance["unlimited"] else balance["remaining"]
            blocked_message = (
                f"This audit usually needs {estimate['amount']} workspace credits and the current balance is "
                f"{remaining_label}."
            )

    next_unlock_message = ""
    if next_plan:
        next_unlock_message = f"{next_plan['name']} starts at {next_plan.get('price_label', '')} and unlocks more audit capacity."

    return {
        "available": (usage_allowed and credit_allowed) or not settings.AUDIT_TIER_ENFORCEMENT,
        "usage_allowed": usage_allowed,
        "credit_allowed": credit_allowed,
        "blocked_message": blocked_message,
        "next_unlock_message": next_unlock_message,
        "balance": balance,
        "estimate": estimate,
        "usage": usage,
        "capabilities": capabilities,
        "next_plan_slug": next_plan.get("slug", "") if next_plan else "",
        "next_plan_name": next_plan.get("name", "") if next_plan else "",
        "next_plan_price": next_plan.get("price_label", "") if next_plan else "",
    }


def can_run_workspace_audit(user, *, project=None):
    access = build_audit_run_access_context(user, project=project)
    return access["available"], access["balance"], access["estimate"]


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


def fetch_checkout_session(session_id):
    if not settings.STRIPE_ENABLED:
        raise BillingError("Stripe billing is not configured.")
    if not session_id:
        raise BillingError("Missing Stripe checkout session id.")

    response = requests.get(
        f"{STRIPE_API_BASE}/checkout/sessions/{session_id}",
        auth=(settings.STRIPE_SECRET_KEY, ""),
        timeout=20,
    )
    if response.status_code >= 400:
        raise BillingError(f"Stripe checkout session lookup failed: {response.text[:200]}")
    return response.json()


def sync_subscription_from_checkout_session_id(session_id):
    session_data = fetch_checkout_session(session_id)
    return sync_subscription_from_checkout_session(session_data)


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
    ensure_plan_credit_grants(subscription.user)
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
    if subscription.status in ACTIVE_SUBSCRIPTION_STATUSES:
        ensure_plan_credit_grants(subscription.user)
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

    access = build_audit_run_access_context(user, project=project)
    if settings.AUDIT_TIER_ENFORCEMENT and not access["available"]:
        raise BillingError(
            access["blocked_message"]
            or access["next_unlock_message"]
            or "This audit rerun is blocked on the current plan."
        )

    audit_run = AuditRun.objects.create(
        audit_request=project.audit_request,
        normalized_domain="pending",
        start_url=project.website,
    )
    spend_action_credits(
        user,
        "audit",
        project=project,
        note="Workspace audit rerun",
        reference_key=f"audit-run:{audit_run.pk}",
        metadata={
            "remaining_before": access["balance"].get("remaining"),
            "audits_remaining_before": access["usage"].get("audit_runs_remaining"),
        },
    )
    record_usage(user, UsageRecord.Metric.AUDIT_RUN, quantity=1)
    return audit_run
