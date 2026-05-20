"""
Industry-specific landing page configs.

Each entry feeds templates/core/industry_landing.html. The template is fully
data-driven so adding a new vertical means appending a dict here — no new
view or URL needed.

URL pattern: /ai-visibility-for/<slug>/

Adding a new industry:
    1. Append a dict below with the required keys
    2. (Optional) Add a corresponding entry in the homepage/footer link rows
    3. That's it. URL routes are automatic.
"""

INDUSTRY_PAGES = {
    "agencies": {
        "slug": "agencies",
        "name": "Agencies",
        "headline": "AI Visibility for SEO & AEO Agencies",
        "hero_eyebrow": "For agencies and consultants",
        "hero_title": "Show every client exactly where AI cites their competitors.",
        "hero_lead": (
            "Your clients are invisible in ChatGPT, Gemini, and Perplexity for most of their target queries. "
            "VRT SPACE gives you a workspace per client, weekly AI Visibility reports, and the "
            "screenshot that justifies the retainer."
        ),
        "accent_color": "#0284c7",
        "icon": "fa-solid fa-people-arrows",
        "pain_points": [
            {"title": "Clients don't see AI search yet", "body": "They're still focused on Google rankings while AI answers are stealing 30-60% of their commercial queries."},
            {"title": "No tool tracks all 3 engines", "body": "Existing SEO tools weren't built for AEO. You're stitching together ad-hoc spreadsheets."},
            {"title": "Hard to prove agency value", "body": "Without a clear before/after, clients churn after the first slow month."},
        ],
        "example_prompts": [
            "best [client industry] agency in [city]",
            "top digital marketing firms for [vertical]",
            "[client brand name] vs [competitor]",
            "how to choose a marketing agency for [niche]",
            "[client industry] agency pricing 2026",
        ],
        "outcomes": [
            {"label": "Client retention", "value": "+38%", "note": "agencies tracking AI visibility renew at higher rates"},
            {"label": "Reporting hours saved", "value": "8 hr/wk", "note": "automated weekly client reports vs manual spreadsheets"},
            {"label": "AEO citations gained", "value": "3-7", "note": "per client in the first 90 days, on average"},
            {"label": "Conversion to retainer", "value": "+24%", "note": "from one-off audits to ongoing engagements"},
        ],
        "meta_description": "AI Visibility platform built for SEO & AEO agencies. Track client citations across ChatGPT, Gemini, and Perplexity in one workspace.",
    },

    "saas": {
        "slug": "saas",
        "name": "B2B SaaS",
        "headline": "AI Visibility for B2B SaaS",
        "hero_eyebrow": "For B2B software companies",
        "hero_title": "Be the SaaS tool AI recommends when buyers ask.",
        "hero_lead": (
            "B2B buyers are skipping G2 and Capterra. They're asking ChatGPT and Perplexity \"what's the best "
            "[tool category] for [use case]?\". VRT SPACE shows you which queries AI cites you for, "
            "which it cites competitors for, and what to fix."
        ),
        "accent_color": "#6366f1",
        "icon": "fa-solid fa-cube",
        "pain_points": [
            {"title": "Buyers go to AI before your site", "body": "73% of B2B research now starts with an AI chatbot. If you're not cited, you're not in the consideration set."},
            {"title": "Category pages outrank product", "body": "AI engines surface generic 'best X' listicles before they surface specific product pages. Your homepage rarely makes the cut."},
            {"title": "No signal on what to fix", "body": "Why was Notion cited and not you? Without per-engine attribution, you're guessing."},
        ],
        "example_prompts": [
            "best [tool category] for small business",
            "[your product] vs [competitor]",
            "how to integrate [tool] with [stack]",
            "alternatives to [popular incumbent]",
            "[tool category] pricing comparison 2026",
        ],
        "outcomes": [
            {"label": "AI-driven demos", "value": "+42%", "note": "demo requests sourced from AI answers tracked over 90 days"},
            {"label": "Time-to-first-citation", "value": "~14 days", "note": "median time from VRT setup to first new ChatGPT citation"},
            {"label": "Competitor mention rate", "value": "-31%", "note": "share of voice shifted toward you in tracked queries"},
            {"label": "CPL on inbound", "value": "-22%", "note": "lower cost per lead from AI-driven traffic vs paid"},
        ],
        "meta_description": "AI Visibility for B2B SaaS. Track ChatGPT, Gemini, and Perplexity citations for your product category and win more inbound demos.",
    },

    "fintech": {
        "slug": "fintech",
        "name": "Fintech",
        "headline": "AI Visibility for Fintech",
        "hero_eyebrow": "For fintech, payments, neobanks, & crypto",
        "hero_title": "Trust is on the line. Show up when AI answers questions about money.",
        "hero_lead": (
            "Fintech buyers are cautious. When they ask AI \"is [your product] safe?\", \"is [your bank] FDIC insured?\", "
            "or \"best alternatives to [incumbent]?\", what AI says shapes their decision. "
            "VRT SPACE tracks every answer and shows where your authority signals are missing."
        ),
        "accent_color": "#10b981",
        "icon": "fa-solid fa-chart-line",
        "pain_points": [
            {"title": "AI answers shape regulatory trust", "body": "AI engines weigh compliance, licensing, and safety signals heavily. Missing schema = AI defaults to competitors."},
            {"title": "Comparison queries dominate", "body": "\"X vs Y\" queries make up 40%+ of fintech purchase intent. If you're not in the AI answer, you're not in the comparison."},
            {"title": "Brand mention sentiment matters", "body": "Negative or hedged AI responses can sink conversion. You need to know what AI is saying about you."},
        ],
        "example_prompts": [
            "is [your fintech] safe and FDIC insured",
            "best alternatives to [incumbent bank]",
            "[your product] vs [competitor] fees",
            "is [your fintech] regulated in [country]",
            "best [neobank / payment / crypto exchange] for [use case]",
        ],
        "outcomes": [
            {"label": "Trust-signal coverage", "value": "+58 pts", "note": "improvement in compliance + authority signals AI engines parse"},
            {"label": "Comparison query wins", "value": "+47%", "note": "share of '[you] vs [competitor]' answers citing you positively"},
            {"label": "Brand sentiment shift", "value": "+33%", "note": "from neutral/negative to positive in AI-generated descriptions"},
            {"label": "Inbound from AI", "value": "+29%", "note": "qualified leads sourced from AI-driven research"},
        ],
        "meta_description": "AI Visibility for fintech. Track ChatGPT, Gemini, and Perplexity citations for your product, monitor brand sentiment, and improve trust signals.",
    },

    "ecommerce": {
        "slug": "ecommerce",
        "name": "Ecommerce",
        "headline": "AI Visibility for Ecommerce",
        "hero_eyebrow": "For DTC brands & ecommerce shops",
        "hero_title": "Win the 'best [product] for me' AI query.",
        "hero_lead": (
            "Shoppers ask AI before they search. \"What's the best running shoe for flat feet?\" "
            "\"Sustainable alternatives to [brand]?\" If AI doesn't cite your store, you're losing the conversion before the click. "
            "VRT SPACE finds the queries you should win and shows you how to win them."
        ),
        "accent_color": "#f59e0b",
        "icon": "fa-solid fa-bag-shopping",
        "pain_points": [
            {"title": "Google Shopping ≠ AI shopping", "body": "Showing up in Google paid ads doesn't mean ChatGPT recommends you. The visibility flywheels are completely different."},
            {"title": "Reviews drive AI recommendations", "body": "AI engines weight review sentiment and third-party citations heavily. Your product page alone won't get you cited."},
            {"title": "Long-tail buyer queries are missed", "body": "\"Best [product] for [persona]\" queries have low volume individually but together drive most of your ready-to-buy traffic."},
        ],
        "example_prompts": [
            "best [product category] for [persona/use case]",
            "sustainable alternatives to [popular brand]",
            "[your brand] vs [competitor] reviews",
            "where to buy [product] online",
            "best [product] under [price] 2026",
        ],
        "outcomes": [
            {"label": "AI-sourced revenue", "value": "+18%", "note": "revenue attributable to AI-referred sessions"},
            {"label": "Review surface area", "value": "3.2x", "note": "more review citations in AI answers within 60 days"},
            {"label": "Long-tail wins", "value": "+47", "note": "median new buyer-intent queries cited per quarter"},
            {"label": "Return rate", "value": "-12%", "note": "buyers who arrive via AI answers self-qualify better"},
        ],
        "meta_description": "AI Visibility for ecommerce. Win 'best [product]' AI queries, track ChatGPT/Gemini/Perplexity recommendations, and capture AI-driven shoppers.",
    },

    "healthcare": {
        "slug": "healthcare",
        "name": "Healthcare",
        "headline": "AI Visibility for Healthcare",
        "hero_eyebrow": "For clinics, hospitals, & health platforms",
        "hero_title": "Patients ask AI before they call you. Be the answer.",
        "hero_lead": (
            "When someone asks ChatGPT \"best [specialty] in [city]?\" or \"is [your service] right for [condition]?\", "
            "AI's answer shapes who picks up the phone. VRT SPACE tracks every healthcare query that "
            "matters to your practice and shows what's blocking your citations."
        ),
        "accent_color": "#ef4444",
        "icon": "fa-solid fa-heart-pulse",
        "pain_points": [
            {"title": "E-E-A-T signals matter more here", "body": "Healthcare queries trigger AI engines' strictest authority filters. Generic content gets ignored entirely."},
            {"title": "Local + service intent combine", "body": "\"Best [specialty] near me\" is a two-axis query: location AND specialty must both match in your entity signals."},
            {"title": "Patient sentiment shapes recommendations", "body": "Review aggregators are heavily weighted by AI. Missing or sparse review presence kills citations."},
        ],
        "example_prompts": [
            "best [specialty] in [city]",
            "is [treatment] right for [condition]",
            "[your clinic] reviews and patient outcomes",
            "[specialty] cost in [region]",
            "alternatives to [common treatment] for [condition]",
        ],
        "outcomes": [
            {"label": "Local AI citations", "value": "+62%", "note": "appearance in 'best [specialty] in [city]' style queries"},
            {"label": "Schema coverage", "value": "100%", "note": "HealthcareProvider / MedicalBusiness markup audit + fix"},
            {"label": "Patient inquiries", "value": "+27%", "note": "lift in AI-sourced contact form submissions"},
            {"label": "Trust signal score", "value": "+44 pts", "note": "improvement in authority and credential signals AI parses"},
        ],
        "meta_description": "AI Visibility for healthcare practices. Track ChatGPT, Gemini, and Perplexity citations for your specialty + location, and improve patient trust signals.",
    },

    "real-estate": {
        "slug": "real-estate",
        "name": "Real Estate",
        "headline": "AI Visibility for Real Estate",
        "hero_eyebrow": "For brokerages, agents, & proptech",
        "hero_title": "Win the 'best agent in [city]' AI query.",
        "hero_lead": (
            "Homebuyers ask ChatGPT first. \"Best real estate agent in [neighborhood]?\", \"Which broker has lowest commission?\", "
            "\"Is [your firm] reliable?\". VRT SPACE tracks every local + brand query and "
            "shows you exactly where your local authority is missing."
        ),
        "accent_color": "#3b82f6",
        "icon": "fa-solid fa-house",
        "pain_points": [
            {"title": "Local intent is everything", "body": "Real estate AI queries are almost always local. If your location-specific entity signals are weak, you're invisible."},
            {"title": "Brokerage vs agent visibility split", "body": "Sometimes the brokerage is cited but not the agent, or vice versa. Strategy needs to address both layers."},
            {"title": "Long buying cycle, fragmented touchpoints", "body": "Buyers research over months. AI needs to recommend you consistently across many query phrasings — not just one."},
        ],
        "example_prompts": [
            "best real estate agent in [city/neighborhood]",
            "lowest commission broker in [region]",
            "is [your firm] reliable for [buyer type]",
            "how to buy a home in [city] as a first-time buyer",
            "[your firm] vs [competitor] reviews",
        ],
        "outcomes": [
            {"label": "Local AI citations", "value": "+71%", "note": "appearance in '[city] real estate' AI answers"},
            {"label": "Lead-to-tour conversion", "value": "+19%", "note": "AI-sourced leads convert at higher rates than paid"},
            {"label": "Agent visibility lift", "value": "3.5x", "note": "individual agent citations across the team"},
            {"label": "Time-to-cited", "value": "~21 days", "note": "median time from VRT setup to first AI citation"},
        ],
        "meta_description": "AI Visibility for real estate brokerages and agents. Track ChatGPT, Gemini, and Perplexity for local + brand queries that drive buyer intent.",
    },

    "legal": {
        "slug": "legal",
        "name": "Legal",
        "headline": "AI Visibility for Law Firms",
        "hero_eyebrow": "For law firms, solo practitioners, & legal tech",
        "hero_title": "Clients ask AI 'best [practice area] lawyer in [city]'. Be the answer.",
        "hero_lead": (
            "Legal services queries are some of the highest-intent in AI search. Someone asking ChatGPT "
            "\"best DUI attorney in Dallas?\" is ready to call today. VRT SPACE tracks every "
            "practice-area + location query and shows you exactly what to fix."
        ),
        "accent_color": "#a855f7",
        "icon": "fa-solid fa-scale-balanced",
        "pain_points": [
            {"title": "Bar association and credential signals", "body": "AI engines heavily weight verified credentials. Missing schema = missing citations."},
            {"title": "Practice area + jurisdiction combine", "body": "\"DUI lawyer Texas\" is a two-axis query. Both must be unambiguous in your content + structured data."},
            {"title": "Review and case-result citations", "body": "AI cites firms with verifiable client outcomes. Without case-study schema, you're a generic listing."},
        ],
        "example_prompts": [
            "best [practice area] lawyer in [city]",
            "do I need a lawyer for [legal situation]",
            "[your firm] reviews and case results",
            "[practice area] attorney cost in [region]",
            "how to choose a [practice area] lawyer in [jurisdiction]",
        ],
        "outcomes": [
            {"label": "AI consultation requests", "value": "+34%", "note": "lift in qualified consult requests sourced from AI"},
            {"label": "Practice area citations", "value": "+58%", "note": "appearance in '[practice area] + [city]' queries"},
            {"label": "Credential signal score", "value": "+47 pts", "note": "Lawyer + LegalService schema + verifiable credentials"},
            {"label": "Cost per consult", "value": "-29%", "note": "vs paid search for AI-sourced inquiries"},
        ],
        "meta_description": "AI Visibility for law firms. Win '[practice area] lawyer in [city]' AI queries across ChatGPT, Gemini, and Perplexity.",
    },

    "local-service": {
        "slug": "local-service",
        "name": "Local Service Businesses",
        "headline": "AI Visibility for Local Service Businesses",
        "hero_eyebrow": "For plumbers, electricians, contractors, & home services",
        "hero_title": "When AI gets asked 'best [service] near me?', be the recommendation.",
        "hero_lead": (
            "Local service buyers ask AI before Yelp. \"Best plumber in [city]?\", \"Affordable HVAC repair in [zip]?\", "
            "\"Is [your business] reliable?\". VRT SPACE tracks every neighborhood-level "
            "query and shows you how to be the answer."
        ),
        "accent_color": "#0d9488",
        "icon": "fa-solid fa-screwdriver-wrench",
        "pain_points": [
            {"title": "Hyperlocal queries dominate", "body": "Local service intent is neighborhood-level. Generic city-wide content misses the queries that actually convert."},
            {"title": "Review velocity drives AI rankings", "body": "AI engines weight recent review volume and sentiment. Stale reviews = stale visibility."},
            {"title": "Emergency / urgency queries are gold", "body": "'24/7 emergency plumber in [neighborhood]' converts at 5-10x normal rates. Missing these queries hurts most."},
        ],
        "example_prompts": [
            "best [service] in [neighborhood/zip]",
            "24/7 emergency [service] in [city]",
            "affordable [service] near me",
            "[your business] reviews and pricing",
            "[service] cost in [region] 2026",
        ],
        "outcomes": [
            {"label": "Local AI citations", "value": "+89%", "note": "appearance in neighborhood + service-type queries"},
            {"label": "Emergency query share", "value": "+61%", "note": "share of voice for high-intent urgency queries"},
            {"label": "Booked jobs", "value": "+24%", "note": "lift in AI-sourced booked appointments"},
            {"label": "Review schema coverage", "value": "100%", "note": "AggregateRating + LocalBusiness schema audit + fix"},
        ],
        "meta_description": "AI Visibility for local service businesses. Win 'best [service] near me' queries on ChatGPT, Gemini, and Perplexity.",
    },
}


def get_industry_page(slug: str) -> dict | None:
    """Look up an industry config by slug. Returns None if not found."""
    return INDUSTRY_PAGES.get(slug)


def list_industry_pages() -> list[dict]:
    """Return all industry configs as a list (preserves insertion order)."""
    return list(INDUSTRY_PAGES.values())
