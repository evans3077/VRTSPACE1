from copy import deepcopy
from itertools import count

from apps.core.plan_catalog import build_marketing_packages
from django.utils.text import slugify

SERVICE_GROUPS = [
    {
        "anchor": "services",
        "tone": "signal",
        "title": "Core Analysis Modules",
        "lead": "The three essential tools that diagnose your website, reveal gaps, and improve AI visibility.",
        "services": [
            {
                "name": "Website Audit",
                "summary": "Live site diagnostics and performance analysis.",
                "bullets": [
                    "Google PageSpeed Insights integration",
                    "Technical SEO checks",
                    "Mobile and accessibility audits",
                    "Performance bottlenecks identification",
                    "Actionable improvement recommendations",
                ],
                "system_feature": "Free audit tool with detailed reports",
            },
            {
                "name": "SEO Analysis",
                "summary": "Competitive intelligence and strategic improvements.",
                "bullets": [
                    "Keyword gap analysis",
                    "Competitor comparison",
                    "Content pattern discovery",
                    "Backlink opportunity identification",
                    "Priority action roadmap",
                ],
                "system_feature": "SEO intelligence engine with competitor insights",
            },
            {
                "name": "AEO / AI Visibility",
                "summary": "Optimize for AI-powered search and answer engines.",
                "bullets": [
                    "ChatGPT and Gemini optimization",
                    "Entity and topic coverage analysis",
                    "Structured data readiness",
                    "AI answer simulation",
                    "Citation-friendly content structuring",
                ],
                "system_feature": "AI visibility score and optimization recommendations",
            },
        ],
    },
]

PACKAGES = build_marketing_packages(include_free=False)

SYSTEM_BLOCKS = [
    {
        "title": "Start with one clear diagnosis",
        "body": "The audit shows the biggest blockers first so you know where to focus before guessing what to change.",
    },
    {
        "title": "Keep everything in one workspace",
        "body": "Save runs, compare changes, and keep the next action visible instead of losing context across separate tools.",
    },
    {
        "title": "Rerun after fixes and track progress",
        "body": "Use the same flow again after updates so improvements become visible, measurable, and easier to share with your team.",
    },
]

VALUE_PILLARS = [
    {
        "title": "See the biggest issues first",
        "body": "The platform groups the highest-impact problems so you can stop guessing and start with what matters most.",
    },
    {
        "title": "Understand what to do next",
        "body": "Audit, SEO, and AEO signals work together so the next step feels clear instead of technical or overwhelming.",
    },
    {
        "title": "Keep progress visible over time",
        "body": "Workspaces, reruns, and history help you prove what improved and what still needs attention after each change.",
    },
]

ENGAGEMENT_STEPS = [
    {
        "phase": "01",
        "title": "Run the first audit",
        "body": "Scan your website to surface the technical, search, and AI-visibility issues that are holding it back.",
    },
    {
        "phase": "02",
        "title": "Review SEO and AEO gaps",
        "body": "See where competitors are stronger, what your content is missing, and how answer-readiness can improve.",
    },
    {
        "phase": "03",
        "title": "Save the work in a workspace",
        "body": "Keep recommendations, audit history, credits, and next steps together so your team can keep moving.",
    },
    {
        "phase": "04",
        "title": "Rerun after fixes",
        "body": "Validate what improved, what still needs attention, and where the next round of gains should come from.",
    },
]

FAQS = [
    {
        "question": "What happens after I run the audit?",
        "answer": "You get a clearer view of the biggest issues, the quickest wins, and the next steps for SEO and AI visibility. You can then save the work in a workspace and rerun after fixes.",
    },
    {
        "question": "Why combine audit, SEO, and AEO in one system?",
        "answer": "Because most websites need more than one kind of fix. The audit finds the issues, SEO shows what competitors are doing better, and AEO helps you improve visibility in AI-driven answers.",
    },
    {
        "question": "Do I need a workspace to keep using the platform?",
        "answer": "A workspace keeps your audit history, next actions, and reruns together, which makes it much easier to track progress over time.",
    },
    {
        "question": "When should I ask for custom help?",
        "answer": "Start with the product first. Use custom scoping only when the work goes beyond the standard audit, SEO, AEO, and workspace flow.",
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
