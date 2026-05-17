"""
One-shot demo seeder for VRT SPACE AGENCY.

Creates 3 sample workspaces (free / growth / agency) with realistic data:
- Users with known credentials
- ClientProjects linked to fake brand domains
- Completed AuditRun + AuditPages (so AEO + workspace dashboards have data)
- AEOAudit with scores + recommendations
- TrackedPrompts + TrackedCompetitors with simulated check history
- WorkspaceAuditSchedule so the dashboard activation checklist completes

Run:
    python manage.py seed_demo
    python manage.py seed_demo --reset   # wipe previous demo users and recreate
"""

from __future__ import annotations

import os
import random
import sys
from datetime import timedelta

# Windows console defaults to cp1252; ensure UTF-8 output for any unicode chars.
if sys.platform == "win32" and os.environ.get("PYTHONIOENCODING") is None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
from typing import Iterable

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.aeo.models import (
    AEOAudit,
    AIRecommendation,
    PromptCheckRun,
    TrackedCompetitor,
    TrackedPrompt,
    VisibilitySnapshot,
)
from apps.aeo.prompt_service import run_prompt_check
from apps.aeo.simulator import (
    build_competitor_features,
    derive_target_features,
    simulate_prompt_check,
)
from apps.leads.billing import sync_workspace_plan_catalog
from apps.leads.models import ClientProject, WorkspacePlan, WorkspaceSubscription
from apps.seo.models import SEOProjectProfile
from apps.tools.models import AuditPage, AuditRun, WorkspaceAuditSchedule


User = get_user_model()


DEMO_SUFFIX = "@demo.vrtspace.dev"


DEMO_USERS = [
    {
        "kind": "free",
        "email": f"alex.solo{DEMO_SUFFIX}",
        "password": "VrtDemo!2026",
        "name": "Alex Solo",
        "brand": "Solo Studio",
        "domain": "solostudio.co",
        "website": "https://solostudio.co",
        "business_type": "creative",
        "primary_service": "Brand strategy and Webflow design",
        "location": "Remote (NYC, US)",
        "target_goal": "Win product-led brands searching for design partners",
        "plan_slug": "free",
        "prompts": [
            ("best Webflow design studios for startups", "comparison"),
            ("how to choose a brand strategist", "informational"),
            ("Webflow vs Framer for SaaS landing pages", "comparison"),
        ],
        "competitors": [
            ("Ueno", "ueno.co", "#f97316"),
            ("Studio Hooray", "studiohooray.com", "#8b5cf6"),
            ("Ramotion", "ramotion.com", "#10b981"),
        ],
        "audit_scores": {"overall": 71, "tech": 78, "on_page": 65, "content": 70, "aeo": 58, "perf": 74, "internal": 64},
        "pages": [
            ("/", "Solo Studio — Brand & Webflow for product teams", "Brand & Webflow for product teams", 540, 2, True),
            ("/work", "Selected work — Solo Studio", "Selected work", 320, 1, False),
            ("/services/brand", "Brand strategy — Solo Studio", "Brand strategy services", 460, 1, False),
        ],
    },
    {
        "kind": "growth",
        "email": f"morgan.lee{DEMO_SUFFIX}",
        "password": "VrtDemo!2026",
        "name": "Morgan Lee",
        "brand": "Lumen Health",
        "domain": "lumenhealth.io",
        "website": "https://lumenhealth.io",
        "business_type": "saas",
        "primary_service": "Healthcare patient engagement platform",
        "location": "San Francisco, CA, US",
        "target_goal": "Be cited by AI when clinics research patient engagement tools",
        "plan_slug": "growth",
        "prompts": [
            ("best patient engagement software for clinics", "comparison"),
            ("HIPAA compliant patient reminder app", "informational"),
            ("Lumen Health vs Klara", "brand"),
            ("how to reduce patient no-shows with AI", "informational"),
            ("patient communication platform pricing", "commercial"),
        ],
        "competitors": [
            ("Klara", "klara.com", "#f43f5e"),
            ("Solv", "solvhealth.com", "#facc15"),
            ("Luma Health", "lumahealth.io", "#0ea5e9"),
            ("Phreesia", "phreesia.com", "#a855f7"),
        ],
        "audit_scores": {"overall": 84, "tech": 88, "on_page": 82, "content": 80, "aeo": 76, "perf": 89, "internal": 78},
        "pages": [
            ("/", "Lumen Health — patient engagement that clinics actually use", "Patient engagement that clinics use", 880, 6, True),
            ("/product/reminders", "Automated appointment reminders | Lumen Health", "Automated appointment reminders", 720, 3, True),
            ("/product/intake", "Digital patient intake forms | Lumen Health", "Digital patient intake", 690, 3, True),
            ("/security", "HIPAA & SOC2 — Lumen Health Security", "HIPAA and SOC2 compliance", 1240, 4, False),
            ("/pricing", "Pricing — Lumen Health", "Lumen Health pricing", 410, 2, False),
        ],
    },
    {
        "kind": "agency",
        "email": f"sam.rivera{DEMO_SUFFIX}",
        "password": "VrtDemo!2026",
        "name": "Sam Rivera",
        "brand": "Northwind Agency",
        "domain": "northwind.agency",
        "website": "https://northwind.agency",
        "business_type": "agency",
        "primary_service": "AI SEO and AEO agency for B2B software brands",
        "location": "London, UK",
        "target_goal": "Become the go-to AEO partner cited across ChatGPT & Perplexity",
        "plan_slug": "authority",
        "prompts": [
            ("best AEO agency for B2B SaaS", "comparison"),
            ("AI SEO agency for fintech", "comparison"),
            ("how to optimize content for Perplexity citations", "informational"),
            ("agencies that specialise in ChatGPT visibility", "comparison"),
            ("Profound vs Otterly vs Northwind", "brand"),
            ("answer engine optimization for enterprise SaaS", "commercial"),
            ("how much does an AEO agency cost in 2026", "commercial"),
        ],
        "competitors": [
            ("Profound", "tryprofound.com", "#06b6d4"),
            ("Otterly AI", "otterly.ai", "#10b981"),
            ("Athena HQ", "athenahq.ai", "#f97316"),
            ("Peec AI", "peec.ai", "#a855f7"),
            ("Goodie AI", "goodie.ai", "#ec4899"),
        ],
        "audit_scores": {"overall": 92, "tech": 95, "on_page": 90, "content": 89, "aeo": 88, "perf": 93, "internal": 91},
        "pages": [
            ("/", "Northwind — the AEO agency for B2B SaaS", "AEO agency for B2B SaaS", 1240, 8, True),
            ("/services/aeo-strategy", "AEO Strategy — Northwind", "AEO strategy service", 920, 5, True),
            ("/services/ai-content", "AI-ready content ops — Northwind", "AI-ready content", 880, 5, True),
            ("/insights/perplexity-citations", "How to win Perplexity citations in 2026 | Northwind", "Perplexity citations playbook", 1820, 4, True),
            ("/case-studies", "Case studies — Northwind", "Client outcomes and case studies", 640, 3, False),
            ("/pricing", "Pricing & engagements — Northwind", "Pricing", 480, 2, False),
            ("/about", "About Northwind", "Who we are", 540, 3, False),
        ],
    },
]


def _build_audit_run(*, project_data: dict) -> AuditRun:
    scores = project_data["audit_scores"]
    audit = AuditRun.objects.create(
        normalized_domain=project_data["domain"],
        start_url=project_data["website"],
        status=AuditRun.Status.COMPLETED,
        overall_score=scores["overall"],
        technical_score=scores["tech"],
        on_page_score=scores["on_page"],
        content_score=scores["content"],
        aeo_score=scores["aeo"],
        internal_linking_score=scores["internal"],
        performance_score=scores["perf"],
        pages_crawled=len(project_data["pages"]),
        summary={
            "context_analysis": {"business_type": project_data["business_type"]},
            "location": project_data["location"],
        },
        completed_at=timezone.now() - timedelta(hours=2),
    )
    for path, title, h1, wc, schema_count, has_faq in project_data["pages"]:
        AuditPage.objects.create(
            audit_run=audit,
            url=project_data["website"].rstrip("/") + path,
            status_code=200,
            title=title,
            meta_description=f"{title[:140]}",
            h1=h1,
            canonical_url=project_data["website"].rstrip("/") + path,
            word_count=wc,
            schema_count=schema_count,
            has_faq_schema=has_faq,
            response_time_ms=380 + (wc % 200),
            pagespeed_score=78 + (wc % 18),
            internal_link_count=12 + (wc % 8),
        )
    return audit


def _build_aeo_audit(*, project: ClientProject, audit_run: AuditRun, scores: dict, target_keyword: str) -> AEOAudit:
    overall = scores["overall"]
    aeo = AEOAudit.objects.create(
        project=project,
        source_audit_run=audit_run,
        target_keyword=target_keyword,
        visibility_score=min(95, overall - 5),
        entity_score=min(95, overall - 2),
        structure_score=min(95, overall - 8),
        completeness_score=min(95, overall - 6),
        output_json={
            "scores": {
                "visibility_score": min(95, overall - 5),
                "entity_score": min(95, overall - 2),
                "structure_score": min(95, overall - 8),
                "completeness_score": min(95, overall - 6),
                "citation_readiness": overall,
            }
        },
        status=AEOAudit.Status.COMPLETED,
        engines_used=["chatgpt", "gemini", "perplexity"],
        queries_sent=8,
    )

    sample_recs = [
        ("Add FAQPage JSON-LD to your top 3 service pages.",
         "AI engines like ChatGPT specifically use FAQPage schema to extract Q&A.",
         "Wrap your 5 most-asked questions in FAQPage JSON-LD on the service hub page.",
         "Typically +15-25 pt boost in ChatGPT citation probability.",
         88, "Answer structure"),
        ("Expand thin service pages to 600+ words with specifics.",
         "Perplexity sources from fact-dense pages over 600 words.",
         "Add 'What's Included', pricing tiers, and 'Who this is for' sections.",
         "Unlocks Perplexity citations for primary keywords.",
         76, "Content depth"),
        ("Cite primary research and inline-link authoritative sources.",
         "Perplexity scores by inline citation density.",
         "Add 3-5 links to industry studies on each pillar page.",
         "Improves Perplexity authority weighting by 10-15 pts.",
         72, "Authority"),
    ]
    for issue, why, fix, impact, prio, cat in sample_recs:
        AIRecommendation.objects.create(
            aeo_audit=aeo,
            issue=issue,
            why_ai_ignores_this=why,
            fix=fix,
            expected_impact=impact,
            priority_score=prio,
            category=cat,
        )

    # Snapshot rows (one per engine) for the share view
    for engine, freq, ans in (
        (VisibilitySnapshot.Engine.CHATGPT, 2 if overall >= 80 else 1, overall >= 70),
        (VisibilitySnapshot.Engine.GEMINI, 2 if overall >= 85 else 1, overall >= 75),
        (VisibilitySnapshot.Engine.PERPLEXITY, 1 if overall >= 80 else 0, overall >= 78),
    ):
        VisibilitySnapshot.objects.create(
            aeo_audit=aeo,
            engine=engine,
            prompt=target_keyword,
            cited_url=audit_run.start_url if ans else "",
            answer_present=ans,
            citation_frequency=freq,
            notes=f"Simulated baseline from on-page audit — {engine}.",
        )
    return aeo


def _seed_prompt_history(prompt: TrackedPrompt, *, target_features, competitor_features, weeks: int = 6):
    """Generate plausible historical PromptCheckRuns spread over the past `weeks` weeks."""
    now = timezone.now()
    for week in range(weeks, 0, -1):
        run_dt = now - timedelta(days=week * 7 + random.randint(-2, 2))
        for engine in (
            VisibilitySnapshot.Engine.CHATGPT,
            VisibilitySnapshot.Engine.GEMINI,
            VisibilitySnapshot.Engine.PERPLEXITY,
        ):
            # Add small per-week noise to give the chart movement
            jitter_features = []
            for feat in competitor_features:
                jitter = random.uniform(-4, 4)
                feat_copy = type(feat)(**{**feat.__dict__})
                feat_copy.authority = max(0, min(100, feat.authority + jitter))
                feat_copy.depth = max(0, min(100, feat.depth + jitter))
                jitter_features.append(feat_copy)

            result = simulate_prompt_check(
                prompt_text=f"{prompt.prompt} ::w{week}",  # vary seed per week
                engine=engine,
                target=target_features,
                competitors=jitter_features,
            )
            PromptCheckRun.objects.create(
                prompt=prompt,
                engine=engine,
                target_cited=result["target_cited"],
                target_position=result["target_position"],
                citation_score=result["citation_score"],
                answer_snippet=result["answer_snippet"],
                cited_brands=result["cited_brands"],
                competitor_brands=result["competitor_brands"],
                sentiment=result["sentiment"],
                raw_signals=result["raw_signals"],
                created_at=run_dt,
                updated_at=run_dt,
            )
    # Bump prompt's last-checked timestamps via a final live check
    run_prompt_check(prompt)


class Command(BaseCommand):
    help = "Seed demo users, workspaces, audits, prompts, and citation history."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing demo users (matching @demo.vrtspace.dev) before re-seeding.",
        )
        parser.add_argument(
            "--weeks",
            type=int,
            default=6,
            help="How many weeks of prompt-check history to backfill (default: 6).",
        )

    def handle(self, *args, **options):
        random.seed(2026)
        weeks = options["weeks"]

        sync_workspace_plan_catalog()
        self.stdout.write(self.style.SUCCESS("OK Plan catalog synced."))

        if options["reset"]:
            self.stdout.write("Resetting demo users…")
            User.objects.filter(email__iendswith=DEMO_SUFFIX).delete()

        plans_by_slug = {p.slug: p for p in WorkspacePlan.objects.all()}

        for data in DEMO_USERS:
            with transaction.atomic():
                self._seed_one(data, plans_by_slug, weeks=weeks)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=== Demo seed complete ==="))
        self.stdout.write("Login credentials (use the workspace sign-in page):")
        for data in DEMO_USERS:
            self.stdout.write(f"  - {data['kind'].upper():8s} {data['email']}  |  {data['password']}")
        self.stdout.write("")
        self.stdout.write("Open the homepage and sign in as any of the above.")

    def _seed_one(self, data: dict, plans_by_slug: dict, *, weeks: int):
        email = data["email"]
        user, created = User.objects.get_or_create(
            username=email,
            defaults={"email": email, "first_name": data["name"].split()[0], "last_name": data["name"].split()[-1]},
        )
        if created or not user.has_usable_password():
            user.set_password(data["password"])
            user.save()

        # Subscription
        plan = plans_by_slug.get(data["plan_slug"])
        if plan:
            WorkspaceSubscription.objects.update_or_create(
                user=user,
                defaults={"plan": plan, "status": WorkspaceSubscription.Status.ACTIVE},
            )

        # Project
        project, _ = ClientProject.objects.update_or_create(
            owner=user,
            name=data["brand"],
            defaults={
                "website": data["website"],
                "normalized_domain": data["domain"],
                "contact_email": email,
                "business_type": data["business_type"],
                "primary_service": data["primary_service"],
                "location": data["location"],
                "target_goal": data["target_goal"],
                "stage": ClientProject.Stage.ACTIVE,
                "notes": ", ".join([p[0] for p in data["prompts"][:3]]),
            },
        )

        # Audit
        audit_run = _build_audit_run(project_data=data)
        project.latest_audit_run = audit_run
        project.latest_score = data["audit_scores"]["overall"]
        project.save(update_fields=("latest_audit_run", "latest_score", "updated_at"))

        # SEO profile (needed for AEO context)
        SEOProjectProfile.objects.update_or_create(
            project=project,
            defaults={
                "business_type": data["business_type"],
                "primary_service": data["primary_service"],
                "location": data["location"],
                "target_goal": data["target_goal"],
            },
        )

        # AEO audit
        aeo_audit = _build_aeo_audit(
            project=project,
            audit_run=audit_run,
            scores=data["audit_scores"],
            target_keyword=data["prompts"][0][0] if data["prompts"] else "AI visibility",
        )

        # Schedule (so activation checklist completes)
        WorkspaceAuditSchedule.objects.update_or_create(
            project=project,
            defaults={
                "cadence": WorkspaceAuditSchedule.Cadence.WEEKLY,
                "is_active": True,
                "last_audit_run": audit_run,
                "last_run_at": timezone.now() - timedelta(hours=2),
                "next_run_at": timezone.now() + timedelta(days=7),
            },
        )

        # Competitors
        for brand_name, domain, color in data["competitors"]:
            TrackedCompetitor.objects.update_or_create(
                project=project,
                brand_name=brand_name,
                defaults={"domain": domain, "color": color, "is_active": True},
            )

        # Tracked prompts + simulated history
        target_features = derive_target_features(audit_run=audit_run, aeo_audit=aeo_audit)
        target_features.label = data["brand"]
        competitor_features = [
            build_competitor_features(c)
            for c in TrackedCompetitor.objects.filter(project=project, is_active=True)
        ]
        for prompt_text, intent in data["prompts"]:
            prompt, prompt_created = TrackedPrompt.objects.update_or_create(
                project=project,
                prompt=prompt_text,
                defaults={"intent": intent, "is_active": True},
            )
            # Wipe pre-existing runs only when re-seeding the same prompt
            PromptCheckRun.objects.filter(prompt=prompt).delete()
            _seed_prompt_history(
                prompt,
                target_features=target_features,
                competitor_features=competitor_features,
                weeks=weeks,
            )

        self.stdout.write(self.style.SUCCESS(
            f"OK {data['kind']:8s} {data['brand']:20s} → {len(data['prompts'])} prompts, "
            f"{len(data['competitors'])} competitors, audit score {data['audit_scores']['overall']}"
        ))
