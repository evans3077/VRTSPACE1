PLAN_DEFINITIONS = [
    {
        "slug": "free",
        "name": "Free",
        "price_label": "$0",
        "label": "Audit entry layer",
        "description": "Run the entry audit, review the first priority findings, and see whether the workspace is worth deeper investment.",
        "sort_order": 0,
        "is_public": True,
        "is_paid": False,
        "is_custom": False,
        "audience": "Early evaluation and proof of value",
        "features": [
            "Public audit entry layer",
            "Grouped recommendations",
            "One saved workspace project",
            "Entry-level visibility into the fix queue",
        ],
        "credits": {
            "workspace": 1,
        },
        "limits": {
            "audit_runs": 1,
            "saved_history": 1,
            "premium_recommendations": 3,
            "seo_refreshes": 0,
            "aeo_analyses": 0,
            "exports": 0,
            "content_drafts": 0,
            "share_links": 0,
            "tracked_competitors": 0,
            "competitor_pages_per_refresh": 0,
            "backlink_prospects": 0,
            "automation_projects": 0,
        },
        "feature_flags": {
            "workspace_dashboard_enabled": True,
            "seo_workspace_enabled": False,
            "aeo_workspace_enabled": False,
            "content_workspace_enabled": False,
            "backlink_workspace_enabled": False,
            "recurring_audits_enabled": False,
            "export_reports_enabled": False,
            "email_reports_enabled": False,
            "competitor_tracking_enabled": False,
            "stakeholder_sharing_enabled": False,
            "action_packs_enabled": False,
            "campaign_tracking_enabled": False,
            "cross_module_summary_enabled": False,
        },
        "upgrade_message": "Upgrade when you need saved history, deeper recommendations, and module-level workspace tools.",
    },
    {
        "slug": "starter",
        "name": "Starter",
        "price_label": "~$200",
        "label": "Self-serve entry",
        "description": "For businesses that want repeatable audits and a clearer SEO and AEO action path without a heavy process.",
        "sort_order": 10,
        "is_public": True,
        "is_paid": True,
        "is_custom": False,
        "audience": "Solo operators and small local businesses",
        "features": [
            "Core audit workspace",
            "Saved audit history",
            "Priority recommendations",
            "Foundational SEO and AEO visibility review",
        ],
        "credits": {
            "workspace": 50,
        },
        "limits": {
            "audit_runs": 5,
            "saved_history": 5,
            "premium_recommendations": 8,
            "seo_refreshes": 4,
            "aeo_analyses": 4,
            "exports": 2,
            "content_drafts": 0,
            "share_links": 0,
            "tracked_competitors": 4,
            "competitor_pages_per_refresh": 3,
            "backlink_prospects": 0,
            "automation_projects": 0,
        },
        "feature_flags": {
            "workspace_dashboard_enabled": True,
            "seo_workspace_enabled": True,
            "aeo_workspace_enabled": True,
            "content_workspace_enabled": False,
            "backlink_workspace_enabled": False,
            "recurring_audits_enabled": False,
            "export_reports_enabled": False,
            "email_reports_enabled": False,
            "competitor_tracking_enabled": True,
            "stakeholder_sharing_enabled": False,
            "action_packs_enabled": True,
            "campaign_tracking_enabled": False,
            "cross_module_summary_enabled": False,
        },
        "upgrade_message": "Upgrade when you need recurring audits, deeper benchmarking, and stronger reporting.",
    },
    {
        "slug": "growth",
        "name": "Growth",
        "price_label": "~$500",
        "label": "Team plan",
        "description": "For teams that want recurring audits, stronger SEO and AEO depth, and reporting they can actually use.",
        "sort_order": 20,
        "is_public": True,
        "is_paid": True,
        "is_custom": False,
        "audience": "Serious SMBs and lean growth teams",
        "features": [
            "Recurring audits and exports",
            "Deeper competitor benchmarking",
            "Stronger SEO and AEO analysis capacity",
            "Stakeholder-ready reporting and sharing",
        ],
        "credits": {
            "workspace": 150,
        },
        "limits": {
            "audit_runs": 20,
            "saved_history": 20,
            "premium_recommendations": 18,
            "seo_refreshes": 12,
            "aeo_analyses": 10,
            "exports": 12,
            "content_drafts": 16,
            "share_links": 5,
            "tracked_competitors": 6,
            "competitor_pages_per_refresh": 4,
            "backlink_prospects": 80,
            "automation_projects": 2,
        },
        "feature_flags": {
            "workspace_dashboard_enabled": True,
            "seo_workspace_enabled": True,
            "aeo_workspace_enabled": True,
            "content_workspace_enabled": True,
            "backlink_workspace_enabled": False,
            "recurring_audits_enabled": True,
            "export_reports_enabled": True,
            "email_reports_enabled": True,
            "competitor_tracking_enabled": True,
            "stakeholder_sharing_enabled": True,
            "action_packs_enabled": True,
            "campaign_tracking_enabled": True,
            "cross_module_summary_enabled": False,
        },
        "upgrade_message": "Upgrade when you need more capacity, deeper visibility analysis, and stronger team reporting.",
    },
    {
        "slug": "authority",
        "name": "Authority",
        "price_label": "$1000+",
        "label": "Advanced visibility plan",
        "description": "For operators who want full audit, SEO, and AEO coverage with the deepest reporting and strategic support.",
        "sort_order": 30,
        "is_public": True,
        "is_paid": True,
        "is_custom": False,
        "audience": "Agencies, multi-location brands, and execution-heavy teams",
        "features": [
            "Full audit, SEO, and AEO workflow",
            "Higher monthly analysis capacity",
            "Advanced reporting and stakeholder visibility",
            "Deeper strategic support",
        ],
        "credits": {
            "workspace": 400,
        },
        "limits": {
            "audit_runs": 100,
            "saved_history": None,
            "premium_recommendations": None,
            "seo_refreshes": 40,
            "aeo_analyses": 30,
            "exports": None,
            "content_drafts": 60,
            "share_links": 25,
            "tracked_competitors": 8,
            "competitor_pages_per_refresh": 6,
            "backlink_prospects": 250,
            "automation_projects": 10,
        },
        "feature_flags": {
            "workspace_dashboard_enabled": True,
            "seo_workspace_enabled": True,
            "aeo_workspace_enabled": True,
            "content_workspace_enabled": True,
            "backlink_workspace_enabled": True,
            "recurring_audits_enabled": True,
            "export_reports_enabled": True,
            "email_reports_enabled": True,
            "competitor_tracking_enabled": True,
            "stakeholder_sharing_enabled": True,
            "action_packs_enabled": True,
            "campaign_tracking_enabled": True,
            "cross_module_summary_enabled": True,
        },
        "upgrade_message": "Move to Enterprise only when you need multi-market, custom integration, or bespoke workflow complexity.",
    },
    {
        "slug": "enterprise",
        "name": "Enterprise",
        "price_label": "Custom",
        "label": "Custom environments",
        "description": "Reserved for complex teams that need custom delivery, high-touch reporting, or multi-market support.",
        "sort_order": 40,
        "is_public": True,
        "is_paid": True,
        "is_custom": True,
        "audience": "Multi-market, multi-site, or custom workflow teams",
        "features": [
            "Custom architecture and workflow design",
            "Cross-market or multi-site strategy",
            "Custom integrations and reporting",
            "Bespoke implementation support",
        ],
        "credits": {
            "workspace": None,
        },
        "limits": {
            "audit_runs": None,
            "saved_history": None,
            "premium_recommendations": None,
            "seo_refreshes": None,
            "aeo_analyses": None,
            "exports": None,
            "content_drafts": None,
            "share_links": None,
            "tracked_competitors": None,
            "competitor_pages_per_refresh": None,
            "backlink_prospects": None,
            "automation_projects": None,
        },
        "feature_flags": {
            "workspace_dashboard_enabled": True,
            "seo_workspace_enabled": True,
            "aeo_workspace_enabled": True,
            "content_workspace_enabled": True,
            "backlink_workspace_enabled": True,
            "recurring_audits_enabled": True,
            "export_reports_enabled": True,
            "email_reports_enabled": True,
            "competitor_tracking_enabled": True,
            "stakeholder_sharing_enabled": True,
            "action_packs_enabled": True,
            "campaign_tracking_enabled": True,
            "cross_module_summary_enabled": True,
            "custom_workflows_enabled": True,
            "priority_support_enabled": True,
        },
        "upgrade_message": "Enterprise is reserved for real operational complexity, not ordinary workspace usage.",
    },
]


_LIMIT_SUMMARY_LABELS = {
    "audit_runs": "Audit runs",
    "saved_history": "Saved runs",
    "premium_recommendations": "Detailed recommendations",
    "seo_refreshes": "SEO refreshes",
    "aeo_analyses": "AEO analyses",
    "exports": "Exports",
    "share_links": "Share links",
    "tracked_competitors": "Tracked competitors",
    "competitor_pages_per_refresh": "Competitor pages per refresh",
}


def get_plan_definition(slug):
    normalized = str(slug or "").strip().lower()
    for definition in PLAN_DEFINITIONS:
        if definition["slug"] == normalized:
            return definition
    return None


def get_plan_definitions(*, include_free=True):
    if include_free:
        return list(PLAN_DEFINITIONS)
    return [item for item in PLAN_DEFINITIONS if item["slug"] != "free"]


def build_limit_summary(definition):
    limits = definition.get("limits", {})
    summary = []
    for key, label in _LIMIT_SUMMARY_LABELS.items():
        if key not in limits:
            continue
        value = limits.get(key)
        summary.append(
            {
                "key": key,
                "label": label,
                "value": value,
                "display": "Unlimited" if value is None else str(value),
            }
        )
    return summary


def build_plan_metadata(definition):
    return {
        "features": dict(definition.get("feature_flags", {})),
        "limits": dict(definition.get("limits", {})),
        "credits": dict(definition.get("credits", {})),
        "label": definition.get("label", ""),
        "audience": definition.get("audience", ""),
        "marketing_features": list(definition.get("features", [])),
        "upgrade_message": definition.get("upgrade_message", ""),
    }


def build_marketing_packages(*, include_free=False):
    packages = []
    for definition in get_plan_definitions(include_free=include_free):
        packages.append(
            {
                "name": definition["name"],
                "slug": definition["slug"],
                "price": definition["price_label"],
                "label": definition["label"],
                "features": list(definition.get("features", [])),
                "limits_summary": build_limit_summary(definition),
                "credits": dict(definition.get("credits", {})),
                "description": definition.get("description", ""),
                "audience": definition.get("audience", ""),
                "upgrade_message": definition.get("upgrade_message", ""),
                "is_custom": definition.get("is_custom", False),
                "is_free": definition["slug"] == "free",
            }
        )
    return packages


def build_workspace_plan_defaults(definition):
    limits = definition.get("limits", {})
    feature_flags = definition.get("feature_flags", {})
    return {
        "name": definition["name"],
        "price_label": definition["price_label"],
        "description": definition.get("description", ""),
        "sort_order": definition.get("sort_order", 0),
        "monthly_audits_limit": limits.get("audit_runs"),
        "history_limit": limits.get("saved_history"),
        "premium_recommendation_limit": limits.get("premium_recommendations"),
        "recurring_audits_enabled": feature_flags.get("recurring_audits_enabled", False),
        "export_reports_enabled": feature_flags.get("export_reports_enabled", False),
        "email_reports_enabled": feature_flags.get("email_reports_enabled", False),
        "competitor_tracking_enabled": feature_flags.get("competitor_tracking_enabled", False),
        "stakeholder_sharing_enabled": feature_flags.get("stakeholder_sharing_enabled", False),
        "metadata": build_plan_metadata(definition),
    }
