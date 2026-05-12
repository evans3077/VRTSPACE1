from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View

from apps.content.services import get_workspace_content_project
from apps.leads.billing import BillingError, build_credit_action_guide, can_access_workspace_feature, record_usage, spend_action_credits
from apps.leads.services import get_workspace_projects
from apps.leads.models import UsageRecord

from .forms import AEOAuditRequestForm
from .index_service import lookup_or_queue, normalise_domain
from .models import AEOAudit, AEOIndexEntry
from .services import build_aeo_payload, build_aeo_competitor_benchmarks, create_aeo_audit, get_latest_aeo_audit
from apps.seo.models import SEOProjectProfile


class WorkspaceAEOView(LoginRequiredMixin, View):
    template_name = "aeo/workspace_aeo.html"

    def get(self, request, *args, **kwargs):
        from .precision import is_precision_available
        project = get_workspace_content_project(user=request.user, request=request)
        latest_aeo_audit = get_latest_aeo_audit(project)

        # Surface real-LLM availability so the UI can warn when AEO falls
        # back to derived scoring (i.e. no API keys configured on the server).
        precision_engines = is_precision_available()
        precision_engine_status = [
            {"engine": "ChatGPT",    "available": precision_engines.get("chatgpt", False)},
            {"engine": "Gemini",     "available": precision_engines.get("gemini", False)},
            {"engine": "Perplexity", "available": precision_engines.get("perplexity", False)},
        ]
        precision_engines_available = sum(1 for e in precision_engine_status if e["available"])

        aeo_history = (
            project.aeo_audits.order_by("-created_at")[:10]
            if project and getattr(project, "pk", None)
            else []
        )
        
        aeo_intelligence = {}
        if project and hasattr(project, "seo_profile") and project.seo_profile:
            metadata = getattr(project.seo_profile, "metadata", {}) or {}
            aeo_intelligence = metadata.get("intelligence", {})

        # Always rebuild payload live so new fields (citation_readiness, engine_gaps) are current
        if latest_aeo_audit and latest_aeo_audit.source_audit_run:
            profile = SEOProjectProfile.objects.filter(project=project).first()
            live_payload = build_aeo_payload(
                audit_run=latest_aeo_audit.source_audit_run,
                profile=profile,
                target_keyword=latest_aeo_audit.target_keyword or "",
            )
        else:
            live_payload = latest_aeo_audit.output_json if latest_aeo_audit else {}

        # Build competitor benchmark
        profile = SEOProjectProfile.objects.filter(project=project).first() if project else None
        _bench_audit = latest_aeo_audit.source_audit_run if latest_aeo_audit else None
        competitor_benchmark = build_aeo_competitor_benchmarks(
            project=project,
            profile=profile,
            target_keyword=getattr(latest_aeo_audit, "target_keyword", "") or "",
            aeo_intelligence=aeo_intelligence,
        ) if project and _bench_audit else {"client": None, "competitors": [], "has_data": False}

        return render(
            request,
            self.template_name,
            {
                "project": project,
                "workspace_projects": get_workspace_projects(request.user),
                "form": AEOAuditRequestForm(initial={"target_keyword": getattr(latest_aeo_audit, "target_keyword", "")}),
                "latest_aeo_audit": latest_aeo_audit,
                "aeo_payload": live_payload,
                "aeo_history": aeo_history,
                "aeo_intelligence": aeo_intelligence,
                "competitor_benchmark": competitor_benchmark,
                "precision_engine_status": precision_engine_status,
                "precision_engines_available": precision_engines_available,
                "workspace_credit_actions": build_credit_action_guide(project, request.user) if project else [],
                "page_title": f"{project.name if project else 'Workspace'} AEO Workspace | VRT SPACE AGENCY",
                "meta_description": "Private AEO workspace for answer-engine visibility, citation readiness, and competitor comparison.",
                "canonical_url": request.build_absolute_uri(request.path),
                "meta_robots": "noindex, nofollow",
                "shell_theme": "shell-light",
            },
        )

    def post(self, request, *args, **kwargs):
        project = get_workspace_content_project(user=request.user, request=request)
        if not project:
            messages.error(request, "Create or connect a workspace project before running AEO analysis.")
            return redirect(f"{reverse('tools:workspace-dashboard')}#new-project")
        allowed, _ = can_access_workspace_feature(request.user, "aeo_workspace_enabled")
        if not allowed:
            messages.error(request, "AEO analysis requires a plan that includes AEO credits.")
            return redirect("tools:workspace-dashboard")

        form = AEOAuditRequestForm(request.POST)
        
        aeo_intelligence = {}
        if project and hasattr(project, "seo_profile") and project.seo_profile:
            metadata = getattr(project.seo_profile, "metadata", {}) or {}
            aeo_intelligence = metadata.get("intelligence", {})
            
        if not form.is_valid():
            latest_aeo_audit = get_latest_aeo_audit(project)
            return render(
                request,
                self.template_name,
                {
                    "project": project,
                    "workspace_projects": get_workspace_projects(request.user),
                    "form": form,
                    "latest_aeo_audit": latest_aeo_audit,
                    "aeo_payload": latest_aeo_audit.output_json if latest_aeo_audit else {},
                    "aeo_intelligence": aeo_intelligence,
                    "page_title": f"{project.name if project else 'Workspace'} AEO Workspace | VRT SPACE AGENCY",
                    "meta_description": "Private AEO workspace for answer-engine visibility, citation readiness, and competitor comparison.",
                    "canonical_url": request.build_absolute_uri(request.path),
                    "meta_robots": "noindex, nofollow",
                    "shell_theme": "shell-light",
                },
                status=400,
            )

        try:
            _entry, estimate = spend_action_credits(
                request.user,
                "aeo",
                project=project,
                note="AEO analysis",
                reference_key=f"aeo:{project.pk}:{form.cleaned_data['target_keyword'][:60]}",
            )
            aeo_audit = create_aeo_audit(
                project=project,
                target_keyword=form.cleaned_data["target_keyword"],
            )
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect("aeo:workspace-aeo")
        except BillingError as exc:
            messages.error(request, str(exc))
            return redirect("aeo:workspace-aeo")

        record_usage(request.user, UsageRecord.Metric.AEO_AUDIT)
        messages.success(
            request,
            f"AEO analysis created from the latest workspace audit. This run used {estimate['amount']} workspace credits.",
        )
        aeo_history = (
            project.aeo_audits.order_by("-created_at")[:10]
            if project and getattr(project, "pk", None)
            else []
        )
        # Rebuild payload live for consistency
        if latest_aeo_audit_obj := aeo_audit:
            profile_post = SEOProjectProfile.objects.filter(project=project).first()
            live_payload_post = build_aeo_payload(
                audit_run=aeo_audit.source_audit_run,
                profile=profile_post,
                target_keyword=aeo_audit.target_keyword or "",
            )
        else:
            live_payload_post = aeo_audit.output_json

        # Build competitor benchmark post-run
        profile_bench = SEOProjectProfile.objects.filter(project=project).first()
        competitor_benchmark_post = build_aeo_competitor_benchmarks(
            project=project,
            profile=profile_bench,
            target_keyword=aeo_audit.target_keyword or "",
            aeo_intelligence=aeo_intelligence,
        )

        return render(
            request,
            self.template_name,
            {
                "project": project,
                "workspace_projects": get_workspace_projects(request.user),
                "form": AEOAuditRequestForm(initial={"target_keyword": aeo_audit.target_keyword}),
                "latest_aeo_audit": aeo_audit,
                "aeo_payload": live_payload_post,
                "aeo_history": aeo_history,
                "aeo_intelligence": aeo_intelligence,
                "competitor_benchmark": competitor_benchmark_post,
                "workspace_credit_actions": build_credit_action_guide(project, request.user),
                "page_title": f"{project.name if project else 'Workspace'} AEO Workspace | VRT SPACE AGENCY",
                "meta_description": "Private AEO workspace for answer-engine visibility, citation readiness, and competitor comparison.",
                "canonical_url": request.build_absolute_uri(request.path),
                "meta_robots": "noindex, nofollow",
                "shell_theme": "shell-light",
            },
        )


class AEOAuditPollView(LoginRequiredMixin, View):
    """HTMX poll endpoint returning the AEO audit status as JSON.

    The workspace page polls this every few seconds while an audit is RUNNING.
    Once status is COMPLETED or FAILED the client stops polling and refreshes.
    """

    def get(self, request, pk, *args, **kwargs):
        audit = get_object_or_404(
            AEOAudit.objects.select_related("project"),
            pk=pk,
            project__owner=request.user,
        )
        return JsonResponse(
            {
                "status": audit.status,
                "precision_mode": audit.precision_mode,
                "queries_sent": audit.queries_sent,
                "engines_used": list(audit.engines_used or []),
                "overall_score": audit.overall_score,
            }
        )


class AEOShareView(View):
    """Public read-only AEO snapshot accessed via share_token."""

    template_name = "aeo/aeo_share.html"

    def get(self, request, token, *args, **kwargs):
        audit = (
            AEOAudit.objects.select_related("project", "source_audit_run", "seo_profile")
            .prefetch_related("recommendations", "visibility_snapshots")
            .filter(share_token=token)
            .first()
        )
        if not audit or not audit.share_active:
            raise Http404("Share link is invalid or expired.")

        # Rebuild payload live for accuracy
        if audit.source_audit_run:
            payload = build_aeo_payload(
                audit_run=audit.source_audit_run,
                profile=audit.seo_profile,
                target_keyword=audit.target_keyword or "",
            )
        else:
            payload = audit.output_json or {}

        return render(
            request,
            self.template_name,
            {
                "audit": audit,
                "payload": payload,
                "snapshots": list(audit.visibility_snapshots.all()),
                "page_title": f"AEO Visibility — {audit.project.name if audit.project else ''}",
                "meta_description": "Shared answer-engine visibility snapshot powered by VRT SPACE AGENCY.",
                "meta_robots": "noindex, nofollow",
                "canonical_url": request.build_absolute_uri(request.path),
                "shell_theme": "shell-light",
            },
        )


class AEOIndexHomeView(View):
    """Public landing page for the AEO visibility index.

    Indexable, SEO-targeted ("is your brand visible in ChatGPT?").
    Search box submits to the detail page for a given domain.
    """

    template_name = "aeo/aeo_index_home.html"

    def get(self, request, *args, **kwargs):
        top_entries = (
            AEOIndexEntry.objects.filter(status=AEOIndexEntry.Status.COMPLETED)
            .order_by("-overall_score", "-last_checked_at")[:12]
        )
        recent_lookups = AEOIndexEntry.objects.order_by("-lookup_count")[:8]
        return render(
            request,
            self.template_name,
            {
                "top_entries": top_entries,
                "recent_lookups": recent_lookups,
                "page_title": "AEO Visibility Index — Is your brand visible in ChatGPT, Gemini, and Perplexity?",
                "meta_description": "Free public tool: check whether ChatGPT, Gemini, and Perplexity cite your brand. AEO visibility scoring for any domain, powered by VRT SPACE AGENCY.",
                "canonical_url": request.build_absolute_uri(request.path),
                "shell_theme": "shell-light",
            },
        )

    def post(self, request, *args, **kwargs):
        raw = (request.POST.get("domain") or "").strip()
        domain = normalise_domain(raw)
        if not domain:
            messages.error(request, "Enter a valid domain.")
            return redirect("aeo:aeo-index")
        return redirect("aeo:aeo-index-detail", domain=domain)


class AEOIndexDetailView(View):
    """Public per-domain detail page.

    On first visit, kicks off a lightweight precision pass (rate-limited)
    and persists the result for future lookups.  All detail pages are
    indexable to drive organic search traffic.
    """

    template_name = "aeo/aeo_index_detail.html"

    def get(self, request, domain, *args, **kwargs):
        domain = normalise_domain(domain)
        if not domain:
            raise Http404("Invalid domain.")
        try:
            entry = lookup_or_queue(domain)
        except ValueError:
            raise Http404("Invalid domain.")

        page_title = f"Is {entry.domain} cited by ChatGPT, Gemini, or Perplexity? | AEO Visibility Index"
        if entry.status == AEOIndexEntry.Status.COMPLETED:
            meta = (
                f"AEO visibility check for {entry.domain}: "
                f"{entry.engines_cited_count}/3 engines cite this brand. "
                f"Score: {entry.overall_score}/100."
            )
        else:
            meta = f"Checking AEO visibility for {entry.domain} across ChatGPT, Gemini, and Perplexity."

        return render(
            request,
            self.template_name,
            {
                "entry": entry,
                "page_title": page_title,
                "meta_description": meta,
                "canonical_url": request.build_absolute_uri(request.path),
                "shell_theme": "shell-light",
            },
        )
