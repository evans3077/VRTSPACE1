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


def build_faq_schema(faqs):
    """Return a schema.org FAQPage dict from a list of {question, answer, detail?}.

    `detail` (when present) is appended to the answer text so the structured
    data carries the same full answer a reader sees in the accordion — keeping
    the visible markup and the JSON-LD identical, which is what Google and
    answer engines expect.
    """
    main_entity = []
    for item in faqs or []:
        answer_text = item["answer"]
        detail = item.get("detail")
        if detail:
            answer_text = f"{answer_text} {detail}"
        main_entity.append(
            {
                "@type": "Question",
                "name": item["question"],
                "acceptedAnswer": {"@type": "Answer", "text": answer_text},
            }
        )
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": main_entity,
    }


# ── Curated FAQs ────────────────────────────────────────────────────────────
# Written answer-first (the opening sentence is the liftable snippet) and seeded
# with the terms people actually type/ask: "AI visibility", "answer engine
# optimization", "ChatGPT / Gemini / Perplexity", "SEO audit". These power both
# the visible accordion (includes/faq_section.html) and FAQPage JSON-LD.

# Per-service FAQs, keyed by the slugified service name.
SERVICE_FAQS = {
    "website-audit": [
        {
            "question": "What does the free website audit check?",
            "answer": "The audit checks technical SEO, page speed, mobile and accessibility health, on-page structure, and AI-readiness in a single run.",
            "detail": "It uses live data — including Google PageSpeed Insights — to surface the issues most likely to be holding back rankings, conversions, and AI visibility, then ranks them so you know what to fix first.",
        },
        {
            "question": "How long does an SEO audit take?",
            "answer": "Most audits complete in a few minutes, and you get a shareable report the moment the run finishes.",
            "detail": "Larger sites take a little longer because more pages are crawled, but you never have to wait for a human analyst — the report is generated automatically.",
        },
        {
            "question": "Is the website audit really free?",
            "answer": "Yes. You can run a full diagnostic audit for free without a credit card.",
            "detail": "Free runs include your overall score and category gauges. Paid plans unlock more audits per month, deeper recommendations, PDF export, and saved workspace history.",
        },
        {
            "question": "What should I do after I get my audit results?",
            "answer": "Start with the highest-impact issues the report flags first, then rerun the audit after each fix to confirm the score is moving.",
            "detail": "Saving the audit in a workspace keeps your history, recommendations, and next actions together so progress stays measurable over time.",
        },
    ],
    "seo-analysis": [
        {
            "question": "What is included in the SEO analysis?",
            "answer": "SEO analysis covers keyword gap analysis, competitor comparison, content pattern discovery, backlink opportunities, and a prioritised action roadmap.",
            "detail": "It shows where competitors are stronger and which gaps to close first, so the next step is clear instead of buried in raw data.",
        },
        {
            "question": "How is this different from Ahrefs or SEMrush?",
            "answer": "VRT SPACE pairs traditional SEO analysis with AI visibility (AEO) tracking and change-over-time scoring in one workspace.",
            "detail": "Incumbent tools tell you how you rank on Google. We also show whether AI answer engines like ChatGPT, Gemini, and Perplexity cite you — the search surface those tools don't measure.",
        },
        {
            "question": "Do I need technical SEO skills to use it?",
            "answer": "No. Findings are translated into plain-language next actions you can follow without a technical background.",
            "detail": "Each recommendation explains what to change and why it matters, so growth teams and founders can act without guessing.",
        },
        {
            "question": "How does SEO analysis improve AI visibility?",
            "answer": "Strong technical SEO and clear topic coverage are the foundation AI engines use to understand and cite a site.",
            "detail": "Fixing crawlability, structure, and content gaps makes your pages easier for both search crawlers and large language models to read, quote, and recommend.",
        },
    ],
    "aeo-ai-visibility": [
        {
            "question": "What is Answer Engine Optimization (AEO)?",
            "answer": "Answer Engine Optimization is the practice of making your brand discoverable and citable inside AI answers from tools like ChatGPT, Gemini, Perplexity, and Google AI Overviews.",
            "detail": "Where SEO targets the ten blue links, AEO targets the single synthesised answer an AI gives — making sure your brand is the source behind it.",
        },
        {
            "question": "How do I know if AI is citing my competitors instead of me?",
            "answer": "VRT SPACE runs your target queries against AI answer engines and shows which brands get cited, including whether you appear at all.",
            "detail": "You see a side-by-side share-of-voice view — for example, a competitor cited in 7 of 10 buyer queries while you appear in none — so the gap is impossible to ignore.",
        },
        {
            "question": "How is AEO different from SEO?",
            "answer": "SEO optimises for ranked search results; AEO optimises for being the source an AI engine quotes in its answer.",
            "detail": "They reinforce each other — clean structure, schema, and entity coverage help you rank on Google and get cited by ChatGPT, Gemini, and Perplexity.",
        },
        {
            "question": "What does the AI Visibility Score measure?",
            "answer": "The AI Visibility Score measures how often and how prominently your brand is surfaced across the AI answer engines you track.",
            "detail": "Rerun it after each fix to watch the score move, so you can prove that your AEO work is translating into real citation share.",
        },
    ],
}

# Services index page — broad, top-of-funnel questions.
SERVICES_INDEX_FAQS = [
    {
        "question": "How do the audit, SEO, and AEO services work together?",
        "answer": "The audit finds the issues, SEO analysis shows what competitors do better, and AEO improves how AI answer engines cite you — one connected system instead of three disconnected tools.",
        "detail": "Most sites don't have a single visibility problem; they have a mix of technical, search, and AI-readiness gaps that need one clear order of attack.",
    },
    {
        "question": "Which service should I start with?",
        "answer": "Start with the free website audit — it gives you the clearest picture of what's blocking discovery before you commit to anything.",
        "detail": "From there, SEO analysis and AEO build on the audit findings inside the same workspace.",
    },
    {
        "question": "Do you optimize for ChatGPT, Gemini, and Perplexity?",
        "answer": "Yes. AI visibility tracking and AEO recommendations cover ChatGPT, Gemini, Perplexity, and Google AI Overviews.",
        "detail": "You see which engines cite you, which cite competitors, and what to change to win more citations.",
    },
    {
        "question": "Can my whole team use one workspace?",
        "answer": "Yes. A workspace keeps audits, recommendations, history, and next actions in one shared place for your team.",
        "detail": "That makes it easy to track progress over time and show measurable improvement after each round of fixes.",
    },
]

# For-agencies landing page — agency-specific buying questions.
AGENCY_FAQS = [
    {
        "question": "Can I manage multiple client sites in one account?",
        "answer": "Yes. VRT SPACE is built for agencies to manage multiple client projects from a single dashboard with a per-client health view.",
        "detail": "Each client gets their own workspace, score history, and at-risk-category view, so you can see everyone's status at a glance.",
    },
    {
        "question": "How does this help me prove ROI to clients?",
        "answer": "Every audit run is saved, so you can show a client's score moving from, say, 54 to 71 over 60 days.",
        "detail": "The AI visibility comparison — showing a competitor cited where the client isn't — is the screenshot agencies use to justify the retainer.",
    },
    {
        "question": "Can I white-label or share reports with clients?",
        "answer": "Yes. You can generate shareable audit report links and exports to send straight to clients.",
        "detail": "Shared links let a client discover the platform through your work, while you keep the full workspace.",
    },
    {
        "question": "Do you offer an affiliate or referral program for agencies?",
        "answer": "Yes. Agencies and influencers can earn commission on referrals through the built-in affiliate program.",
        "detail": "Referrals are tracked on signup and commission is calculated automatically, with monthly payout statements.",
    },
    {
        "question": "How is pricing structured for agencies?",
        "answer": "Plans scale by tracked client sites and monthly audits — Starter ($59), Growth ($149), and Authority ($349).",
        "detail": "Most agencies bill the tool back to clients, so the plan pays for itself across a handful of retainers.",
    },
]

# Packages / pricing page — mirrors the visible accordion so the FAQPage schema
# stays identical to what readers see.
PACKAGES_FAQS = [
    {
        "question": "Should I start with a plan or with the free audit?",
        "answer": "Start with the free audit first.",
        "detail": "It gives you a clearer picture of what is broken, what matters most, and whether you need a paid plan right away.",
    },
    {
        "question": "What changes as I move up the plan ladder?",
        "answer": "You unlock more capacity, more follow-through, and more room to keep improving.",
        "detail": "The higher tiers are designed for teams that need more audits, more active workspace usage, or more advanced delivery support.",
    },
    {
        "question": "When should I request custom scope?",
        "answer": "Only when the normal audit, SEO, AEO, and workspace flow is not enough.",
        "detail": "If your need is a large rebuild, bespoke implementation, or multi-domain complexity, custom scope becomes the better path.",
    },
    {
        "question": "Can I create a workspace before I upgrade?",
        "answer": "Yes. You can start the relationship before committing to a larger plan.",
        "detail": "That keeps the first step light and lets the product prove value before you decide how far to scale.",
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
            "faqs": SERVICE_FAQS.get(slug, []),
        }


SERVICE_PAGE_LIST = list(SERVICE_PAGE_LOOKUP.values())
