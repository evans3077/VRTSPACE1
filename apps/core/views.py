import json

from django.http import Http404
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
        "page_title": "VRT SPACE AGENCY | SEO Audits, AI Visibility, and Growth Workspace",
        "meta_description": (
            "VRT SPACE AGENCY provides SEO audits, AI visibility diagnostics, growth workspaces, "
            "and custom implementation paths for websites, apps, and advanced search systems."
        ),
        "schema_json": json.dumps(
            {
                "@context": "https://schema.org",
                "@type": "Organization",
                "name": "VRT SPACE AGENCY",
                "description": "SEO audit, AI visibility, workspace, analytics, and custom implementation platform.",
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
            {"value": "21", "label": "Solution paths connected to one growth system"},
            {"value": "4", "label": "Visible plans from Starter to Enterprise"},
            {"value": "3", "label": "Core product surfaces for audits, workspaces, and ops"},
        ],
        "method_steps": [
            "Map audits, workspace flows, and package destinations into a website that teaches, qualifies, and converts without a manual sales dependency.",
            "Build SEO, AEO, development, content, and analytics into one product stack instead of disconnected offers.",
            "Turn tools, audit summaries, dashboards, and follow-up sequences into an always-on growth engine.",
            "Use reporting, performance, and AI visibility monitoring to keep users informed and expand them into higher-value modules when needed.",
        ],
        "trust_signals": ["SEO foundation", "AI citation edge", "Global Search Dominance", "Enterprise-capable delivery"],
        "audiences": ["Founders", "Growth teams", "Enterprise brands", "Global Agencies"],
        "case_study": case_study,
        "critical_insight": (
            "Most sites still stop at lead capture and manual follow-up. VRT SPACE is being built "
            "as a product system that audits, groups fixes, routes users into workspaces, and only escalates to direct scoping when the request is custom."
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
            "page_title": "VRT SPACE AGENCY Solutions",
            "meta_description": "Browse the VRT SPACE growth system across SEO, AI visibility, reporting, workspaces, and custom implementation paths.",
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


class PackagesView(TemplateView):
    template_name = "core/packages.html"

    def get_context_data(self, **kwargs):
        return {
            "page_title": "Plans & Pricing | VRT SPACE AGENCY",
            "meta_description": "Flexible plans designed to evolve with your business.",
            "plans": build_plan_cards(self.request.user),
        }
