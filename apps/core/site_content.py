from copy import deepcopy
from itertools import count

from apps.core.plan_catalog import build_marketing_packages
from django.utils.text import slugify

SERVICE_GROUPS = [
    {
        "anchor": "revenue",
        "tone": "signal",
        "title": "Core Growth Modules",
        "lead": "The main product paths that diagnose demand, improve visibility, and anchor the platform.",
        "services": [
            {
                "name": "SEO Services",
                "summary": "The ranking foundation.",
                "bullets": [
                    "Technical SEO",
                    "On-page SEO",
                    "Keyword research",
                    "Internal linking optimization",
                    "Site audits",
                ],
                "system_feature": "SEO audit tool and site health dashboard",
            },
            {
                "name": "AEO / AI Search Optimization",
                "summary": "The differentiation layer.",
                "bullets": [
                    "ChatGPT visibility optimization",
                    "Google AI Overviews optimization",
                    "Entity SEO",
                    "LLM content structuring",
                    "Schema optimization",
                ],
                "system_feature": "AI visibility score and citation tracking system",
            },
            {
                "name": "Website Development",
                "summary": "The delivery engine.",
                "bullets": [
                    "High-performance websites in Django or static delivery",
                    "SEO-ready architecture",
                    "Landing pages",
                    "Conversion-optimized builds",
                ],
                "system_feature": "Website audit upsell and template system",
                "custom_inquiry": True,
            },
            {
                "name": "Content Marketing",
                "summary": "The authority compounding layer.",
                "bullets": [
                    "Blog writing with cluster strategy",
                    "Pillar page creation",
                    "Thought leadership content",
                    "SEO articles",
                ],
                "system_feature": "Content planner and internal linking engine",
            },
        ],
    },
    {
        "anchor": "growth",
        "tone": "mist",
        "title": "Growth and Performance Modules",
        "lead": "Layers that improve existing traffic value and keep the stack useful over time.",
        "services": [
            {
                "name": "Conversion Rate Optimization",
                "summary": "Improve the value of existing traffic.",
                "bullets": [
                    "Landing page optimization",
                    "A/B testing",
                    "Funnel analysis",
                ],
                "system_feature": "CTA tracking and conversion analytics dashboard",
            },
            {
                "name": "Local SEO",
                "summary": "Important for the Kenya market and service area capture.",
                "bullets": [
                    "Google Business Profile optimization",
                    "Local citations",
                    "Maps ranking",
                ],
                "system_feature": "Local audit tool and NAP consistency checker",
            },
            {
                "name": "Analytics and Tracking Setup",
                "summary": "Measure what moves pipeline.",
                "bullets": [
                    "GA4 setup",
                    "Conversion tracking",
                    "Funnel tracking",
                ],
                "system_feature": "Client-facing dashboard inside VRT SPACE",
            },
            {
                "name": "Backlink and Authority Building",
                "summary": "Expand trust outside owned channels.",
                "bullets": [
                    "Digital PR",
                    "Link building",
                    "Brand mentions",
                ],
                "system_feature": "Link tracker and authority score",
            },
        ],
    },
    {
        "anchor": "ai-services",
        "tone": "dark",
        "title": "AI Visibility Modules",
        "lead": "The layer that makes the platform useful across answer engines and AI search surfaces.",
        "services": [
            {
                "name": "AI Visibility Monitoring",
                "summary": "Track brand presence inside answer engines.",
                "bullets": [
                    "Track mentions in AI tools",
                    "Measure share of voice",
                    "Monitor answer presence",
                ],
                "system_feature": "AI monitoring dashboard",
            },
            {
                "name": "AI Content Optimization",
                "summary": "Rewrite and structure content for LLM consumption.",
                "bullets": [
                    "Structured answers",
                    "Snippet optimization",
                    "Entity-rich formatting",
                ],
                "system_feature": "Reusable AI-ready content patterns",
            },
            {
                "name": "AI Chatbot Integration",
                "summary": "Use on-site assistants to capture and route demand.",
                "bullets": [
                    "Website chatbot setup",
                    "Lead capture bots",
                    "FAQ bots",
                ],
                "system_feature": "Chatbot builder in a later phase",
                "custom_inquiry": True,
            },
        ],
    },
    {
        "anchor": "tools",
        "tone": "signal",
        "title": "Tools and Workspaces",
        "lead": "The self-serve entry points that turn a scan into a saved user workflow.",
        "services": [
            {
                "name": "Free SEO Audit Tool",
                "summary": "Scan a website and return a score plus recommendations.",
                "bullets": [
                    "Website scan",
                    "Score output",
                    "Recommendations",
                ],
                "system_feature": "Lead capture and automated qualification",
            },
            {
                "name": "AI Visibility Audit Tool",
                "summary": "Check whether a brand appears in AI answers.",
                "bullets": [
                    "Brand presence checks",
                    "Citation review",
                    "Opportunity detection",
                ],
                "system_feature": "AI visibility score",
            },
            {
                "name": "SEO Score Calculator",
                "summary": "Simple scoring experience similar to top agency tools.",
                "bullets": [
                    "Fast scoring",
                    "Email gating",
                    "Follow-up sequencing",
                ],
                "system_feature": "Top-of-funnel lead magnet",
            },
            {
                "name": "Page Speed Analyzer",
                "summary": "Explain performance bottlenecks and upsell remediation.",
                "bullets": [
                    "Performance breakdown",
                    "Priority fixes",
                    "Rebuild opportunities",
                ],
                "system_feature": "Speed-based upsell path",
            },
        ],
    },
    {
        "anchor": "enterprise",
        "tone": "mist",
        "title": "Enterprise and Advisory Paths",
        "lead": "Reserved for larger environments, higher complexity, or requests that need direct scope review.",
        "services": [
            {
                "name": "Enterprise SEO",
                "summary": "High-complexity optimization at scale.",
                "bullets": [
                    "Large-scale optimization",
                    "Technical audits",
                    "Strategy consulting",
                ],
                "system_feature": "Executive-grade reporting and roadmaping",
            },
            {
                "name": "International SEO",
                "summary": "Growth beyond one market or one language.",
                "bullets": [
                    "Multi-language SEO",
                    "Global targeting",
                    "Localization support",
                ],
                "system_feature": "Multi-market architecture planning",
            },
            {
                "name": "SEO Strategy Consulting",
                "summary": "Advisory for teams that need direction before execution.",
                "bullets": [
                    "Monthly advisory",
                    "Custom roadmap",
                    "Search prioritization",
                ],
                "system_feature": "Decision support for in-house teams",
            },
        ],
    },
    {
        "anchor": "retention",
        "tone": "dark",
        "title": "Retention and Reporting Modules",
        "lead": "Ongoing layers that protect performance and keep decision-making visible after setup.",
        "services": [
            {
                "name": "Website Maintenance",
                "summary": "Protect performance and reliability after launch.",
                "bullets": [
                    "Updates",
                    "Performance monitoring",
                    "Security fixes",
                ],
                "system_feature": "Ongoing delivery layer",
            },
            {
                "name": "Hosting and Performance",
                "summary": "Managed infrastructure for speed and stability.",
                "bullets": [
                    "Managed hosting",
                    "CDN setup",
                    "Performance tuning",
                ],
                "system_feature": "Managed performance stack",
            },
            {
                "name": "Reporting and Insights",
                "summary": "Translate execution into visible business movement.",
                "bullets": [
                    "Monthly reports",
                    "KPI dashboards",
                    "Executive summaries",
                ],
                "system_feature": "Retention-focused reporting cadence",
            },
        ],
    },
]

PACKAGES = build_marketing_packages(include_free=False)

SYSTEM_BLOCKS = [
    {
        "title": "What the platform really does",
        "body": "Run audits, create workspaces, expose plan upgrades, and support custom delivery without depending on cold outreach.",
    },
    {
        "title": "Core system models",
        "body": "Service, plan, tool, lead, audit result, client project, and report should remain first-class concepts.",
    },
    {
        "title": "Internal systems",
        "body": "Operations dashboard, user workspace, and an automation engine for scoring, follow-up, and reporting.",
    },
]

VALUE_PILLARS = [
    {
        "title": "Clarity from the first week",
        "body": "Users should know what is being fixed, why it matters, and what metric it should move.",
    },
    {
        "title": "A site that routes the next action",
        "body": "Every page should reduce doubt and move the user toward an audit, a workspace, a plan, or a custom request.",
    },
    {
        "title": "Reporting that proves business value",
        "body": "Traffic, citations, lead quality, and conversion movement should connect back to decisions that teams can understand.",
    },
]

ENGAGEMENT_STEPS = [
    {
        "phase": "01",
        "title": "Run the first audit",
        "body": "Start with technical, content, and AI-surface diagnostics to expose what is blocking growth and where the easiest wins live.",
    },
    {
        "phase": "02",
        "title": "Open the workspace",
        "body": "Save results, review grouped recommendations, and choose the right plan path for the current stage and budget.",
    },
    {
        "phase": "03",
        "title": "Unlock the right modules",
        "body": "Add the monitoring, content, reporting, and performance layers that fit the diagnosed gaps and the growth target.",
    },
    {
        "phase": "04",
        "title": "Expand when complexity requires it",
        "body": "Use reporting, monitoring, automation, and custom implementation support when self-serve modules are no longer enough.",
    },
]

FAQS = [
    {
        "question": "Why combine SEO and AEO instead of selling them separately?",
        "answer": "Because buyers do not want disconnected channels. They want one system that improves discoverability, trust, and pipeline across both classic search and AI answers.",
    },
    {
        "question": "How does VRT SPACE work as a product instead of a brochure site?",
        "answer": "By using audits, workspaces, scoring, and clear packages so the site can diagnose, educate, and route upgrades before a direct conversation is needed.",
    },
    {
        "question": "Who is the strongest fit for the flagship Authority package?",
        "answer": "Brands that need traditional rankings, AI visibility, better conversion paths, and a reporting layer that can justify ongoing investment.",
    },
]


SERVICE_PAGE_LOOKUP = {}
_service_order = count(1)
for group in SERVICE_GROUPS:
    for service in group["services"]:
        slug = slugify(service["name"])
        SERVICE_PAGE_LOOKUP[slug] = {
            "slug": slug,
            "order": next(_service_order),
            "group_title": group["title"],
            "group_lead": group["lead"],
            "tone": group["tone"],
            "name": service["name"],
            "summary": service["summary"],
            "bullets": deepcopy(service["bullets"]),
            "system_feature": service["system_feature"],
            "value_statement": (
                f"{service['name']} is positioned as part of the VRT SPACE growth system, "
                "not as a disconnected one-off deliverable."
            ),
            "experience_points": [
                "Start with a clear diagnosis of what is blocking discovery, trust, or conversion.",
                "Translate findings into a roadmap that users can understand without technical guesswork.",
                "Connect implementation to measurable movement and the next logical product unlock.",
            ],
            "custom_inquiry": service.get("custom_inquiry", False),
        }


SERVICE_PAGE_LIST = list(SERVICE_PAGE_LOOKUP.values())
