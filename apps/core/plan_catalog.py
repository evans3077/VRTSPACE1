PLAN_DEFINITIONS = [
    {
        "slug": "free",
        "name": "Free",
        "price_label": "$0",
        "monthly_amount_cents": 0,
        "label": "Audit entry layer",
        "description": "Run two starter audits, save one website, and review the guided diagnosis before deciding whether to go deeper.",
        "sort_order": 0,
        "is_public": True,
        "is_paid": False,
        "is_custom": False,
        "audience": "Early evaluation and proof of value",
        "features": [
            "2 starter audits each cycle",
            "1 tracked website",
            "Guided diagnosis with critical issues and quick wins",
            "Upgrade path into SEO, AEO, and workspace history",
        ],
        "credits": {
            "workspace": 8,
        },
        "limits": {
            "audit_runs": 2,
            "saved_history": 2,
            "premium_recommendations": 3,
            "seo_refreshes": 0,
            "aeo_analyses": 0,
            "exports": 0,
            "content_drafts": 0,
            "share_links": 0,
            "tracked_sites": 1,
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
            "clinical_intelligence_enabled": False,
        },
        "upgrade_message": "Upgrade when you need more websites, deeper audit detail, and access to the SEO and AEO workspaces.",
    },
    {
        "slug": "starter",
        "name": "Starter",
        "price_label": "$59",
        "monthly_amount_cents": 5900,
        "label": "Focused operator plan",
        "description": "Detailed audits for operators managing a small number of sites and ready to act on the findings inside the workspace.",
        "sort_order": 10,
        "is_public": True,
        "is_paid": True,
        "is_custom": False,
        "audience": "Solo operators and small local businesses",
        "features": [
            "Detailed audit workspace with action-ready recommendations",
            "3 tracked websites",
            "Starter SEO and AEO runs on top of the audit base",
            "Credits for reruns, exports, and guided execution",
        ],
        "credits": {
            "workspace": 40,
        },
        "limits": {
            "audit_runs": 8,
            "saved_history": 12,
            "premium_recommendations": 8,
            "seo_refreshes": 4,
            "aeo_analyses": 4,
            "exports": 2,
            "content_drafts": 2,
            "share_links": 1,
            "tracked_sites": 3,
            "tracked_competitors": 2,
            "competitor_pages_per_refresh": 2,
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
            "clinical_intelligence_enabled": True,
        },
        "upgrade_message": "Upgrade when you need more websites, recurring workflows, richer exports, and deeper competitor context.",
    },
    {
        "slug": "growth",
        "name": "Growth",
        "price_label": "$149",
        "monthly_amount_cents": 14900,
        "label": "Team growth plan",
        "description": "The operating plan for teams that want recurring audits, deeper SEO and AEO execution, reporting, and structured content work.",
        "sort_order": 20,
        "is_public": True,
        "is_paid": True,
        "is_custom": False,
        "audience": "Serious SMBs and lean growth teams",
        "features": [
            "Deeper audit detail and recurring validation",
            "10 tracked websites",
            "Richer competitor benchmarking and exports",
            "Content workflows and stakeholder-ready reporting",
        ],
        "credits": {
            "workspace": 120,
        },
        "limits": {
            "audit_runs": 24,
            "saved_history": 30,
            "premium_recommendations": 16,
            "seo_refreshes": 12,
            "aeo_analyses": 10,
            "exports": 12,
            "content_drafts": 16,
            "share_links": 6,
            "tracked_sites": 10,
            "tracked_competitors": 5,
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
            "clinical_intelligence_enabled": True,
        },
        "upgrade_message": "Upgrade when you need more tracked websites, deeper authority workflows, and larger monthly capacity.",
    },
    {
        "slug": "authority",
        "name": "Authority",
        "price_label": "$349",
        "monthly_amount_cents": 34900,
        "label": "Authority operating system",
        "description": "Full execution plan for teams running audit, SEO, AEO, content, reporting, and authority-building as one connected system.",
        "sort_order": 30,
        "is_public": True,
        "is_paid": True,
        "is_custom": False,
        "audience": "Agencies, multi-location brands, and execution-heavy teams",
        "features": [
            "Deepest audit layer with full technical visibility",
            "25 tracked websites",
            "Full SEO, AEO, content, and authority workflows",
            "Advanced sharing, automation, and reporting",
        ],
        "credits": {
            "workspace": 320,
        },
        "limits": {
            "audit_runs": 80,
            "saved_history": None,
            "premium_recommendations": None,
            "seo_refreshes": 36,
            "aeo_analyses": 24,
            "exports": None,
            "content_drafts": 60,
            "share_links": 25,
            "tracked_sites": 25,
            "tracked_competitors": 10,
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
            "clinical_intelligence_enabled": True,
        },
        "upgrade_message": "Move to Enterprise only when you need multi-market delivery, custom integrations, or bespoke workflow complexity.",
    },
    {
        "slug": "enterprise",
        "name": "Enterprise",
        "price_label": "Custom",
        "monthly_amount_cents": None,
        "label": "Custom environments",
        "description": "Reserved for multi-market delivery, custom integrations, high-touch reporting, and bespoke implementation.",
        "sort_order": 40,
        "is_public": False,
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
            "tracked_sites": None,
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
            "clinical_intelligence_enabled": True,
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
    "content_drafts": "Content drafts",
    "share_links": "Share links",
    "tracked_sites": "Tracked websites",
    "tracked_competitors": "Tracked competitors",
    "competitor_pages_per_refresh": "Competitor pages per refresh",
    "backlink_prospects": "Backlink prospects",
    "automation_projects": "Automated projects",
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
        "monthly_amount_cents": definition.get("monthly_amount_cents"),
    }


def get_plan_monthly_amount_cents(slug):
    definition = get_plan_definition(slug)
    if definition is None:
        return None
    return definition.get("monthly_amount_cents")


def build_marketing_packages(*, include_free=False):
    packages = []
    for definition in get_plan_definitions(include_free=include_free):
        if not definition.get("is_public", True):
            continue
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
