"""Seed a handful of starter blog articles + case studies for demo purposes.

Run:
    python manage.py seed_blog
    python manage.py seed_blog --reset
"""

from __future__ import annotations

import os
import sys

if sys.platform == "win32" and os.environ.get("PYTHONIOENCODING") is None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from apps.content.models import Article
from apps.case_studies.models import CaseStudy


ARTICLES = [
    {
        "slug": "what-is-answer-engine-optimization",
        "title": "What is Answer Engine Optimization (AEO)?",
        "excerpt": "AEO is the practice of optimizing content so AI engines like ChatGPT, Gemini, and Perplexity recommend you in their answers. Here's how it differs from SEO — and why it matters now.",
        "content": (
            "Answer Engine Optimization (AEO) is the practice of structuring your site, content, and entity signals "
            "so AI engines confidently surface you in their answers.\n\n"
            "Where SEO is about being clicked, AEO is about being cited. When ChatGPT answers \"what's the best AEO platform "
            "for agencies?\", the brands that get named in the response — without a click ever happening — are winning AEO. "
            "Everyone else is invisible.\n\n"
            "## The three signals AI engines look for\n\n"
            "AI engines weight three signals heavily when deciding who to cite:\n\n"
            "1. **Entity clarity** — does your site unambiguously establish who you are, what you do, and who for?\n"
            "2. **Answer-first structure** — is your content arranged so AI can extract a direct answer in 30 seconds?\n"
            "3. **Authority + freshness** — recent, well-cited, fact-dense content beats sparse marketing copy every time.\n\n"
            "## How AEO differs from SEO\n\n"
            "Traditional SEO optimizes for rankings and SERP clicks. AEO optimizes for citations and recommendations in AI answers. "
            "An SEO win shows up as a click; an AEO win shows up as your brand being named in an AI response.\n\n"
            "Both matter, and they reinforce each other — Google's AI Overviews source from your existing SEO content. But AEO requires "
            "additional work: FAQ schema, entity-rich content, and continuous monitoring of which prompts you win and lose."
        ),
        "is_pillar": True,
        "status": Article.Status.PUBLISHED,
        "days_ago": 3,
    },
    {
        "slug": "5-prompts-every-saas-should-track",
        "title": "5 prompts every B2B SaaS company should be tracking in AI search",
        "excerpt": "If you're not monitoring these five queries across ChatGPT, Gemini, and Perplexity, you're missing the most commercial intent in your category.",
        "content": (
            "If you're a B2B SaaS founder or marketer, your buyers are asking AI before they even hit your site. "
            "Here are the five prompt patterns we'd watch first.\n\n"
            "## 1. \"Best [category] for [persona]\"\n\n"
            "The highest-intent query in B2B search. \"Best CRM for solo consultants\" doesn't have huge volume, but the people asking are "
            "ready to commit. AI engines need to know your tool fits this persona — entity signals, social proof, and case studies all matter.\n\n"
            "## 2. \"[Your product] vs [Competitor]\"\n\n"
            "Comparison queries are pure consideration-stage. If you're not in the AI answer, you're not in the deal. Audit which competitors are "
            "named when AI describes your tool — and which aren't.\n\n"
            "## 3. \"Alternatives to [Incumbent]\"\n\n"
            "Buyers actively shopping switch providers ask this. If your product genuinely beats Notion / Slack / Salesforce on something specific, "
            "this is your moment.\n\n"
            "## 4. \"How to integrate [tool] with [stack]\"\n\n"
            "Late-stage technical queries. Buyers are mapping implementation. Get cited here and you're effectively pre-approved.\n\n"
            "## 5. \"[Category] pricing comparison 2026\"\n\n"
            "Pure cost validation. If AI describes your pricing accurately and favorably, you save your sales team a discovery call.\n\n"
            "## How to actually track these\n\n"
            "VRT SPACE runs these prompts on a schedule across ChatGPT, Gemini, and Perplexity, captures who got cited, and surfaces share-of-voice "
            "trends week over week. Without that, you're guessing."
        ),
        "is_pillar": False,
        "status": Article.Status.PUBLISHED,
        "days_ago": 7,
    },
    {
        "slug": "faq-schema-aeo-quickwin",
        "title": "FAQ schema is still the fastest AEO win (and most sites don't have it)",
        "excerpt": "Adding FAQPage JSON-LD to your top 3 pages is the single highest-leverage AEO action — typically a 15-25 point boost in ChatGPT citation probability.",
        "content": (
            "FAQ schema (FAQPage JSON-LD) is the cleanest, most reliable AEO win available. It takes 30 minutes to implement and typically "
            "produces a 15-25 point lift in ChatGPT citation probability for the queries it targets. And yet — most sites still don't have it.\n\n"
            "## Why it works\n\n"
            "FAQPage schema is one of the only structured-data formats that AI engines literally use to construct their answers. When ChatGPT "
            "answers a question, it often pulls the answer verbatim from a FAQPage-marked block on a cited page. Without the schema, it has to "
            "infer the answer from prose — and inferred answers are much lower-confidence.\n\n"
            "Gemini and Perplexity also weight FAQPage schema heavily, though less than ChatGPT.\n\n"
            "## The 30-minute implementation\n\n"
            "1. Pick your three highest-traffic / highest-intent pages.\n"
            "2. For each, identify the 5 questions a buyer would ask before converting.\n"
            "3. Write a 1-paragraph answer for each (under 60 words).\n"
            "4. Wrap them in FAQPage JSON-LD:\n\n"
            "```json\n"
            "{\n"
            "  \"@context\": \"https://schema.org\",\n"
            "  \"@type\": \"FAQPage\",\n"
            "  \"mainEntity\": [{\n"
            "    \"@type\": \"Question\",\n"
            "    \"name\": \"How does X work?\",\n"
            "    \"acceptedAnswer\": { \"@type\": \"Answer\", \"text\": \"...\" }\n"
            "  }]\n"
            "}\n"
            "```\n\n"
            "5. Ship. Re-run your AI Visibility audit after 7-14 days.\n\n"
            "## What to expect\n\n"
            "Within 2-3 weeks, ChatGPT citations for the targeted prompts typically jump 20-40%. Gemini takes a bit longer (its knowledge "
            "panel re-indexing cycle). Perplexity responds within days because it queries live."
        ),
        "is_pillar": False,
        "status": Article.Status.PUBLISHED,
        "days_ago": 14,
    },
]


CASE_STUDIES = [
    {
        "slug": "northwind-agency-aeo-pivot",
        "title": "How Northwind Agency added $48K MRR by repositioning around AEO",
        "client_name": "Northwind Agency",
        "industry": "Agency",
        "challenge": (
            "Northwind ran a successful SEO agency for B2B SaaS clients but watched their pitch land flatter every quarter — "
            "prospects were starting to ask 'but what about AI search?' and Northwind didn't have a clean answer. Three retainers "
            "churned in Q3 alone, citing 'we need someone who handles AI visibility' as the reason."
        ),
        "solution": (
            "Northwind adopted VRT SPACE as the workspace for every client engagement. They started every audit with the screenshot "
            "showing that the client was invisible in ChatGPT for 8 of 10 target queries, while a named competitor was cited in 7 of them. "
            "That single image — paired with VRT's AI Visibility Score — became the centerpiece of every pitch. The team also "
            "tracked weekly share-of-voice progress and shared dashboard access with the client's CMO."
        ),
        "results": (
            "Within 90 days: 6 new retainers signed at an average of $8K/month MRR (totaling $48K). Churn dropped to zero in Q4. "
            "The team also reduced their reporting overhead from ~6 hours/week of manual spreadsheet work to ~30 minutes of reviewing "
            "VRT-generated dashboards. The founder cites the 'AI visibility before/after' screenshot as the single biggest sales tool "
            "they've ever used."
        ),
        "key_metric": "+$48K MRR in 90 days",
        "featured": True,
    },
    {
        "slug": "lumen-health-citations-jump",
        "title": "Lumen Health went from 0 to 79 AI Visibility Score in 6 weeks",
        "client_name": "Lumen Health",
        "industry": "Healthcare SaaS",
        "challenge": (
            "Lumen Health, a patient engagement platform for clinics, knew their content was solid but couldn't figure out why ChatGPT "
            "kept recommending Klara and Phreesia over them. They had no visibility into which queries they were winning, losing, or "
            "absent from — and their sales team was getting beat to consultations because prospects had already heard about competitors "
            "from AI."
        ),
        "solution": (
            "Lumen Health onboarded to VRT SPACE and added 5 high-intent prompts to their tracker: 'best patient engagement software for clinics', "
            "'HIPAA compliant patient reminder app', 'Lumen Health vs Klara', 'how to reduce patient no-shows with AI', and 'patient "
            "communication platform pricing'. The team also tracked Klara, Solv, Luma Health, and Phreesia as competitors. "
            "Within the first audit, VRT surfaced 3 specific fixes: missing FAQPage schema on their /security page, thin content on "
            "/pricing, and weak author bylines on their blog. They shipped all three fixes in two sprints."
        ),
        "results": (
            "After 6 weeks: AI Visibility Score went from 51 to 79. ChatGPT citations doubled (from 1 to 2 of 3 engines reliably "
            "citing them for the tracked prompts). Inbound consultation requests sourced from AI-referred traffic jumped 27%. "
            "Most importantly, in the 'Lumen Health vs Klara' query, Lumen Health now appears cited 100% of the time (up from "
            "0% at baseline)."
        ),
        "key_metric": "AI Visibility 51 → 79 in 6 weeks",
        "featured": True,
    },
    {
        "slug": "solo-studio-design-citations",
        "title": "How Solo Studio became the design partner ChatGPT recommends for early-stage SaaS",
        "client_name": "Solo Studio",
        "industry": "Creative agency",
        "challenge": (
            "Solo Studio, a 2-person Webflow + brand strategy shop, was getting drowned out by larger studios (Ueno, Ramotion, Studio Hooray) "
            "when SaaS founders asked AI 'who should I hire to design my SaaS marketing site?'. They had no marketing budget and "
            "couldn't outspend the competitors on backlinks."
        ),
        "solution": (
            "Solo Studio used VRT SPACE to track 3 specific queries and identify exactly which on-site signals were missing. "
            "VRT surfaced two issues: no FAQ schema on their /services page, and no E-E-A-T signals around their team (no author bios, "
            "no case study schema). The fix was a single afternoon's work — they added a FAQPage JSON-LD with 6 questions, plus "
            "a /about page with Person schema and real photos."
        ),
        "results": (
            "Within 4 weeks: appearing in 'best Webflow design studios for startups' (ChatGPT) at position 2-3 (previously not cited). "
            "Direct inbound from AI-referred founder traffic accounts for ~40% of their pipeline today. Solo Studio raised rates 30% "
            "since their work started being explicitly recommended by AI."
        ),
        "key_metric": "40% of pipeline from AI",
        "featured": False,
    },
]


class Command(BaseCommand):
    help = "Seed sample blog articles + case studies for demo / public surface."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete seeded entries first.")

    def handle(self, *args, **options):
        if options["reset"]:
            Article.objects.filter(slug__in=[a["slug"] for a in ARTICLES]).delete()
            CaseStudy.objects.filter(slug__in=[c["slug"] for c in CASE_STUDIES]).delete()
            self.stdout.write("Reset complete.")

        now = timezone.now()
        for data in ARTICLES:
            days_ago = data.pop("days_ago", 0)
            published_at = now - timedelta(days=days_ago)
            article, created = Article.objects.update_or_create(
                slug=data["slug"],
                defaults={**data, "published_at": published_at},
            )
            self.stdout.write(
                self.style.SUCCESS(f"OK {'created' if created else 'updated'} article: {article.title}")
            )

        for data in CASE_STUDIES:
            cs, created = CaseStudy.objects.update_or_create(
                slug=data["slug"],
                defaults=data,
            )
            self.stdout.write(
                self.style.SUCCESS(f"OK {'created' if created else 'updated'} case study: {cs.title}")
            )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Done. {Article.objects.filter(status=Article.Status.PUBLISHED).count()} published articles, "
            f"{CaseStudy.objects.count()} case studies."
        ))
