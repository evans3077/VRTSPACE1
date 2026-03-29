import json

from django.http import Http404
from django.db import OperationalError, ProgrammingError
from django.views.generic import TemplateView

from apps.case_studies.models import CaseStudy
from apps.leads.forms import AuditRequestForm, LeadCaptureForm

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
        "page_title": "VRT SPACE AGENCY | SEO, AEO, Web Development, and AI Visibility",
        "meta_description": (
            "VRT SPACE AGENCY offers SEO, AEO, web development, content, CRO, local SEO, "
            "analytics, authority building, and AI visibility systems designed to sell automatically."
        ),
        "schema_json": json.dumps(
            {
                "@context": "https://schema.org",
                "@type": "ProfessionalService",
                "name": "VRT SPACE AGENCY",
                "description": "SEO, AEO, web development, analytics, and AI visibility agency.",
                "url": request.build_absolute_uri("/"),
                "areaServed": ["Kenya", "Global"],
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
            {"value": "21", "label": "Service lines mapped to one sellable system"},
            {"value": "4", "label": "Commercial packages from Starter to Enterprise"},
            {"value": "3", "label": "Core internal systems for automation and retention"},
        ],
        "method_steps": [
            "Map revenue services into a website that teaches, qualifies, and converts without manual selling.",
            "Build SEO, AEO, development, content, and analytics into one delivery stack instead of disconnected offers.",
            "Turn tools, audits, dashboards, and follow-up sequences into an always-on lead engine.",
            "Use reporting, performance, and AI visibility monitoring to keep clients retained and upsell-ready.",
        ],
        "trust_signals": ["SEO foundation", "AI citation edge", "Kenya-ready local SEO", "Enterprise-capable delivery"],
        "audiences": ["Founders", "Growth teams", "Enterprise brands", "Local Kenyan businesses"],
        "case_study": case_study,
        "critical_insight": (
            "Most agencies still sell services manually and depend on outreach. VRT SPACE is being built "
            "as a system that sells, audits, converts, and upsells automatically."
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
            "page_title": "VRT SPACE AGENCY Services",
            "meta_description": "Browse the VRT SPACE service stack across SEO, AEO, web development, content, CRO, analytics, and AI visibility.",
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
            "service": service,
            "service_page_list": SERVICE_PAGE_LIST,
        }
