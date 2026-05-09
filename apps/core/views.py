import json

import requests
from django.http import Http404, JsonResponse
from django.db import OperationalError, ProgrammingError
from django.views.generic import TemplateView

from apps.case_studies.models import CaseStudy
from apps.leads.forms import AuditRequestForm, LeadCaptureForm
from apps.leads.billing import build_plan_cards

from .site_content import (
    ENGAGEMENT_STEPS,
    FAQS,
    PACKAGES,
    SERVICE_GROUPS,
    SERVICE_PAGE_LIST,
    SERVICE_PAGE_LOOKUP,
    SYSTEM_BLOCKS,
    VALUE_PILLARS,
)


def build_home_context(request, **extra):
    case_study = None
    try:
        case_study = CaseStudy.objects.filter(featured=True).first()
    except (OperationalError, ProgrammingError):
        case_study = None
    if not case_study:
        case_study = {
            "title": "B2B visibility turnaround",
            "client_name": "Enterprise SaaS brand",
            "industry": "B2B SaaS",
            "challenge": "Low organic authority and no footprint in AI answers.",
            "solution": "Rebuilt architecture, schema, and topic clusters around buyer questions.",
            "results": "2.4x qualified organic traffic and measurable growth in AI mention share.",
            "key_metric": "2.4x pipeline-ready traffic",
        }

    context = {
        "page_title": "Website Audit, SEO Analysis, and AI Visibility | VRT SPACE AGENCY",
        "meta_description": (
            "Run a website audit, uncover SEO gaps, improve AI visibility, and track progress in one VRT SPACE workspace."
        ),
        "canonical_url": request.build_absolute_uri(request.path),
        "og_title": "Website Audit, SEO Analysis, and AI Visibility | VRT SPACE AGENCY",
        "og_description": (
            "Understand what is holding your website back, what to fix next, and how to improve over time."
        ),
        "meta_robots": "index,follow",
        "schema_json": json.dumps(
            [
                {
                    "@context": "https://schema.org",
                    "@type": "Organization",
                    "name": "VRT SPACE AGENCY",
                    "description": "Website audit, SEO analysis, AI visibility, and workspace progress platform.",
                    "url": request.build_absolute_uri("/"),
                    "areaServed": ["Global"],
                    "sameAs": [],
                },
                {
                    "@context": "https://schema.org",
                    "@type": "FAQPage",
                    "mainEntity": [
                        {
                            "@type": "Question",
                            "name": item["question"],
                            "acceptedAnswer": {
                                "@type": "Answer",
                                "text": item["answer"],
                            },
                        }
                        for item in FAQS
                    ],
                },
            ]
        ),
        "lead_form": extra.get("lead_form", LeadCaptureForm()),
        "audit_form": extra.get("audit_form", AuditRequestForm()),
        "service_groups": SERVICE_GROUPS,
        "service_page_list": SERVICE_PAGE_LIST,
        "packages": PACKAGES,
        "system_blocks": SYSTEM_BLOCKS,
        "value_pillars": VALUE_PILLARS,
        "engagement_steps": ENGAGEMENT_STEPS,
        "faqs": FAQS,
        "results": [
            {"value": "3", "label": "Connected layers across audit, SEO, and AI visibility"},
            {"value": "1", "label": "Workspace that keeps every run and next step together"},
            {"value": "Repeat", "label": "Rerun after fixes and measure what improved"},
        ],
        "method_steps": [
            "Run a live audit to surface the biggest issues affecting speed, search visibility, and AI readiness.",
            "Review the SEO and AEO signals to understand what competitors are doing better and what your site is missing.",
            "Save the work in a workspace so your team can track recommendations, history, and next actions in one place.",
            "Rerun after updates to validate improvements and keep building progress over time.",
        ],
        "trust_signals": ["Audit-first clarity", "SEO roadmap", "AI visibility insight", "Workspace progress tracking"],
        "audiences": ["Founders", "Growth teams", "Enterprise brands", "Global Agencies"],
        "case_study": case_study,
        "critical_insight": (
            "Most websites do not have one visibility problem. They have a mix of technical, search, and AI-readiness gaps that need one clear order of attack."
        ),
        "shell_theme": "shell-light",
    }
    context.update(extra)
    return context


class HomePageView(TemplateView):
    template_name = "core/home.html"

    def get_context_data(self, **kwargs):
        return build_home_context(self.request, **kwargs)


class ServicesIndexView(TemplateView):
    template_name = "core/services.html"

    def get_context_data(self, **kwargs):
        return {
            "page_title": "Audit, SEO, and AEO Services | VRT SPACE AGENCY",
            "meta_description": "Explore the three connected VRT SPACE services: website audit, SEO analysis, and AI visibility.",
            "canonical_url": self.request.build_absolute_uri(self.request.path),
            "meta_robots": "index,follow",
            "shell_theme": "shell-light",
            "schema_json": json.dumps(
                {
                    "@context": "https://schema.org",
                    "@type": "CollectionPage",
                    "name": "VRT SPACE Services",
                    "description": "Website audit, SEO analysis, and AI visibility services.",
                    "url": self.request.build_absolute_uri(self.request.path),
                }
            ),
            "service_groups": SERVICE_GROUPS,
            "service_page_list": SERVICE_PAGE_LIST,
        }


class ServiceDetailView(TemplateView):
    template_name = "core/service_detail.html"

    def get_context_data(self, **kwargs):
        slug = kwargs["slug"]
        service = SERVICE_PAGE_LOOKUP.get(slug)
        if not service:
            raise Http404("Service not found.")

        return {
            "page_title": f"{service['name']} | VRT SPACE AGENCY",
            "meta_description": service["summary"],
            "canonical_url": self.request.build_absolute_uri(self.request.path),
            "meta_robots": "index,follow",
            "shell_theme": "shell-light",
            "schema_json": json.dumps(
                {
                    "@context": "https://schema.org",
                    "@type": "Service",
                    "name": service["name"],
                    "description": service["summary"],
                    "provider": {
                        "@type": "Organization",
                        "name": "VRT SPACE AGENCY",
                    },
                    "url": self.request.build_absolute_uri(self.request.path),
                }
            ),
            "service": service,
            "service_page_list": SERVICE_PAGE_LIST,
        }


class PackagesView(TemplateView):
    template_name = "core/packages.html"

    def get_context_data(self, **kwargs):
        return {
            "page_title": "Plans & Pricing | VRT SPACE AGENCY",
            "meta_description": "Compare VRT SPACE plans for audits, SEO analysis, AI visibility, and workspace progress tracking.",
            "canonical_url": self.request.build_absolute_uri(self.request.path),
            "meta_robots": "index,follow",
            "shell_theme": "shell-light",
            "schema_json": json.dumps(
                {
                    "@context": "https://schema.org",
                    "@type": "WebPage",
                    "name": "VRT SPACE Pricing",
                    "description": "Pricing for audits, SEO analysis, AI visibility, and workspace plans.",
                    "url": self.request.build_absolute_uri(self.request.path),
                }
            ),
            "plans": build_plan_cards(self.request.user),
        }

class ForAgenciesView(TemplateView):
    template_name = "core/for_agencies.html"

    def get_context_data(self, **kwargs):
        ref = self.request.GET.get("ref", "").strip()
        return {
            "page_title": "SEO & AI Visibility Platform for Agencies | VRT SPACE",
            "meta_description": (
                "Manage all your clients' SEO and AI visibility in one workspace. "
                "Run audits, track scores, and show measurable progress. Built for agencies."
            ),
            "og_title": "SEO & AI Visibility Platform for Agencies | VRT SPACE",
            "og_description": (
                "Your clients are invisible in AI search. Show them the gap — and fix it. "
                "VRT SPACE gives agencies one workspace for every client's SEO and AEO health."
            ),
            "canonical_url": self.request.build_absolute_uri(self.request.path),
            "meta_robots": "index,follow",
            "schema_json": json.dumps(
                {
                    "@context": "https://schema.org",
                    "@type": "WebPage",
                    "name": "VRT SPACE for Agencies",
                    "description": "Manage client SEO and AI visibility in one workspace.",
                    "url": self.request.build_absolute_uri(self.request.path),
                    "provider": {
                        "@type": "Organization",
                        "name": "VRT SPACE AGENCY",
                    },
                }
            ),
            "audit_form": AuditRequestForm(initial={"ref": ref} if ref else {}),
            "ref": ref,
            "shell_theme": "shell-light",
            "agency_stats": [
                {"value": "3–15", "label": "Client sites managed per agency"},
                {"value": "8 of 10", "label": "Queries where clients are invisible in AI answers"},
                {"value": "Weekly", "label": "Automated score tracking and delta alerts"},
            ],
            "pain_points": [
                {
                    "icon": "fas fa-random",
                    "title": "Context-switching between tools",
                    "body": "Ahrefs for backlinks, GSC for search, separate tools for AI — no single view of a client's health.",
                },
                {
                    "icon": "fas fa-eye-slash",
                    "title": "No AI visibility data",
                    "body": "None of the tools you already pay for tell you if your client is being cited in ChatGPT, Gemini, or Perplexity.",
                },
                {
                    "icon": "fas fa-chart-bar",
                    "title": "Can't show progress over time",
                    "body": "Clients ask 'Is it working?' You have no automated score history to point at.",
                },
            ],
            "platform_features": [
                {
                    "icon": "fas fa-th-large",
                    "tag": "Dashboard",
                    "title": "Bird's-eye view of every client",
                    "body": "One screen shows all your client sites with their overall score, the most at-risk category, and how the score has moved since the last audit.",
                },
                {
                    "icon": "fas fa-robot",
                    "tag": "AEO",
                    "title": "AI search visibility — measured",
                    "body": "See exactly which of your client's target queries are answered by AI and whether their brand is cited. No guessing.",
                },
                {
                    "icon": "fas fa-history",
                    "tag": "Progress",
                    "title": "Score deltas that justify the retainer",
                    "body": "Every audit run is saved. When a client asks if the work is paying off, you show them the score moving from 54 to 71 over 60 days.",
                },
                {
                    "icon": "fas fa-calendar-check",
                    "tag": "Automation",
                    "title": "Scheduled audits — no manual triggers",
                    "body": "Set weekly or monthly audit schedules per client. Get notified when a score drops so you catch regressions before the client does.",
                },
            ],
            "plan_comparison": [
                {"name": "Starter", "price": "$59/mo", "clients": "3 sites", "audits": "8 audits/mo", "highlight": False},
                {"name": "Growth", "price": "$149/mo", "clients": "10 sites", "audits": "24 audits/mo", "highlight": True},
                {"name": "Authority", "price": "$349/mo", "clients": "25 sites", "audits": "80 audits/mo", "highlight": False},
            ],
        }


def location_autocomplete(request):
    query = request.GET.get("q", "").strip()
    if len(query) < 2:
        return JsonResponse({"results": []})
    
    try:
        response = requests.get(
            "https://serpapi.com/locations.json", 
            params={"q": query, "limit": 10}, 
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                results = [
                    {
                        "id": item.get("id"),
                        "name": item.get("name"),
                        "canonical_name": item.get("canonical_name"),
                        "country_code": item.get("country_code"),
                        "target_type": item.get("target_type")
                    }
                    for item in data if "name" in item and "canonical_name" in item
                ][:10]
                return JsonResponse({"results": results})
    except Exception:
        pass
    
    return JsonResponse({"results": []})
