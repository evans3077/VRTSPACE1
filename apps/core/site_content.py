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
        "question": "What is AI visibility and why does it matter?",
        "answer": "AI visibility is how often AI answer engines — ChatGPT, Gemini, Perplexity, and Google AI Overviews — surface and cite your brand when people ask questions in your market.",
        "detail": "Buyers increasingly get answers from AI instead of scrolling search results, so if AI doesn't cite you, you're invisible at the exact moment a decision is being made. VRT SPACE measures that visibility and shows you how to improve it.",
    },
    {
        "question": "How do you track whether ChatGPT, Gemini, or Perplexity cite my brand?",
        "answer": "We run your target queries against the major AI answer engines and report which brands get cited, including whether you appear and where competitors beat you.",
        "detail": "You get a share-of-voice view across engines, so you can see — query by query — when an AI recommends a competitor but never mentions you.",
    },
    {
        "question": "How is VRT SPACE different from Ahrefs or SEMrush?",
        "answer": "Traditional SEO tools measure how you rank on Google; VRT SPACE adds AI visibility (AEO) tracking and change-over-time scoring in one workspace.",
        "detail": "You still get the technical audit and SEO analysis you'd expect, plus the answer-engine layer those tools don't cover and a score history that proves whether your fixes are working.",
    },
    {
        "question": "Is the website audit free, and what does it include?",
        "answer": "Yes — you can run a full diagnostic audit for free, covering technical SEO, performance, on-page health, and AI-readiness, with no credit card required.",
        "detail": "Free runs give you your overall score and category gauges. Paid plans unlock more audits per month, deeper recommendations, PDF export, AI citation tracking over time, and saved workspace history.",
    },
    {
        "question": "How do I actually improve my AI visibility after the audit?",
        "answer": "Start with the highest-impact fixes the audit surfaces, then rerun to confirm your AI Visibility Score is moving in the right direction.",
        "detail": "Clear technical health, schema, entity coverage, and answer-first content make your pages easier for AI engines to read, quote, and recommend — and the workspace keeps every recommendation and rerun in one place so progress stays measurable.",
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
        "answer": "Yes. VRT SPACE is built for agencies to run every client from one dashboard, each with its own workspace and health score.",
        "detail": "The agency view shows all clients side by side — overall score, the most at-risk category, and how each score moved since the last audit — so your morning status check takes seconds, not a spreadsheet.",
    },
    {
        "question": "How does this help me prove ROI and keep retainers?",
        "answer": "Every audit run is saved, so you can show a client's score climbing from, say, 54 to 71 over 60 days — concrete proof the work is paying off.",
        "detail": "The AI visibility comparison — a competitor cited in answers where your client isn't — is the screenshot agencies use to win the deal and justify the monthly fee.",
    },
    {
        "question": "Can I share or white-label reports for clients?",
        "answer": "Yes. You can generate shareable audit report links and exports to send clients directly, no login required on their end.",
        "detail": "Shared links double as a soft acquisition channel — the client sees your work and discovers the platform — while you keep the full workspace and history.",
    },
    {
        "question": "How fast can I onboard a new client?",
        "answer": "Add a client site and run the first audit in under two minutes — no crawl setup, integrations, or onboarding calls required.",
        "detail": "You get a baseline score and prioritized fixes immediately, then schedule weekly or monthly re-audits so regressions surface before the client notices.",
    },
    {
        "question": "Do you offer an affiliate or referral program?",
        "answer": "Yes. Agencies and creators earn commission through the built-in invite-only partner program — currently up to 25% on first payment and 15% recurring.",
        "detail": "Referrals are attributed on signup and commission is calculated automatically, with payouts handled weekly through Stripe.",
    },
    {
        "question": "How is pricing structured for agencies?",
        "answer": "Plans scale by tracked client sites and monthly audits — Starter ($59), Growth ($149), and Authority ($349) per month.",
        "detail": "Growth fits most agencies at 10 client sites and 24 audits a month. Because the cost is billable back to clients, the plan usually pays for itself across a couple of retainers.",
    },
]

# Packages / pricing page — single source for both the visible accordion and
# the FAQPage schema, so they can never drift apart.
PACKAGES_FAQS = [
    {
        "question": "Is there a free plan, and what's included?",
        "answer": "Yes. The free plan includes a tracked website, starter audits, your overall score, and category gauges — no credit card required.",
        "detail": "It's enough to see where you stand and run your first diagnosis. Paid plans add more audits, more tracked sites, AI citation tracking over time, deeper recommendations, and PDF export.",
    },
    {
        "question": "How much does VRT SPACE cost?",
        "answer": "Paid plans are Starter at $59/mo, Growth at $149/mo, and Authority at $349/mo, billed monthly.",
        "detail": "Each tier scales the number of monthly audits, tracked websites, and AEO/content capacity. Most agencies bill the cost back to clients, so a single retainer usually covers the plan.",
    },
    {
        "question": "How do credits work?",
        "answer": "Credits are the currency for actions — roughly one credit per audit or AI scan, and a couple per content draft — and they refresh each billing cycle.",
        "detail": "When you run low you get alerts at 50%, 75%, and 90%, and you can buy a one-time top-up starting at $10 instead of being forced into a higher plan.",
    },
    {
        "question": "Can I upgrade, downgrade, or cancel anytime?",
        "answer": "Yes. You can change plans or cancel at any time from your account — there's no lock-in contract.",
        "detail": "Upgrades take effect immediately so you get the extra capacity right away, and your workspace history is preserved across plan changes.",
    },
    {
        "question": "What's the difference between the plans for AI visibility?",
        "answer": "Higher tiers track more target queries across more AI engines and more client sites, so you see a fuller picture of where you're cited.",
        "detail": "Starter is right for a single brand getting started; Growth suits agencies tracking several clients; Authority adds the deepest query coverage and the most monthly capacity.",
    },
]


# ── Orientation layer ───────────────────────────────────────────────────────
# Plain-language help content that makes a feature-rich product feel simple.
# Powers /how-it-works/ and /glossary/. Golden rule: what it is → why it
# matters → what to do next.

# The core loop, shown as 4 steps on the "How VRT Works" page.
HOW_IT_WORKS_STEPS = [
    {
        "icon": "fa-magnifying-glass-chart",
        "title": "Audit your site",
        "body": "Run a free scan of your website's technical health, content, and AI-readiness.",
        "module": "Website Audit",
    },
    {
        "icon": "fa-robot",
        "title": "See where AI ignores you",
        "body": "Find out which buyer questions AI engines answer with competitors instead of you.",
        "module": "AI Visibility",
    },
    {
        "icon": "fa-screwdriver-wrench",
        "title": "Fix the gaps",
        "body": "Work through prioritized, plain-language recommendations — highest impact first.",
        "module": "SEO Audit & Content",
    },
    {
        "icon": "fa-arrows-rotate",
        "title": "Rerun & track",
        "body": "Re-audit after each change and watch your scores move, so you know it's working.",
        "module": "Overview",
    },
]

# "What the words mean" concept cards on the How VRT Works page.
HOW_IT_WORKS_CONCEPTS = [
    {
        "term": "AI Visibility",
        "blurb": "How often AI answer engines mention and cite your brand when buyers ask questions.",
        "anchor": "ai-visibility",
    },
    {
        "term": "Answer Engine Optimization (AEO)",
        "blurb": "The work of making your site easy for AI engines to read, trust, quote, and recommend.",
        "anchor": "aeo",
    },
    {
        "term": "Share of Voice",
        "blurb": "Your slice of all the AI answers in your space, compared with competitors.",
        "anchor": "share-of-voice",
    },
    {
        "term": "Prompts",
        "blurb": "The real questions and topics you track to see who AI recommends.",
        "anchor": "prompt",
    },
]

# "Where to start" persona cards.
HOW_IT_WORKS_PERSONAS = [
    {
        "icon": "fa-people-arrows",
        "title": "Agencies",
        "body": "Run an audit on a client site and use the AI visibility gap as your pitch.",
        "cta_label": "See the agency view",
        "cta_url_name": "core:for-agencies",
    },
    {
        "icon": "fa-user-gear",
        "title": "In-house SEO",
        "body": "Baseline your own site, then fix the highest-impact issues and rerun.",
        "cta_label": "Run a free audit",
        "cta_url_name": "tools:free-seo-audit",
    },
    {
        "icon": "fa-cube",
        "title": "SaaS teams",
        "body": "Track the buyer questions in your category and win the AI recommendation.",
        "cta_label": "Check your AI visibility",
        "cta_url_name": "aeo:aeo-index",
    },
]

# Glossary — one plain-language source for every term, feeding both the visible
# page and the DefinedTermSet structured data (great for AEO).
GLOSSARY_CATEGORIES = [
    "AI Visibility & AEO",
    "SEO & Technical",
    "Content",
    "Performance",
    "Workspace & Account",
]

GLOSSARY_TERMS = [
    {
        "term": "AI Visibility",
        "acronym": "",
        "category": "AI Visibility & AEO",
        "definition": "How often AI answer engines — ChatGPT, Gemini, Perplexity, Google AI Overviews — mention and cite your brand when people ask questions in your market.",
        "module_label": "AI Visibility",
        "module_url_name": "aeo:workspace-aeo",
        "related": ["AEO", "AI Visibility Score", "Citation"],
    },
    {
        "term": "Answer Engine Optimization",
        "acronym": "AEO",
        "category": "AI Visibility & AEO",
        "definition": "Making your website easy for AI answer engines to read, trust, quote, and recommend — the AI-era counterpart to SEO.",
        "module_label": "AI Visibility",
        "module_url_name": "aeo:workspace-aeo",
        "related": ["AI Visibility", "Schema", "Citation"],
    },
    {
        "term": "AI Visibility Score",
        "acronym": "AVS",
        "category": "AI Visibility & AEO",
        "definition": "A single 0–100 number summarising how present and prominent your brand is across the AI engines you track. Higher is better.",
        "module_label": "AI Visibility",
        "module_url_name": "aeo:workspace-aeo",
        "related": ["AI Visibility", "Share of Voice"],
    },
    {
        "term": "Citation",
        "acronym": "",
        "category": "AI Visibility & AEO",
        "definition": "A specific mention of your brand or page inside an AI-generated answer. Citations are the AI-search equivalent of ranking on page one.",
        "module_label": "AI Visibility",
        "module_url_name": "aeo:workspace-aeo",
        "related": ["AI Visibility", "Share of Voice"],
    },
    {
        "term": "Share of Voice",
        "acronym": "SOV",
        "category": "AI Visibility & AEO",
        "definition": "Your slice of all the AI answers for your tracked questions, measured against competitors — who AI mentions most in your space.",
        "module_label": "Share of Voice",
        "module_url_name": "aeo:workspace-share-of-voice",
        "related": ["Citation", "Prompt"],
    },
    {
        "term": "Prompt",
        "acronym": "",
        "category": "AI Visibility & AEO",
        "definition": "A question or topic you track — the actual things your customers ask AI tools — so you can see whether you're the recommended answer.",
        "module_label": "Prompts",
        "module_url_name": "aeo:workspace-prompts",
        "related": ["Topic cluster", "Share of Voice"],
    },
    {
        "term": "Recommendation strength",
        "acronym": "",
        "category": "AI Visibility & AEO",
        "definition": "How impactful a suggested fix is. Stronger recommendations move your scores the most, so they're worth doing first.",
        "module_label": "SEO Audit",
        "module_url_name": "seo:workspace-seo",
        "related": ["Technical health"],
    },
    {
        "term": "Technical health",
        "acronym": "",
        "category": "SEO & Technical",
        "definition": "How sound your site is under the hood — speed, crawlability, mobile, structure. Weak technical health holds back both search and AI visibility.",
        "module_label": "SEO Audit",
        "module_url_name": "seo:workspace-seo",
        "related": ["Crawlability", "Core Web Vitals"],
    },
    {
        "term": "Crawlability",
        "acronym": "",
        "category": "SEO & Technical",
        "definition": "How easily search engines and AI bots can read your pages. If they can't crawl a page, they can't rank or cite it.",
        "module_label": "SEO Audit",
        "module_url_name": "seo:workspace-seo",
        "related": ["Indexation", "Technical health"],
    },
    {
        "term": "Indexation",
        "acronym": "",
        "category": "SEO & Technical",
        "definition": "Whether a page is actually stored in a search engine's index. A page that isn't indexed can never appear in results or answers.",
        "module_label": "SEO Audit",
        "module_url_name": "seo:workspace-seo",
        "related": ["Crawlability"],
    },
    {
        "term": "Schema",
        "acronym": "",
        "category": "SEO & Technical",
        "definition": "Structured data added to your pages that spells out what they mean — products, FAQs, articles — so engines and AI can understand and quote them.",
        "module_label": "SEO Audit",
        "module_url_name": "seo:workspace-seo",
        "related": ["AEO", "Crawlability"],
    },
    {
        "term": "Internal linking",
        "acronym": "",
        "category": "SEO & Technical",
        "definition": "The links between your own pages. Good internal links help engines discover content and understand which pages matter most.",
        "module_label": "SEO Audit",
        "module_url_name": "seo:workspace-seo",
        "related": ["Crawlability", "Topic cluster"],
    },
    {
        "term": "Topic cluster",
        "acronym": "",
        "category": "Content",
        "definition": "A group of related pages covering one subject in depth. Clusters signal expertise, which both search and AI engines reward.",
        "module_label": "Content",
        "module_url_name": "content:workspace-content",
        "related": ["Prompt", "Internal linking"],
    },
    {
        "term": "Core Web Vitals",
        "acronym": "LCP / CLS / INP",
        "category": "Performance",
        "definition": "Google's three speed-and-stability metrics: how fast the main content loads (LCP), how much the layout jumps (CLS), and how quickly the page responds (INP).",
        "module_label": "SEO Audit",
        "module_url_name": "seo:workspace-seo",
        "related": ["Technical health"],
    },
    {
        "term": "Workspace",
        "acronym": "",
        "category": "Workspace & Account",
        "definition": "Your home for a brand or client — where audits, recommendations, history, and AI visibility all live together so progress stays in one place.",
        "module_label": "Overview",
        "module_url_name": "tools:workspace-dashboard",
        "related": ["Project", "Credits"],
    },
    {
        "term": "Project",
        "acronym": "",
        "category": "Workspace & Account",
        "definition": "A single tracked website inside a workspace. Each client site is its own project with its own score and history.",
        "module_label": "Overview",
        "module_url_name": "tools:workspace-dashboard",
        "related": ["Workspace"],
    },
    {
        "term": "Credits",
        "acronym": "",
        "category": "Workspace & Account",
        "definition": "The currency for actions — roughly one credit per audit or AI scan. They refresh each billing cycle, and you can top up without changing plans.",
        "module_label": "Billing & Credits",
        "module_url_name": "tools:account-dashboard",
        "related": ["Rerun"],
    },
    {
        "term": "Rerun",
        "acronym": "",
        "category": "Workspace & Account",
        "definition": "Running an audit again after you've made changes, so you can see your scores move and confirm the fixes are working.",
        "module_label": "Overview",
        "module_url_name": "tools:workspace-dashboard",
        "related": ["Credits", "AI Visibility Score"],
    },
]


def glossary_anchor(term):
    """Stable anchor id for a glossary term, e.g. 'ai-visibility' (used by
    in-product info-tips to deep-link, e.g. /glossary#aeo)."""
    return slugify(term)


# Stable anchor ids so in-product info-tips and the How-It-Works concept cards
# can deep-link reliably (e.g. /glossary#aeo). Overrides where the short common
# name differs from the full term, so related-term links (which slugify the
# short name) always resolve.
_GLOSSARY_ANCHOR_OVERRIDES = {"Answer Engine Optimization": "aeo"}
for _t in GLOSSARY_TERMS:
    _t["anchor"] = _GLOSSARY_ANCHOR_OVERRIDES.get(_t["term"], slugify(_t["term"]))


def build_glossary_schema(terms):
    """schema.org DefinedTermSet — strong AEO signal: hands answer engines a
    clean, machine-readable dictionary of every concept the product uses."""
    return {
        "@context": "https://schema.org",
        "@type": "DefinedTermSet",
        "name": "VRT SPACE Glossary",
        "description": "Plain-language definitions of AI visibility, AEO, SEO, and workspace terms.",
        "hasDefinedTerm": [
            {
                "@type": "DefinedTerm",
                "name": (f"{t['term']} ({t['acronym']})" if t.get("acronym") else t["term"]),
                "description": t["definition"],
                "inDefinedTermSet": "/glossary/",
            }
            for t in terms
        ],
    }


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


# ── Help Center ────────────────────────────────────────────────────────────

HELP_POPULAR = [
    {
        "title": "How VRT Works",
        "icon": "fa-solid fa-lightbulb",
        "url": "/how-it-works/",
        "desc": "The 60-second mental model for the whole platform.",
    },
    {
        "title": "Run your first audit",
        "icon": "fa-solid fa-play",
        "url": "/workspace/",
        "desc": "Set up your project and get your first health score.",
    },
    {
        "title": "AI Visibility Score explained",
        "icon": "fa-solid fa-robot",
        "url": "/glossary/#avs",
        "desc": "What the number means and how it's calculated.",
    },
    {
        "title": "Share of Voice",
        "icon": "fa-solid fa-chart-pie",
        "url": "/glossary/#share-of-voice",
        "desc": "Your slice of AI citations compared to competitors.",
    },
]

HELP_CATEGORIES = [
    {
        "icon": "fa-solid fa-rocket",
        "name": "Getting started",
        "slug": "getting-started",
        "articles": [
            {"title": "How VRT works in 60 seconds", "url": "/how-it-works/"},
            {"title": "Create your first project and run an audit", "url": "/workspace/"},
            {"title": "Understand your overall health score", "url": "/glossary/#technical-health"},
        ],
    },
    {
        "icon": "fa-solid fa-robot",
        "name": "AI Visibility & AEO",
        "slug": "ai-visibility",
        "articles": [
            {"title": "What is AI Visibility and why it matters", "url": "/glossary/#ai-visibility"},
            {"title": "AI Visibility Score (AVS) — how it's calculated", "url": "/glossary/#avs"},
            {"title": "Track prompts and monitor citations", "url": "/workspace/prompts/"},
        ],
    },
    {
        "icon": "fa-solid fa-chart-pie",
        "name": "Share of Voice",
        "slug": "share-of-voice",
        "articles": [
            {"title": "What Share of Voice means", "url": "/glossary/#share-of-voice"},
            {"title": "Add competitors to benchmark against", "url": "/workspace/prompts/"},
            {"title": "Read the Share of Voice dashboard", "url": "/workspace/share-of-voice/"},
        ],
    },
    {
        "icon": "fa-solid fa-magnifying-glass",
        "name": "SEO & Technical",
        "slug": "seo-technical",
        "articles": [
            {"title": "Your audit score and what each category means", "url": "/glossary/#technical-health"},
            {"title": "Core Web Vitals — LCP, CLS, INP", "url": "/glossary/#core-web-vitals"},
            {"title": "Crawlability and indexation basics", "url": "/glossary/#crawlability"},
        ],
    },
    {
        "icon": "fa-solid fa-file-pen",
        "name": "Content & Publishing",
        "slug": "content",
        "articles": [
            {"title": "Generate content from an SEO brief", "url": "/workspace/content/"},
            {"title": "What is a topic cluster?", "url": "/glossary/#topic-cluster"},
            {"title": "Connect your CMS for direct publishing", "url": "/workspace/content/credentials/"},
        ],
    },
    {
        "icon": "fa-solid fa-credit-card",
        "name": "Billing & Credits",
        "slug": "billing",
        "articles": [
            {"title": "How credits work and what they cost", "url": "/glossary/#credits"},
            {"title": "Compare plans and upgrade", "url": "/packages/"},
            {"title": "Manage your subscription and invoices", "url": "/workspace/account/#billing"},
        ],
    },
]
