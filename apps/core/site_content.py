from copy import deepcopy
from itertools import count

from django.utils.text import slugify

SERVICE_GROUPS = [
    {
        "anchor": "revenue",
        "tone": "signal",
        "title": "Core Revenue Services",
        "lead": "Primary offers built to drive revenue and anchor the platform.",
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
        "title": "Growth and Performance Services",
        "lead": "Upsells that increase client lifetime value and make the stack stick.",
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
        "title": "AI-Powered Services",
        "lead": "This is where VRT SPACE wins against most agencies.",
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
            },
        ],
    },
    {
        "anchor": "tools",
        "tone": "signal",
        "title": "Tools-as-a-Service",
        "lead": "Lead magnets that bring traffic, require email, and trigger follow-up automatically.",
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
        "title": "Enterprise and High-Ticket Services",
        "lead": "Designed for bigger clients with more complex search environments.",
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
        "title": "Support and Retention Services",
        "lead": "Monthly services that keep clients paying and the system improving.",
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

PACKAGES = [
    {
        "name": "Starter",
        "price": "~$200",
        "label": "Low-friction entry",
        "features": [
            "Basic SEO setup",
            "Audit report",
            "Fast recommendations",
        ],
    },
    {
        "name": "Growth",
        "price": "~$500",
        "label": "Most practical for growing brands",
        "features": [
            "SEO and content",
            "Basic AEO",
            "Core tracking",
        ],
    },
    {
        "name": "Authority",
        "price": "$1000+",
        "label": "Flagship offer",
        "features": [
            "Full SEO and AEO",
            "AI visibility tracking",
            "CRO layer",
        ],
    },
    {
        "name": "Enterprise",
        "price": "Custom",
        "label": "Complex environments",
        "features": [
            "Custom architecture",
            "Cross-market strategy",
            "Executive reporting",
        ],
    },
]

SYSTEM_BLOCKS = [
    {
        "title": "What the platform really does",
        "body": "Sell services, run audits, convert interest, and surface the next upsell without depending on cold outreach.",
    },
    {
        "title": "Core system models",
        "body": "Service, ServicePackage, Feature, Tool, Lead, AuditResult, ClientProject, and Report should remain first-class concepts.",
    },
    {
        "title": "Internal systems",
        "body": "Admin dashboard, client dashboard, and an automation engine for scoring, follow-up, and reporting.",
    },
]

VALUE_PILLARS = [
    {
        "title": "Clarity from the first week",
        "body": "Clients should know what is being fixed, why it matters, and what revenue signal it should move.",
    },
    {
        "title": "A site that feels like a closer",
        "body": "Every page should justify value, reduce doubt, and create the next logical action without hard-selling.",
    },
    {
        "title": "Reporting that proves business value",
        "body": "Traffic, citations, lead quality, and conversion movement should connect back to decisions that executives understand.",
    },
]

ENGAGEMENT_STEPS = [
    {
        "phase": "01",
        "title": "Discover the opportunity",
        "body": "Start with technical, content, and AI-surface audits to expose what is blocking growth and where the easiest wins live.",
    },
    {
        "phase": "02",
        "title": "Design the growth system",
        "body": "Package SEO, AEO, web, analytics, and CRO into a roadmap that fits the client's stage and budget.",
    },
    {
        "phase": "03",
        "title": "Deploy authority assets",
        "body": "Ship fast pages, direct-answer content, structured data, tools, and trust signals that improve both ranking and conversion.",
    },
    {
        "phase": "04",
        "title": "Compound and retain",
        "body": "Use reporting, monitoring, and ongoing experiments to protect performance and naturally expand the engagement.",
    },
]

FAQS = [
    {
        "question": "Why combine SEO and AEO instead of selling them separately?",
        "answer": "Because clients do not buy channels. They buy discoverability, trust, and pipeline. The site should present SEO and AEO as one commercial system with different execution layers.",
    },
    {
        "question": "How does VRT SPACE create more value than a normal agency site?",
        "answer": "By using lead magnets, dashboards, scoring, and clear packaging so the website educates, qualifies, and upsells instead of waiting for a manual sales conversation.",
    },
    {
        "question": "Who is the strongest fit for the flagship Authority package?",
        "answer": "Brands that need traditional rankings, AI visibility, better conversion paths, and a reporting layer that can justify retained spend.",
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
                "not as a disconnected one-off service."
            ),
            "experience_points": [
                "Start with a clear diagnosis of what is blocking discovery, trust, or conversion.",
                "Translate findings into a roadmap that clients can understand without technical guesswork.",
                "Deliver implementation with measurable movement and obvious next-step opportunities.",
            ],
        }


SERVICE_PAGE_LIST = list(SERVICE_PAGE_LOOKUP.values())
