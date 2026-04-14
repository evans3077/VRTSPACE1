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
        "body_class": "marketing-body",
        "page_title": "VRT SPACE AGENCY | SEO, Website Audits, and AEO",
        "meta_description": (
            "VRT SPACE AGENCY helps businesses improve SEO, run clear website audits, and strengthen AI visibility with a simpler, audit-led growth path."
        ),
        "schema_json": json.dumps(
            {
                "@context": "https://schema.org",
                "@type": "Organization",
                "name": "VRT SPACE AGENCY",
                "description": "SEO, website audit, and AI visibility agency.",
                "url": request.build_absolute_uri("/"),
                "areaServed": ["Global"],
                "sameAs": [],
            }
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
            {"value": "Audit-led", "label": "Start with evidence"},
            {"value": "Search + AI", "label": "Visibility focus"},
            {"value": "Priority-first", "label": "Clear next steps"},
        ],
        "method_steps": [
            "Start with a live audit so the next decision is based on evidence.",
            "Use SEO to improve how the business gets found in search.",
            "Use AEO to improve how the business shows up in AI answers.",
            "Keep the next step simple: fix what matters first, then expand only when needed.",
        ],
        "trust_signals": [
            "Audit-led recommendations",
            "SEO and AI visibility focus",
            "No bloated public offer",
        ],
        "audiences": ["Founders", "Growth teams", "Enterprise brands", "Global Agencies"],
        "case_study": case_study,
        "critical_insight": (
            "Most businesses do not need more noise. They need a clear audit, a realistic SEO plan, and stronger visibility in both search engines and AI answers."
        ),
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
            "body_class": "marketing-body",
            "page_title": "SEO, Audit, and AEO Services | VRT SPACE AGENCY",
            "meta_description": "Explore the three core VRT SPACE services: SEO, website audits, and AEO.",
            "service_groups": SERVICE_GROUPS,
            "service_page_list": SERVICE_PAGE_LIST,
            "faqs": FAQS,
        }


class ServiceDetailView(TemplateView):
    template_name = "core/service_detail.html"

    def get_context_data(self, **kwargs):
        slug = kwargs["slug"]
        service = SERVICE_PAGE_LOOKUP.get(slug)
        if not service:
            raise Http404("Service not found.")

        return {
            "body_class": "marketing-body",
            "page_title": f"{service['name']} | VRT SPACE AGENCY",
            "meta_description": f"{service['summary']} Learn how VRT SPACE uses an audit-led process to improve visibility and next-step clarity.",
            "service": service,
            "service_page_list": SERVICE_PAGE_LIST,
        }


class PackagesView(TemplateView):
    template_name = "core/packages.html"

    def get_context_data(self, **kwargs):
        return {
            "body_class": "marketing-body",
            "page_title": "Plans & Pricing | VRT SPACE AGENCY",
            "meta_description": "Choose a VRT SPACE plan for audit-led SEO and AEO improvement.",
            "plans": build_plan_cards(self.request.user),
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
