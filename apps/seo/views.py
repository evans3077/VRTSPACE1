import json

from django.contrib import messages
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.dateparse import parse_date
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView

from apps.leads.billing import (
    BillingError,
    build_action_access_context,
    build_credit_action_guide,
    can_access_workspace_feature,
    estimate_credit_cost,
    get_total_credit_balance_summary,
    record_usage,
    spend_action_credits,
)
from apps.leads.services import get_workspace_projects, resolve_workspace_project
from apps.leads.models import ClientProject, UsageRecord
from apps.tools.audit_exports import build_absolute_app_url

from .backlinks import refresh_project_backlink_intelligence
from .forms import SEOProjectProfileForm
from .models import BacklinkProspect, SEOCampaign, SEOCompetitor, SEOProjectProfile, SEOShareLink
from .jobs import enqueue_project_seo_refresh
from .pdf_reports import build_seo_report_pdf
from .reporting import build_seo_export_payload, build_seo_share_urls, get_or_create_seo_share_link, get_seo_reporting_bundle
from .services import infer_business_type_for_project
from .services import (
    build_campaign_value_summary,
    build_campaign_workspace_items,
    build_competitor_trend_summary,
    build_discovery_workspace_sections,
    build_serp_evidence_history,
    can_generate_seo_snapshot,
    refresh_project_seo_intelligence,
    sync_project_campaign_chain,
    sync_project_seo_campaigns,
    sync_project_competitors,
)


class WorkspaceSEOView(LoginRequiredMixin, View):
    template_name = "seo/workspace_seo.html"

    def get(self, request, *args, **kwargs):
        project = self._get_project(request.user)
        profile = getattr(project, "seo_profile", None) if project else None
        form = SEOProjectProfileForm(instance=profile, initial=self._initial_form_data(project, profile))
        snapshot = self._get_latest_snapshot(project, profile)
        opportunity_snapshot = self._get_latest_opportunity_snapshot(project, profile)
        backlink_snapshot = self._get_latest_backlink_snapshot(project, profile)
        return render(
            request,
            self.template_name,
            self._build_context(
                project=project,
                form=form,
                profile=profile,
                snapshot=snapshot,
                opportunity_snapshot=opportunity_snapshot,
                backlink_snapshot=backlink_snapshot,
            ),
        )

    def post(self, request, *args, **kwargs):
        project = self._get_project(request.user)
        if not project:
            messages.error(request, "No workspace project is attached to this account yet.")
            return redirect(f"{reverse('tools:workspace-dashboard')}#new-project")
        seo_allowed, _ = can_access_workspace_feature(request.user, "seo_workspace_enabled")
        if not seo_allowed:
            messages.error(request, "SEO workspace access requires a plan that includes SEO credits.")
            return redirect("tools:workspace-dashboard")

        profile = getattr(project, "seo_profile", None)
        form = SEOProjectProfileForm(request.POST, instance=profile)
        if not form.is_valid():
            snapshot = self._get_latest_snapshot(project, profile)
            opportunity_snapshot = self._get_latest_opportunity_snapshot(project, profile)
            backlink_snapshot = self._get_latest_backlink_snapshot(project, profile)
            return render(
                request,
                self.template_name,
                self._build_context(
                    project=project,
                    form=form,
                    profile=profile,
                    snapshot=snapshot,
                    opportunity_snapshot=opportunity_snapshot,
                    backlink_snapshot=backlink_snapshot,
                ),
                status=400,
            )

        profile = form.save(commit=False)
        profile.project = project
        inferred_business_type = infer_business_type_for_project(
            project,
            audit_run=project.latest_audit_run,
            primary_service=form.cleaned_data.get("primary_service", ""),
        )
        metadata = dict(profile.metadata or {})
        metadata["inferred_business_type"] = inferred_business_type
        metadata["business_type_source"] = "manual" if form.cleaned_data.get("business_type") else "inferred"
        profile.metadata = metadata
        if not form.cleaned_data.get("business_type"):
            profile.business_type = inferred_business_type
        profile.save()
        sync_project_competitors(project, form.cleaned_data.get("competitor_urls", ""))
        balance_before = get_total_credit_balance_summary(request.user)
        try:
            _entry, estimate = spend_action_credits(
                request.user,
                "seo",
                project=project,
                note="SEO intelligence refresh",
                reference_key=f"seo-refresh:{project.pk}:{timezone.now().date().isoformat()}",
            )
        except BillingError as exc:
            messages.error(request, str(exc))
            return redirect("seo:workspace-seo")
        backlink_action = build_action_access_context(
            request.user,
            "backlink",
            project=project,
            feature_name="backlink_workspace_enabled",
            label="Backlink intelligence",
        )
        backlink_estimate = estimate_credit_cost("backlink", project=project)
        run_backlink_refresh = True
        backlink_cost_estimate = 0
        backlink_message = ""
        if settings.AUDIT_TIER_ENFORCEMENT:
            run_backlink_refresh = False
            if backlink_action["feature_allowed"]:
                enough_for_combined_run = balance_before["unlimited"] or (
                    (balance_before["remaining"] or 0) >= estimate["amount"] + backlink_estimate["amount"]
                )
                if enough_for_combined_run:
                    try:
                        _backlink_entry, backlink_spend = spend_action_credits(
                            request.user,
                            "backlink",
                            project=project,
                            note="Backlink intelligence refresh",
                            reference_key=f"backlink-refresh:{project.pk}:{timezone.now().isoformat()}",
                            metadata={"paired_with": "seo-refresh"},
                        )
                        backlink_cost_estimate = backlink_spend["amount"]
                        run_backlink_refresh = True
                    except BillingError:
                        run_backlink_refresh = False
                        backlink_message = "Backlink discovery was skipped because the current balance cannot cover the backlink stage after the SEO refresh."
                else:
                    backlink_message = (
                        f"Backlink discovery was skipped because this refresh needs "
                        f"{backlink_estimate['amount']} extra workspace credits after the SEO run."
                    )
            else:
                backlink_message = backlink_action["next_unlock_message"] or backlink_action["blocked_message"]
        metadata = dict(profile.metadata or {})
        metadata["backlink_refresh_requested"] = run_backlink_refresh
        if run_backlink_refresh:
            metadata["backlink_refresh_status"] = "queued" if settings.SEO_REFRESH_ASYNC else "running"
            metadata["backlink_refresh_error"] = ""
        else:
            metadata["backlink_refresh_status"] = "skipped"
            metadata["backlink_refresh_error"] = backlink_message[:500]
        profile.metadata = metadata
        profile.save(update_fields=["metadata", "updated_at"])
        snapshot = None
        opportunity_snapshot = None
        backlink_snapshot = None
        if settings.SEO_REFRESH_ASYNC:
            metadata = dict(profile.metadata or {})
            metadata["refresh_status"] = "queued"
            metadata["refresh_error"] = ""
            profile.metadata = metadata
            profile.save(update_fields=["metadata", "updated_at"])
            enqueue_project_seo_refresh(project.pk)
            success_message = (
                f"SEO refresh queued. This run uses {estimate['amount']} credits and reuses your latest audit instead of requiring a new crawl."
            )
            if backlink_cost_estimate:
                success_message += f" Backlink discovery is queued too and uses {backlink_cost_estimate} credits."
            messages.success(request, success_message)
            if backlink_message:
                messages.info(request, backlink_message)
            return redirect("seo:workspace-seo")
        else:
            snapshot, opportunity_snapshot = refresh_project_seo_intelligence(project)
            if run_backlink_refresh:
                backlink_snapshot = refresh_project_backlink_intelligence(
                    project,
                    context_snapshot=snapshot,
                    opportunity_snapshot=opportunity_snapshot,
                )
                metadata = dict(profile.metadata or {})
                metadata["backlink_refresh_status"] = "completed"
                metadata["backlink_refresh_error"] = ""
                profile.metadata = metadata
                profile.save(update_fields=["metadata", "updated_at"])
            success_message = (
                f"SEO context saved and refreshed. This run used {estimate['amount']} credits from the workspace balance."
            )
            if backlink_cost_estimate:
                success_message += f" Backlink discovery used {backlink_cost_estimate} additional credits."
            messages.success(request, success_message)
            if backlink_message:
                messages.info(request, backlink_message)
        return render(
            request,
            self.template_name,
            self._build_context(
                project=project,
                form=SEOProjectProfileForm(instance=profile, initial=self._initial_form_data(project, profile)),
                profile=profile,
                snapshot=snapshot,
                opportunity_snapshot=opportunity_snapshot,
                backlink_snapshot=backlink_snapshot,
            ),
        )

    def _get_project(self, user):
        selected_project = resolve_workspace_project(self.request, user)
        if not selected_project:
            return None
        return (
            ClientProject.objects.select_related("latest_audit_run", "seo_profile")
            .filter(pk=selected_project.pk)
            .first()
        )

    def _get_latest_snapshot(self, project, profile):
        if not profile or not can_generate_seo_snapshot(project):
            return None
        return (
            project.seo_snapshots.filter(profile=profile, source_audit_run=project.latest_audit_run)
            .order_by("-created_at")
            .first()
        )

    def _initial_form_data(self, project, profile=None):
        if not project:
            return {}

        competitor_urls = [
            competitor.homepage_url
            for competitor in project.seo_competitors.filter(
                is_active=True,
                source=SEOCompetitor.Source.PROFILE,
            ).order_by("homepage_url")
        ]
        if not competitor_urls and getattr(project, "audit_request", None):
            competitor_urls = getattr(project.audit_request, "competitor_urls", [])

        # Attempt to pull intelligence from latest audit if available
        intel = (profile.metadata or {}).get("intelligence", {}) if profile else {}
        
        initial = {
            "competitor_urls": "\n".join(competitor_urls),
            "location": getattr(project, "location", "") or intel.get("location", ""),
            "target_goal": getattr(project, "target_goal", ""),
            "primary_service": getattr(project, "primary_service", "") or intel.get("query", ""),
            "target_audience": getattr(project, "target_audience", ""),
        }
        if not getattr(profile, "business_type", ""):
            initial["business_type"] = getattr(project, "business_type", "") or infer_business_type_for_project(project)
        return initial

    def _get_latest_opportunity_snapshot(self, project, profile):
        if not profile or not can_generate_seo_snapshot(project):
            return None
        return (
            project.seo_opportunity_snapshots.filter(
                profile=profile,
                source_audit_run=project.latest_audit_run,
            )
            .order_by("-created_at")
            .first()
        )

    def _get_latest_backlink_snapshot(self, project, profile):
        if not profile or not can_generate_seo_snapshot(project):
            return None
        return (
            project.backlink_snapshots.filter(
                profile=profile,
                source_audit_run=project.latest_audit_run,
            )
            .order_by("-created_at")
            .first()
        )

    def _build_context(self, *, project, form, profile, snapshot, opportunity_snapshot, backlink_snapshot):
        payload = snapshot.output_json if snapshot else {}
        opportunity_payload = opportunity_snapshot.output_json if opportunity_snapshot else {}
        backlink_payload = backlink_snapshot.output_json if backlink_snapshot else {}
        refresh_state = (getattr(profile, "metadata", None) or {}) if profile else {}
        campaign_items = (
            build_campaign_workspace_items(
                project,
                campaigns=sync_project_campaign_chain(project),
            )
            if project and opportunity_snapshot
            else []
        )
        return {
            "project": project,
            "workspace_projects": get_workspace_projects(self.request.user),
            "form": form,
            "profile": profile,
            "snapshot": snapshot,
            "opportunity_snapshot": opportunity_snapshot,
            "seo_context": payload.get("context", {}),
            "seo_keyword_clusters": payload.get("keyword_clusters", {}),
            "seo_recommendations": payload.get("recommendations", []),
            "seo_audit_snapshot": payload.get("audit_snapshot", {}),
            "seo_site_structure": payload.get("site_structure", {}),
            "seo_benchmark_summary": payload.get("benchmark_summary", {}),
            "seo_discovery": payload.get("discovery", {}),
            "seo_discovery_sections": build_discovery_workspace_sections(payload.get("discovery", {})),
            "seo_competitors": payload.get("competitors", []),
            "seo_competitor_trace": payload.get("competitor_trace", []),
            "seo_competitor_patterns": payload.get("competitor_patterns", []),
            "seo_page_comparisons": payload.get("page_comparisons", []),
            "seo_serp_history": build_serp_evidence_history(project) if project else [],
            "seo_competitor_trends": build_competitor_trend_summary(project) if project else [],
            "seo_campaigns": campaign_items,
            "seo_chain_value_summary": build_campaign_value_summary(project, campaign_items=campaign_items) if project else {},
            "workspace_credit_actions": build_credit_action_guide(project, self.request.user) if project else [],
            "seo_export_action": build_action_access_context(
                self.request.user,
                "export",
                project=project,
                feature_name="export_reports_enabled",
                label="SEO exports",
            ) if project else {},
            "seo_share_action": build_action_access_context(
                self.request.user,
                "share",
                project=project,
                feature_name="stakeholder_sharing_enabled",
                label="SEO stakeholder sharing",
            ) if project else {},
            "backlink_action": build_action_access_context(
                self.request.user,
                "backlink",
                project=project,
                feature_name="backlink_workspace_enabled",
                label="Backlink intelligence",
            ) if project else {},
            "seo_campaign_status_choices": SEOCampaign.Status.choices,
            "seo_value_summary": opportunity_payload.get("value_summary", {}),
            "seo_keyword_opportunities": opportunity_payload.get("keyword_opportunities", []),
            "seo_page_map": opportunity_payload.get("page_map", []),
            "seo_execution_queue": opportunity_payload.get("execution_queue", []),
            "backlink_snapshot": backlink_snapshot,
            "backlink_summary": backlink_payload.get("summary", {}),
            "backlink_linkable_assets": backlink_payload.get("linkable_assets", []),
            "backlink_errors": backlink_payload.get("errors", []),
            "backlink_prospects": list(project.backlink_prospects.order_by("-total_score", "-updated_at")[:20]) if project else [],
            "backlink_status_choices": BacklinkProspect.Status.choices,
            "can_generate_snapshot": can_generate_seo_snapshot(project),
            "seo_refresh_state": refresh_state,
            "latest_seo_share_link": self._get_latest_share_link(project, campaign_items=campaign_items),
            "latest_seo_share_url": self._get_latest_share_url(project, campaign_items=campaign_items),
            "page_title": f"{project.name if project else 'Workspace'} SEO Workspace | VRT SPACE AGENCY",
            "meta_description": "Private SEO workspace for competitor-backed benchmark decisions, campaign execution, and stakeholder reporting.",
            "canonical_url": self.request.build_absolute_uri(self.request.path),
            "meta_robots": "noindex, nofollow",
            "og_title": f"{project.name if project else 'Workspace'} SEO Workspace",
            "og_description": "Private SEO workspace for benchmarked competitor intelligence and execution planning.",
            "og_type": "website",
            "twitter_card": "summary",
            "shell_theme": "shell-light",
            "schema_json": json.dumps(
                {
                    "@context": "https://schema.org",
                    "@type": "WebPage",
                    "name": f"{project.name if project else 'Workspace'} SEO Workspace",
                    "description": "Private SEO workspace for competitor-backed benchmark decisions and execution planning.",
                }
            ),
        }

    def _get_latest_share_link(self, project, *, campaign_items=None):
        if not project:
            return None
        bundle = get_seo_reporting_bundle(project)
        context_snapshot = bundle.get("context_snapshot")
        opportunity_snapshot = bundle.get("opportunity_snapshot")
        backlink_snapshot = bundle.get("backlink_snapshot")
        if not context_snapshot or not opportunity_snapshot:
            return None
        return (
            SEOShareLink.objects.filter(
                project=project,
                source_context_snapshot=context_snapshot,
                source_opportunity_snapshot=opportunity_snapshot,
                source_backlink_snapshot=backlink_snapshot,
            )
            .order_by("-created_at")
            .first()
        )

    def _get_latest_share_url(self, project, *, campaign_items=None):
        share_link = self._get_latest_share_link(project, campaign_items=campaign_items)
        if not share_link:
            return ""
        return build_seo_share_urls(share_link)["share_url"]


class WorkspaceBacklinkProspectUpdateView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        project = resolve_workspace_project(request, request.user)
        if not project:
            raise Http404
        prospect = project.backlink_prospects.filter(pk=kwargs["pk"]).first()
        if not prospect:
            raise Http404

        status = request.POST.get("status", "").strip()
        anchor_text = request.POST.get("suggested_anchor_text", "").strip()
        notes = request.POST.get("notes", "").strip()
        if status in BacklinkProspect.Status.values:
            prospect.status = status
        prospect.suggested_anchor_text = anchor_text[:255]
        metadata = dict(prospect.metadata or {})
        metadata["notes"] = notes[:1000]
        prospect.metadata = metadata
        prospect.save(update_fields=["status", "suggested_anchor_text", "metadata", "updated_at"])
        messages.success(request, "Backlink prospect updated.")
        return redirect("seo:workspace-seo")


class WorkspaceSEOCompetitorReviewView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        project = resolve_workspace_project(request, request.user)
        if not project:
            raise Http404
        competitor = project.seo_competitors.filter(pk=kwargs["pk"]).first()
        if not competitor:
            raise Http404

        decision = request.POST.get("decision", "auto").strip().lower()
        note = request.POST.get("note", "").strip()
        if decision not in {"auto", "approved", "pinned", "suppressed", "rejected"}:
            messages.error(request, "Invalid competitor review decision.")
            return redirect("seo:workspace-seo")

        metadata = dict(competitor.metadata or {})
        if decision == "auto" and not note:
            metadata.pop("review", None)
        else:
            metadata["review"] = {
                "decision": decision,
                "note": note[:500],
            }
        competitor.metadata = metadata
        competitor.save(update_fields=["metadata", "updated_at"])
        messages.success(request, "Competitor review updated.")
        return redirect("seo:workspace-seo")


class WorkspaceSEOCampaignUpdateView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        project = resolve_workspace_project(request, request.user)
        if not project:
            raise Http404
        campaign = project.seo_campaigns.filter(pk=kwargs["pk"]).first()
        if not campaign:
            raise Http404

        status = request.POST.get("status", "").strip()
        previous_status = campaign.status
        if status in SEOCampaign.Status.values:
            campaign.status = status
        due_date = request.POST.get("due_date", "").strip()
        campaign.due_date = parse_date(due_date) if due_date else None
        if request.POST.get("assign_to_me") == "1":
            campaign.owner = request.user
        note = request.POST.get("note", "").strip()
        metadata = dict(campaign.metadata or {})
        metadata["note"] = note[:500]
        if campaign.status == SEOCampaign.Status.COMPLETED and previous_status != SEOCampaign.Status.COMPLETED:
            metadata["completed_at"] = timezone.now().isoformat()
        elif campaign.status != SEOCampaign.Status.COMPLETED:
            metadata.pop("completed_at", None)
        campaign.metadata = metadata
        campaign.save(update_fields=["status", "due_date", "owner", "metadata", "updated_at"])
        messages.success(request, "Campaign updated.")
        return redirect("seo:workspace-seo")


class WorkspaceSEOExportJsonView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        project = resolve_workspace_project(request, request.user)
        if not project:
            raise Http404
        action = build_action_access_context(
            request.user,
            "export",
            project=project,
            feature_name="export_reports_enabled",
            label="SEO exports",
        )
        if settings.AUDIT_TIER_ENFORCEMENT and not action["available"]:
            return JsonResponse({"error": action["blocked_message"] or action["next_unlock_message"]}, status=403)
        bundle = get_seo_reporting_bundle(project)
        if not bundle.get("context_snapshot") or not bundle.get("opportunity_snapshot"):
            return JsonResponse({"error": "Run the SEO workspace first to generate a reportable snapshot."}, status=409)
        try:
            _entry, estimate = spend_action_credits(
                request.user,
                "export",
                project=project,
                note="SEO JSON export",
                reference_key=f"seo-export-json:{project.pk}:{bundle['context_snapshot'].pk}:{bundle['opportunity_snapshot'].pk}",
                metadata={"project_id": project.pk, "format": "json"},
                reuse_reference=True,
            )
            if not estimate.get("reused_existing_charge"):
                record_usage(request.user, UsageRecord.Metric.EXPORT)
        except BillingError as exc:
            return JsonResponse({"error": str(exc)}, status=403)
        return JsonResponse(build_seo_export_payload(project, bundle=bundle), status=200)


class WorkspaceSEOReportPdfView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        project = resolve_workspace_project(request, request.user)
        if not project:
            raise Http404
        action = build_action_access_context(
            request.user,
            "export",
            project=project,
            feature_name="export_reports_enabled",
            label="SEO exports",
        )
        if settings.AUDIT_TIER_ENFORCEMENT and not action["available"]:
            return HttpResponse(action["blocked_message"] or action["next_unlock_message"], status=403)
        bundle = get_seo_reporting_bundle(project)
        if not bundle.get("context_snapshot") or not bundle.get("opportunity_snapshot"):
            return HttpResponse("Run the SEO workspace first to generate a reportable snapshot.", status=409)
        try:
            _entry, estimate = spend_action_credits(
                request.user,
                "export",
                project=project,
                note="SEO PDF export",
                reference_key=f"seo-export-pdf:{project.pk}:{bundle['context_snapshot'].pk}:{bundle['opportunity_snapshot'].pk}",
                metadata={"project_id": project.pk, "format": "pdf"},
                reuse_reference=True,
            )
            if not estimate.get("reused_existing_charge"):
                record_usage(request.user, UsageRecord.Metric.EXPORT)
        except BillingError as exc:
            return HttpResponse(str(exc), status=403)
        pdf_bytes = build_seo_report_pdf(build_seo_export_payload(project, bundle=bundle))
        disposition = "attachment" if request.GET.get("download") == "1" else "inline"
        filename = f"seo-report-{project.normalized_domain or project.pk}.pdf"
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'{disposition}; filename="{filename}"'
        return response


class WorkspaceSEOShareCreateView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        project = resolve_workspace_project(request, request.user)
        if not project:
            raise Http404
        action = build_action_access_context(
            request.user,
            "share",
            project=project,
            feature_name="stakeholder_sharing_enabled",
            label="SEO stakeholder sharing",
        )
        if settings.AUDIT_TIER_ENFORCEMENT and not action["available"]:
            messages.error(request, action["blocked_message"] or action["next_unlock_message"])
            return redirect("seo:workspace-seo")
        bundle = get_seo_reporting_bundle(project)
        if not bundle.get("context_snapshot") or not bundle.get("opportunity_snapshot"):
            messages.error(request, "Run the SEO workspace first to generate a shareable report.")
            return redirect("seo:workspace-seo")
        try:
            spend_action_credits(
                request.user,
                "share",
                project=project,
                note="SEO stakeholder share link",
                reference_key=f"seo-share:{project.pk}:{bundle['context_snapshot'].pk}:{bundle['opportunity_snapshot'].pk}",
                metadata={"project_id": project.pk},
                reuse_reference=True,
            )
        except BillingError as exc:
            messages.error(request, str(exc))
            return redirect("seo:workspace-seo")
        share_link = get_or_create_seo_share_link(project, bundle=bundle, created_by=request.user)
        payload = build_seo_share_urls(share_link)
        request.session["latest_seo_share_url"] = payload["share_url"]
        messages.success(request, "SEO stakeholder report link created.")
        return redirect("seo:workspace-seo")


class SharedSEOReportView(DetailView):
    model = SEOShareLink
    slug_field = "token"
    slug_url_kwarg = "token"
    template_name = "seo/shared_seo_report.html"
    context_object_name = "share_link"

    def get_queryset(self):
        return SEOShareLink.objects.select_related(
            "project",
            "profile",
            "source_context_snapshot",
            "source_opportunity_snapshot",
            "source_backlink_snapshot",
        )

    def get_object(self, queryset=None):
        share_link = super().get_object(queryset=queryset)
        if share_link.expires_at and share_link.expires_at <= timezone.now():
            raise Http404
        share_link.access_count += 1
        share_link.last_accessed_at = timezone.now()
        share_link.save(update_fields=["access_count", "last_accessed_at", "updated_at"])
        return share_link

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        share_link = self.object
        bundle = get_seo_reporting_bundle(
            share_link.project,
            profile=share_link.profile,
            context_snapshot=share_link.source_context_snapshot,
            opportunity_snapshot=share_link.source_opportunity_snapshot,
            backlink_snapshot=share_link.source_backlink_snapshot,
        )
        payload = build_seo_export_payload(share_link.project, bundle=bundle)
        canonical_url = self.request.build_absolute_uri(
            reverse("seo:shared-seo-report", args=[share_link.token])
        )
        context.update(
            {
                "report_payload": payload,
                "project": share_link.project,
                "shell_theme": "shell-light",
                "canonical_url": canonical_url,
                "page_title": f"{share_link.project.name} SEO Strategy Report | VRT SPACE AGENCY",
                "meta_description": f"Stakeholder SEO strategy report for {share_link.project.normalized_domain} with benchmark evidence, execution priorities, and campaign progress.",
                "meta_robots": "noindex, nofollow",
                "og_title": f"{share_link.project.name} SEO Strategy Report",
                "og_description": f"Stakeholder SEO strategy report for {share_link.project.normalized_domain}.",
                "og_type": "article",
                "twitter_card": "summary",
                "schema_json": json.dumps(
                    {
                        "@context": "https://schema.org",
                        "@type": "Report",
                        "name": f"{share_link.project.name} SEO Strategy Report",
                        "description": f"Stakeholder SEO strategy report for {share_link.project.normalized_domain}.",
                        "url": canonical_url,
                    }
                ),
            }
        )
        return context


class SharedSEOReportPdfView(DetailView):
    model = SEOShareLink
    slug_field = "token"
    slug_url_kwarg = "token"

    def get_queryset(self):
        return SEOShareLink.objects.select_related(
            "project",
            "profile",
            "source_context_snapshot",
            "source_opportunity_snapshot",
            "source_backlink_snapshot",
        )

    def get(self, request, *args, **kwargs):
        share_link = self.get_object()
        if share_link.expires_at and share_link.expires_at <= timezone.now():
            raise Http404
        bundle = get_seo_reporting_bundle(
            share_link.project,
            profile=share_link.profile,
            context_snapshot=share_link.source_context_snapshot,
            opportunity_snapshot=share_link.source_opportunity_snapshot,
            backlink_snapshot=share_link.source_backlink_snapshot,
        )
        pdf_bytes = build_seo_report_pdf(build_seo_export_payload(share_link.project, bundle=bundle))
        disposition = "attachment" if request.GET.get("download") == "1" else "inline"
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'{disposition}; filename="shared-seo-report-{share_link.project.pk}.pdf"'
        return response
