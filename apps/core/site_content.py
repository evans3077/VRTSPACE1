from copy import deepcopy
from itertools import count

from apps.core.plan_catalog import build_marketing_packages
from django.utils.text import slugify

SERVICE_GROUPS = [
    {
        "anchor": "services",
        "tone": "signal",
        "title": "Focused Services",
        "lead": "Three clear ways we help businesses get found, understand what is blocking growth, and improve visibility across search and AI answers.",
        "services": [
            {
                "name": "SEO",
                "summary": "Improve how your business gets found in organic search.",
                "best_for": "Businesses that need stronger rankings, clearer page priorities, and a roadmap grounded in real search demand.",
                "why_it_matters": "Search still captures some of the highest-intent traffic on the internet, but only when the right pages and technical signals are working together.",
                "outcome": "A clearer SEO roadmap tied to the pages, fixes, and opportunities most likely to move visibility.",
                "bullets": [
                    "Technical SEO improvements",
                    "Keyword and page-priority planning",
                    "On-page optimization guidance",
                    "Competitor-backed opportunities",
                ],
                "system_feature": "Competitor-backed SEO roadmap",
            },
            {
                "name": "Audit",
                "summary": "See what is hurting visibility, trust, and conversion before you guess.",
                "best_for": "Teams that know something is off but need a clear diagnosis before committing more time or budget.",
                "why_it_matters": "An audit replaces guesswork with evidence so you can see what is blocking growth before choosing a deeper engagement.",
                "outcome": "A live diagnosis with priority-ranked next steps across technical health, SEO, and AI visibility.",
                "bullets": [
                    "Technical and content diagnostics",
                    "Priority-ranked fixes",
                    "Performance and trust checks",
                    "Clear next-step recommendations",
                ],
                "system_feature": "Live website audit with grouped recommendations",
            },
            {
                "name": "AEO",
                "summary": "Make your content easier for AI systems to understand, quote, and trust.",
                "best_for": "Brands that want their site to be easier for AI tools to interpret, summarize, and cite.",
                "why_it_matters": "More discovery now starts inside AI interfaces, where structure, entities, and answer quality shape whether your site gets surfaced.",
                "outcome": "A sharper path to answer-ready pages, stronger entity clarity, and better citation potential.",
                "bullets": [
                    "AI visibility analysis",
                    "Entity and structure checks",
                    "Citation-readiness recommendations",
                    "Answer-focused content guidance",
                ],
                "system_feature": "AI visibility and citation-readiness scoring",
            },
        ],
    }
]

PACKAGES = build_marketing_packages(include_free=False)

SYSTEM_BLOCKS = [
    {
        "title": "Audit first",
        "body": "Start with a live audit so the next decision comes from evidence instead of assumptions.",
    },
    {
        "title": "Improve what matters",
        "body": "Use the roadmap to focus on the SEO and AI-visibility fixes that should move rankings, trust, and lead flow.",
    },
    {
        "title": "Scale only when needed",
        "body": "Keep the public message simple, then let the workspace and plan system handle the deeper operational layers behind the scenes.",
    },
]

VALUE_PILLARS = [
    {
        "title": "Clarity before action",
        "body": "You should know what is wrong, why it matters, and what to fix first without decoding technical noise.",
    },
    {
        "title": "Visibility that covers now and next",
        "body": "The goal is not only better rankings in Google, but stronger presence in AI-generated answers too.",
    },
    {
        "title": "A service experience that feels guided",
        "body": "The site should help visitors move from uncertainty to action through a clear audit and contact journey.",
    },
]

ENGAGEMENT_STEPS = [
    {
        "phase": "01",
        "title": "Discover",
        "body": "Start with your website, your market, and the goals that matter most to the business.",
    },
    {
        "phase": "02",
        "title": "Audit",
        "body": "Run the audit to expose the highest-impact issues across SEO, trust, speed, and AI visibility.",
    },
    {
        "phase": "03",
        "title": "Improve",
        "body": "Turn the findings into a practical roadmap across SEO and AEO instead of generic advice.",
    },
    {
        "phase": "04",
        "title": "Grow",
        "body": "Use the clearer direction to improve rankings, confidence, and lead quality over time.",
    },
]

FAQS = [
    {
        "question": "What does VRT Space Agency actually help with?",
        "answer": "We focus on three things: SEO, website audits, and AEO. That means helping you get found, understand what is holding the site back, and improve visibility in both search results and AI answers.",
    },
    {
        "question": "Why start with an audit?",
        "answer": "Because it is the fastest way to see what is hurting growth before spending time or money in the wrong place. The audit shows the gaps, the risks, and the next priorities.",
    },
    {
        "question": "How is AEO different from SEO?",
        "answer": "SEO helps you win better rankings and clicks in search engines. AEO helps your content become easier for AI systems to understand, summarize, and cite when people ask direct questions.",
    },
    {
        "question": "Is this a service or a product?",
        "answer": "The public experience is service-led, with the audit as the main starting point. Behind that, the workspace system supports deeper analysis, reporting, and follow-through when needed.",
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
            "best_for": service.get("best_for", ""),
            "why_it_matters": service.get("why_it_matters", ""),
            "outcome": service.get("outcome", ""),
            "bullets": deepcopy(service["bullets"]),
            "system_feature": service["system_feature"],
            "value_statement": (
                f"{service['name']} is positioned as a clear commercial offer inside the audit-led VRT SPACE journey, "
                "not as a disconnected technical module."
            ),
            "experience_points": {
                "seo": [
                    "See where search visibility is underperforming and why.",
                    "Turn benchmark findings into page and keyword priorities that make commercial sense.",
                    "Focus effort on the improvements most likely to strengthen rankings and qualified traffic.",
                ],
                "audit": [
                    "Replace assumptions with a clear diagnosis before deeper work begins.",
                    "See what is hurting trust, speed, SEO, and AI visibility in one place.",
                    "Walk away with a practical next-step list instead of generic advice.",
                ],
                "aeo": [
                    "Understand how clearly your site reads to AI systems and answer engines.",
                    "Strengthen entity clarity, structure, and answer coverage on the pages that matter.",
                    "Improve the chances that your business is surfaced and cited in AI-driven discovery.",
                ],
            }.get(slug, [
                "Start with evidence instead of guesswork.",
                "Translate technical findings into a clear business next step.",
                "Move from visibility problems to a practical improvement plan.",
            ]),
            "custom_inquiry": False,
        }


SERVICE_PAGE_LIST = list(SERVICE_PAGE_LOOKUP.values())
