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
from .models import AEOAudit, AEOIndexEntry, PromptCheckRun, TrackedCompetitor, TrackedPrompt
from .prompt_service import (
    compute_share_of_voice,
    get_competitor_summary,
    get_prompt_trend,
    run_all_active,
    run_prompt_check,
)
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


# ─── Prompt Tracker ────────────────────────────────────────────────────────


class WorkspacePromptsView(LoginRequiredMixin, View):
    """List + create tracked prompts and competitors. The killer AEO feature."""

    template_name = "aeo/workspace_prompts.html"

    def _build_context(self, request, project):
        prompts = list(
            TrackedPrompt.objects.filter(project=project).order_by("-is_active", "-last_checked_at", "prompt")
        )
        competitors = get_competitor_summary(project)
        sov = compute_share_of_voice(project, days=30)
        intent_choices = TrackedPrompt.Intent.choices
        return {
            "project": project,
            "workspace_projects": get_workspace_projects(request.user),
            "prompts": prompts,
            "competitors": competitors,
            "share_of_voice": sov,
            "intent_choices": intent_choices,
            "page_title": f"AI Prompt Tracker — {project.name if project else 'Workspace'} | VRT SPACE AGENCY",
            "meta_description": "Track exactly which AI prompts cite you, who you're competing against, and where you're losing share of voice.",
            "canonical_url": request.build_absolute_uri(request.path),
            "meta_robots": "noindex, nofollow",
            "shell_theme": "shell-light",
        }

    def get(self, request, *args, **kwargs):
        project = get_workspace_content_project(user=request.user, request=request)
        if not project:
            messages.info(request, "Create a workspace project first to start tracking prompts.")
            return redirect("tools:workspace-dashboard")
        return render(request, self.template_name, self._build_context(request, project))

    def post(self, request, *args, **kwargs):
        project = get_workspace_content_project(user=request.user, request=request)
        if not project:
            return redirect("tools:workspace-dashboard")

        action = (request.POST.get("action") or "").strip()

        if action == "add_prompt":
            prompt_text = (request.POST.get("prompt") or "").strip()
            intent = (request.POST.get("intent") or TrackedPrompt.Intent.INFORMATIONAL).strip()
            if not prompt_text:
                messages.error(request, "Prompt text is required.")
            elif len(prompt_text) > 300:
                messages.error(request, "Prompts must be 300 characters or fewer.")
            else:
                prompt, created = TrackedPrompt.objects.get_or_create(
                    project=project,
                    prompt=prompt_text,
                    defaults={"intent": intent},
                )
                if created:
                    try:
                        run_prompt_check(prompt)
                        messages.success(request, f"Tracking '{prompt_text[:60]}' across ChatGPT, Gemini and Perplexity.")
                    except Exception as exc:  # pragma: no cover
                        messages.warning(request, f"Prompt saved but initial check failed: {exc}")
                else:
                    messages.info(request, "Prompt already tracked.")

        elif action == "add_competitor":
            brand_name = (request.POST.get("brand_name") or "").strip()
            domain = (request.POST.get("domain") or "").strip().lower().replace("https://", "").replace("http://", "").strip("/")
            color = (request.POST.get("color") or "#818cf8").strip()
            if not brand_name:
                messages.error(request, "Brand name is required.")
            else:
                comp, created = TrackedCompetitor.objects.get_or_create(
                    project=project,
                    brand_name=brand_name,
                    defaults={"domain": domain, "color": color},
                )
                if not created and (comp.domain != domain or comp.color != color):
                    comp.domain = domain or comp.domain
                    comp.color = color or comp.color
                    comp.is_active = True
                    comp.save(update_fields=("domain", "color", "is_active", "updated_at"))
                messages.success(request, f"{'Added' if created else 'Updated'} competitor {brand_name}.")

        elif action == "delete_prompt":
            prompt_id = request.POST.get("prompt_id")
            TrackedPrompt.objects.filter(pk=prompt_id, project=project).delete()
            messages.info(request, "Prompt removed.")

        elif action == "delete_competitor":
            comp_id = request.POST.get("competitor_id")
            TrackedCompetitor.objects.filter(pk=comp_id, project=project).delete()
            messages.info(request, "Competitor removed.")

        elif action == "rerun_all":
            summary = run_all_active(project)
            messages.success(
                request,
                f"Refreshed {summary['prompts']} prompts — {summary['citations']} citations across {summary['runs_created']} engine checks.",
            )

        elif action == "rerun_prompt":
            prompt_id = request.POST.get("prompt_id")
            prompt = TrackedPrompt.objects.filter(pk=prompt_id, project=project).first()
            if prompt:
                run_prompt_check(prompt)
                messages.success(request, f"Refreshed '{prompt.prompt[:60]}'.")

        return redirect("aeo:workspace-prompts")


class WorkspacePromptDetailView(LoginRequiredMixin, View):
    """Time-series detail page for a single tracked prompt."""

    template_name = "aeo/prompt_detail.html"

    def get(self, request, pk, *args, **kwargs):
        project = get_workspace_content_project(user=request.user, request=request)
        if not project:
            return redirect("tools:workspace-dashboard")
        prompt = get_object_or_404(TrackedPrompt, pk=pk, project=project)
        trend = get_prompt_trend(prompt, days=90)
        recent_runs = list(
            PromptCheckRun.objects.filter(prompt=prompt).order_by("-created_at")[:15]
        )
        return render(
            request,
            self.template_name,
            {
                "project": project,
                "workspace_projects": get_workspace_projects(request.user),
                "prompt": prompt,
                "trend": trend,
                "recent_runs": recent_runs,
                "page_title": f"Prompt trend — {prompt.prompt[:60]} | VRT SPACE AGENCY",
                "meta_description": "Track AI citations for this prompt across ChatGPT, Gemini and Perplexity.",
                "meta_robots": "noindex, nofollow",
                "shell_theme": "shell-light",
            },
        )


class ContentOptimizerView(View):
    """Free public tool: paste content, get AI Citation Readiness score + fixes."""

    template_name = "aeo/content_optimizer.html"

    def get(self, request, *args, **kwargs):
        return render(
            request,
            self.template_name,
            {
                "report": None,
                "submitted_content": "",
                "target_query": "",
                "url": "",
                "page_title": "AI Content Optimizer — Free Citation Readiness Score | VRT SPACE AGENCY",
                "meta_description": "Free tool: paste any content and get an instant AI Citation Readiness Score with actionable fixes for ChatGPT, Gemini, and Perplexity.",
                "canonical_url": request.build_absolute_uri(request.path),
                "shell_theme": "shell-light",
            },
        )

    def post(self, request, *args, **kwargs):
        from .content_optimizer import optimize_content

        content = (request.POST.get("content") or "").strip()
        target_query = (request.POST.get("target_query") or "").strip()
        url = (request.POST.get("url") or "").strip()

        if not content:
            messages.error(request, "Paste some content to analyse.")
            return redirect("aeo:content-optimizer")

        if len(content) > 200_000:
            content = content[:200_000]
            messages.info(request, "Content was truncated to 200,000 characters for analysis.")

        report = optimize_content(content=content, target_query=target_query, url=url)
        return render(
            request,
            self.template_name,
            {
                "report": report,
                "submitted_content": content[:6000],
                "target_query": target_query,
                "url": url,
                "page_title": f"AI Citation Readiness: {report.get('composite_score', 0)}/100 | VRT SPACE AGENCY",
                "meta_description": "Your content's AI Citation Readiness Score with prioritized fixes for ChatGPT, Gemini, and Perplexity.",
                "canonical_url": request.build_absolute_uri(request.path),
                "shell_theme": "shell-light",
            },
        )


class WorkspaceShareOfVoiceView(LoginRequiredMixin, View):
    """Cross-prompt competitor share-of-voice dashboard."""

    template_name = "aeo/share_of_voice.html"

    def get(self, request, *args, **kwargs):
        project = get_workspace_content_project(user=request.user, request=request)
        if not project:
            return redirect("tools:workspace-dashboard")
        days = int(request.GET.get("days") or 30)
        days = max(7, min(days, 180))
        sov = compute_share_of_voice(project, days=days)
        return render(
            request,
            self.template_name,
            {
                "project": project,
                "workspace_projects": get_workspace_projects(request.user),
                "share_of_voice": sov,
                "window_options": [7, 30, 60, 90],
                "selected_window": days,
                "page_title": f"AI Share of Voice — {project.name} | VRT SPACE AGENCY",
                "meta_description": "See where your brand wins or loses against competitors in AI-driven answers.",
                "meta_robots": "noindex, nofollow",
                "shell_theme": "shell-light",
            },
        )


class WeeklyDigestPreviewView(LoginRequiredMixin, View):
    """Render the weekly digest email in the browser for previewing.

    Access rules:
    - Staff users: can preview any project by pk.
    - Regular users: only their own projects.

    URL: /workspace/preview/weekly-digest/<pk>/
    """

    template_name = "emails/weekly_digest.html"

    def get(self, request, pk, *args, **kwargs):
        from apps.aeo.digest_service import build_weekly_digest
        from apps.leads.models import ClientProject as _ClientProject

        if request.user.is_staff:
            project = get_object_or_404(_ClientProject, pk=pk)
        else:
            project = get_object_or_404(_ClientProject, pk=pk, owner=request.user)

        payload = build_weekly_digest(project)
        # Add the URLs the email template normally gets from the management command
        try:
            dashboard_path = reverse("tools:workspace-dashboard")
        except Exception:
            dashboard_path = "/workspace/"
        payload["dashboard_url"] = request.build_absolute_uri(dashboard_path)
        payload["unsubscribe_url"] = ""
        return render(request, self.template_name, payload)


class WeeklyDigestPreviewIndexView(LoginRequiredMixin, View):
    """List all projects the current user can preview a digest for."""

    template_name = "emails/digest_preview_index.html"

    def get(self, request, *args, **kwargs):
        from apps.leads.models import ClientProject as _ClientProject

        if request.user.is_staff:
            projects = _ClientProject.objects.all().select_related("owner")
        else:
            projects = _ClientProject.objects.filter(owner=request.user)
        return render(
            request,
            self.template_name,
            {
                "projects": projects,
                "page_title": "Weekly Digest Preview — VRT SPACE AGENCY",
                "meta_robots": "noindex, nofollow",
                "shell_theme": "shell-light",
            },
        )
