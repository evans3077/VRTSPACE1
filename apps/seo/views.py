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
from .models import BacklinkProspect, SEOCampaign, SEOCampaignEditItem, SEOCompetitor, SEOProjectProfile, SEOShareLink
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
    get_action_pack_for_campaign,
    refresh_project_seo_intelligence,
    sync_campaign_edit_items,
    sync_project_campaign_chain,
    sync_project_seo_campaigns,
    sync_project_competitors,
)
from .dataforseo_api import DataForSeoClient
from apps.aeo.geo_api import GeoApiClient



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
        
        # Clinical Precision: read persisted results from profile metadata
        # (populated by WorkspaceGEOShootoutView and WorkspaceClinicalDataView).
        # Fall back to lightweight mock structure so the template never crashes.
        profile_meta = (getattr(profile, "metadata", None) or {}) if profile else {}

        geo_shootout = profile_meta.get("geo_shootout") or {}
        clinical_stored = profile_meta.get("clinical_data") or {}
        clinical_search_volume = clinical_stored.get("search_volume") or {}
        clinical_backlinks = clinical_stored.get("backlinks") or {}
        entity_confidence = profile_meta.get("entity_confidence") or {}

        # If no stored results yet, show a minimal placeholder so the template
        # section still renders (enabling the "Run Shootout" CTA to appear).
        if not geo_shootout and project:
            keywords = [getattr(project, "primary_service", "SEO") or "SEO Services"]
            geo_shootout = {"query": keywords[0], "is_placeholder": True}

        if not clinical_search_volume and project:
            clinical_search_volume = {}

        # ── AEO mini-summary for the SEO hub callout ────────────────────────
        aeo_summary = None
        if project and getattr(project, "pk", None):
            from apps.aeo.models import AEOAudit, TrackedPrompt, PromptCheckRun
            from django.utils import timezone as _tz
            from datetime import timedelta as _td

            latest_aeo = AEOAudit.objects.filter(project=project).order_by("-created_at").first()
            prompt_count = TrackedPrompt.objects.filter(project=project, is_active=True).count()
            recent_runs = PromptCheckRun.objects.filter(
                prompt__project=project,
                created_at__gte=_tz.now() - _td(days=30),
            )
            recent_total = recent_runs.count()
            recent_cited = recent_runs.filter(target_cited=True).count()
            cited_pct = round(100 * recent_cited / recent_total) if recent_total else 0

            aeo_summary = {
                "has_data": prompt_count > 0,
                "score": latest_aeo.overall_score if latest_aeo else 0,
                "prompt_count": prompt_count,
                "cited_pct": cited_pct,
                "recent_checks": recent_total,
            }

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
            "geo_action": build_action_access_context(
                self.request.user,
                "geo_shootout",
                project=project,
                feature_name="clinical_intelligence_enabled",
                label="GEO Shootout",
            ) if project else {},
            "clinical_action": build_action_access_context(
                self.request.user,
                "clinical_data",
                project=project,
                feature_name="clinical_intelligence_enabled",
                label="Clinical Market Data",
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
            "clinical_search_volume": clinical_search_volume,
            "clinical_backlinks": clinical_backlinks,
            "geo_shootout": geo_shootout,
            "aeo_summary": aeo_summary,
            "entity_confidence": entity_confidence,
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


class WorkspaceSEOPromoteToPromptView(LoginRequiredMixin, View):
    """Promote an SEO/GEO query into a TrackedPrompt with one click.

    Bridges the gap between one-off SEO/GEO analysis and continuous AEO
    monitoring. Used by the GEO Shootout card on the SEO hub.
    """

    def post(self, request, *args, **kwargs):
        from apps.aeo.models import TrackedPrompt
        from apps.aeo.prompt_service import run_prompt_check

        project = resolve_workspace_project(request, request.user)
        if not project or not getattr(project, "pk", None):
            messages.error(request, "Create a workspace project first.")
            return redirect("seo:workspace-seo")

        query = (request.POST.get("query") or "").strip()
        if not query:
            messages.error(request, "No query provided.")
            return redirect("seo:workspace-seo")

        if len(query) > 300:
            query = query[:300]

        prompt, created = TrackedPrompt.objects.get_or_create(
            project=project,
            prompt=query,
            defaults={
                "intent": TrackedPrompt.Intent.INFORMATIONAL,
                "is_active": True,
            },
        )
        if created:
            try:
                run_prompt_check(prompt)
            except Exception:  # pragma: no cover - simulator is offline-safe
                pass
            messages.success(
                request,
                f"Tracking '{query[:60]}' across ChatGPT, Gemini and Perplexity.",
            )
        else:
            messages.info(request, "Already tracking this prompt.")

        return redirect("aeo:workspace-prompts")


class SEOCampaignActionPackView(LoginRequiredMixin, View):
    """
    Action pack detail view for a single SEO campaign.
    GET  → renders the full implementation pack (edit targets, evidence cards, success criteria).
    POST → toggles the status of one SEOCampaignEditItem.
    """

    template_name = "seo/action_pack_detail.html"

    def _get_campaign(self, request, pk):
        project = resolve_workspace_project(request, request.user)
        if not project:
            raise Http404
        campaign = project.seo_campaigns.select_related("project", "source_opportunity_snapshot").filter(pk=pk).first()
        if not campaign:
            raise Http404
        return project, campaign

    def get(self, request, *args, **kwargs):
        project, campaign = self._get_campaign(request, kwargs["pk"])
        edit_items = get_action_pack_for_campaign(campaign)
        metadata = campaign.metadata or {}
        return render(request, self.template_name, {
            "project": project,
            "campaign": campaign,
            "edit_items": edit_items,
            "total_items": len(edit_items),
            "completed_items": sum(1 for i in edit_items if i.status == SEOCampaignEditItem.Status.COMPLETED),
            "action_steps": metadata.get("action_steps", []),
            "why_now": metadata.get("why_now", ""),
            "deliverable": metadata.get("deliverable", ""),
            "competitor_evidence": metadata.get("competitor_evidence", [])[:6],
            "evidence": metadata.get("evidence", {}),
            "edit_item_status_choices": SEOCampaignEditItem.Status.choices,
            "campaign_status_choices": SEOCampaign.Status.choices,
            "page_title": f"Action Pack — {campaign.title} | VRT SPACE",
            "meta_robots": "noindex, nofollow",
        })

    def post(self, request, *args, **kwargs):
        project, campaign = self._get_campaign(request, kwargs["pk"])

        # Toggle an individual edit item status
        item_pk = request.POST.get("item_pk")
        new_status = request.POST.get("item_status", "").strip()
        if item_pk and new_status in SEOCampaignEditItem.Status.values:
            item = campaign.edit_items.filter(pk=item_pk).first()
            if item:
                item.status = new_status
                if new_status == SEOCampaignEditItem.Status.COMPLETED:
                    item.completed_at = timezone.now()
                elif item.completed_at:
                    item.completed_at = None
                item.save(update_fields=["status", "completed_at", "updated_at"])
                messages.success(request, "Edit item updated.")
            return redirect("seo:campaign-action-pack", pk=campaign.pk)

        # Update campaign-level status from the action pack page
        campaign_status = request.POST.get("campaign_status", "").strip()
        if campaign_status in SEOCampaign.Status.values:
            campaign.status = campaign_status
            if campaign_status == SEOCampaign.Status.COMPLETED:
                meta = dict(campaign.metadata or {})
                meta["completed_at"] = timezone.now().isoformat()
                campaign.metadata = meta
            campaign.save(update_fields=["status", "metadata", "updated_at"])
            messages.success(request, "Campaign status updated.")
        return redirect("seo:campaign-action-pack", pk=campaign.pk)


# ---------------------------------------------------------------------------
# Phase 12: Clinical Intelligence Action Views
# ---------------------------------------------------------------------------

class WorkspaceGEOShootoutView(LoginRequiredMixin, View):
    """
    POST — Triggers a live GEO Shootout against Perplexity Sonar Pro.

    Checks clinical_intelligence_enabled, spends 5 credits, calls GeoApiClient,
    persists the result to SEOProjectProfile.metadata["geo_shootout"], then
    redirects back to the SEO workspace so the result renders inline.
    """

    def post(self, request, *args, **kwargs):
        project = resolve_workspace_project(request.user)
        if not project:
            messages.error(request, "No active workspace project.")
            return redirect("seo:workspace-seo")

        profile = getattr(project, "seo_profile", None)
        if not profile:
            messages.error(request, "Complete your SEO profile before running a GEO Shootout.")
            return redirect("seo:workspace-seo")

        # Feature gate
        allowed, reason = can_access_workspace_feature(request.user, "clinical_intelligence_enabled")
        if not allowed:
            messages.error(request, f"GEO Shootout requires a plan with Clinical Intelligence enabled. {reason or ''}")
            return redirect("seo:workspace-seo")

        # Credit spend — idempotent within same day via reuse_reference
        reference_key = f"geo_shootout:{project.pk}:{timezone.now().date()}"
        try:
            spend_action_credits(
                request.user,
                "geo_shootout",
                project=project,
                note=f"GEO Shootout for {project.name}",
                reference_key=reference_key,
                reuse_reference=True,
            )
        except BillingError as exc:
            messages.error(request, str(exc))
            return redirect("seo:workspace-seo")

        # Run the shootout
        keywords = [getattr(project, "primary_service", "") or "digital marketing services"]
        competitor_urls = [c.homepage_url for c in project.seo_competitors.filter(is_active=True)[:3]]
        competitor_names = [c.normalized_domain for c in project.seo_competitors.filter(is_active=True)[:3]]
        if not competitor_names:
            competitor_names = ["competitor1.com", "competitor2.com"]

        geo_client = GeoApiClient()
        result = geo_client.run_geo_shootout(
            brand_name=project.name,
            service_query=keywords[0],
            competitors=competitor_names,
        )
        result["query"] = keywords[0]
        result["run_at"] = timezone.now().isoformat()

        # Persist to profile metadata
        metadata = dict(profile.metadata or {})
        metadata["geo_shootout"] = result
        profile.metadata = metadata
        profile.save(update_fields=["metadata", "updated_at"])

        if result.get("brand_cited"):
            messages.success(request, f"GEO Shootout complete — {project.name} was cited by the AI engine.")
        else:
            messages.warning(request, f"GEO Shootout complete — {project.name} was not cited. Check the Authority Gap plan.")
        return redirect(f"{reverse('seo:workspace-seo')}#seo-clinical-intelligence")


class WorkspaceClinicalDataView(LoginRequiredMixin, View):
    """
    POST — Fetches live search volume and backlink data from DataForSEO.

    Checks clinical_intelligence_enabled, spends 4 credits, calls DataForSeoClient,
    persists to SEOProjectProfile.metadata["clinical_data"], redirects back.
    """

    def post(self, request, *args, **kwargs):
        project = resolve_workspace_project(request.user)
        if not project:
            messages.error(request, "No active workspace project.")
            return redirect("seo:workspace-seo")

        profile = getattr(project, "seo_profile", None)
        if not profile:
            messages.error(request, "Complete your SEO profile before fetching market data.")
            return redirect("seo:workspace-seo")

        # Feature gate
        allowed, reason = can_access_workspace_feature(request.user, "clinical_intelligence_enabled")
        if not allowed:
            messages.error(request, f"Clinical Market Data requires a plan with Clinical Intelligence enabled. {reason or ''}")
            return redirect("seo:workspace-seo")

        # Credit spend
        reference_key = f"clinical_data:{project.pk}:{timezone.now().date()}"
        try:
            spend_action_credits(
                request.user,
                "clinical_data",
                project=project,
                note=f"Clinical market data for {project.name}",
                reference_key=reference_key,
                reuse_reference=True,
            )
        except BillingError as exc:
            messages.error(request, str(exc))
            return redirect("seo:workspace-seo")

        # Fetch data
        keywords = [getattr(project, "primary_service", "") or "digital marketing"]
        dfs_client = DataForSeoClient()
        search_volume = dfs_client.get_search_volume(keywords)
        backlinks = dfs_client.get_backlink_profile(project.normalized_domain or "")

        result = {
            "search_volume": search_volume,
            "backlinks": backlinks,
            "run_at": timezone.now().isoformat(),
        }

        # Persist to profile metadata
        metadata = dict(profile.metadata or {})
        metadata["clinical_data"] = result
        profile.metadata = metadata
        profile.save(update_fields=["metadata", "updated_at"])

        messages.success(request, "Clinical market data refreshed.")
        return redirect(f"{reverse('seo:workspace-seo')}#seo-clinical-intelligence")


class WorkspaceEntityConfidenceView(LoginRequiredMixin, View):
    """
    POST — Runs the brand homepage through Google Cloud NLP to score entity recognition.

    Spends from the clinical_data credit category, persists to profile metadata,
    and redirects to the AEO workspace so the result renders inline.
    """

    def post(self, request, *args, **kwargs):
        project = resolve_workspace_project(request.user)
        if not project:
            messages.error(request, "No active workspace project.")
            return redirect("aeo:workspace-aeo")

        profile = getattr(project, "seo_profile", None)

        # Feature gate
        allowed, reason = can_access_workspace_feature(request.user, "clinical_intelligence_enabled")
        if not allowed:
            messages.error(request, f"Entity Confidence Scan requires Clinical Intelligence. {reason or ''}")
            return redirect("aeo:workspace-aeo")

        # Credit spend
        reference_key = f"entity_confidence:{project.pk}:{timezone.now().date()}"
        try:
            spend_action_credits(
                request.user,
                "clinical_data",
                project=project,
                note=f"Entity confidence scan for {project.name}",
                reference_key=reference_key,
                reuse_reference=True,
            )
        except BillingError as exc:
            messages.error(request, str(exc))
            return redirect("aeo:workspace-aeo")

        # Fetch homepage content for analysis
        import requests as _req
        page_content = ""
        homepage_url = getattr(project, "website", "") or ""
        if homepage_url:
            try:
                resp = _req.get(homepage_url, timeout=10, headers={"User-Agent": "VRTSPACEBot/1.0"})
                if resp.ok:
                    from apps.tools.services import parse_page
                    parsed = parse_page(homepage_url, resp)
                    page_content = parsed.get("body_text", "")[:10000]
            except Exception:
                pass

        if not page_content:
            page_content = f"{project.name} is a {getattr(project, 'primary_service', 'business')} based in {getattr(project, 'location', 'the region')}."

        geo_client = GeoApiClient()
        result = geo_client.get_entity_confidence_score(page_content)
        result["run_at"] = timezone.now().isoformat()

        # Persist to SEO profile metadata (accessible from both SEO and AEO views)
        if profile:
            metadata = dict(profile.metadata or {})
            metadata["entity_confidence"] = result
            profile.metadata = metadata
            profile.save(update_fields=["metadata", "updated_at"])

        score = result.get("highest_salience", 0)
        if score >= 70:
            messages.success(request, f"Entity scan complete — entity confidence at {score:.0f}%. Google recognises the brand clearly.")
        elif score >= 40:
            messages.warning(request, f"Entity scan complete — entity confidence at {score:.0f}%. Schema and content improvements recommended.")
        else:
            messages.error(request, f"Entity scan complete — entity confidence at {score:.0f}%. Brand entities are weakly recognised. Action pack generated.")
        return redirect(f"{reverse('aeo:workspace-aeo')}#aeo-entity-confidence")


class WorkspaceIndexingPingView(LoginRequiredMixin, View):
    """
    POST — Pings the Google Indexing API for a specific URL after publish.

    Expects POST param: url (the published page URL).
    Requires GOOGLE_INDEXING_API_KEY in settings / env.
    """

    def post(self, request, *args, **kwargs):
        project = resolve_workspace_project(request.user)
        page_url = request.POST.get("url", "").strip()

        if not page_url:
            messages.error(request, "No URL provided for indexing ping.")
            return redirect("content:workspace-content")

        api_key = getattr(settings, "GOOGLE_INDEXING_API_KEY", "") or ""
        if not api_key:
            messages.warning(
                request,
                "Google Indexing API key not configured. Set GOOGLE_INDEXING_API_KEY in environment variables.",
            )
            return redirect("content:workspace-content")

        import requests as _req
        try:
            resp = _req.post(
                f"https://indexing.googleapis.com/v3/urlNotifications:publish?key={api_key}",
                json={"url": page_url, "type": "URL_UPDATED"},
                timeout=15,
            )
            if resp.ok:
                messages.success(request, f"Google Indexing API pinged for {page_url}. Indexing usually completes within minutes.")
            else:
                messages.warning(
                    request,
                    f"Indexing ping returned {resp.status_code}. Check that the API key has Indexing API access enabled.",
                )
        except Exception as exc:
            messages.error(request, f"Indexing ping failed: {exc}")

        return redirect("content:workspace-content")


# ---------------------------------------------------------------------------
# Phase 12: Google Search Console OAuth Connection
# ---------------------------------------------------------------------------

class WorkspaceGSCConnectView(LoginRequiredMixin, View):
    """
    GET — Starts the Google Search Console OAuth 2.0 flow.

    Requires GOOGLE_GSC_CLIENT_ID, GOOGLE_GSC_CLIENT_SECRET, and
    GOOGLE_GSC_REDIRECT_URI in settings / env.
    """

    SCOPES = [
        "https://www.googleapis.com/auth/webmasters.readonly",
        "openid",
        "email",
    ]
    AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"

    def get(self, request, *args, **kwargs):
        if not settings.GOOGLE_GSC_ENABLED:
            messages.error(
                request,
                "Google Search Console integration is not configured. "
                "Set GOOGLE_GSC_CLIENT_ID and GOOGLE_GSC_CLIENT_SECRET in environment variables.",
            )
            return redirect("seo:workspace-seo")

        import urllib.parse
        import secrets as _secrets

        state = _secrets.token_urlsafe(24)
        request.session["gsc_oauth_state"] = state

        params = {
            "client_id": settings.GOOGLE_GSC_CLIENT_ID,
            "redirect_uri": settings.GOOGLE_GSC_REDIRECT_URI,
            "response_type": "code",
            "scope": " ".join(self.SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
        auth_url = f"{self.AUTH_URL}?{urllib.parse.urlencode(params)}"
        return redirect(auth_url)


class WorkspaceGSCCallbackView(LoginRequiredMixin, View):
    """
    GET — Google redirects here after the user approves GSC access.

    Exchanges the authorisation code for access + refresh tokens and stores
    them in a GSCConnection record linked to the user's active project.
    """

    TOKEN_URL = "https://oauth2.googleapis.com/token"
    USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

    def get(self, request, *args, **kwargs):
        code = request.GET.get("code", "")
        state = request.GET.get("state", "")
        error = request.GET.get("error", "")

        if error:
            messages.error(request, f"Google authorisation was denied: {error}")
            return redirect("seo:workspace-seo")

        if not code or state != request.session.pop("gsc_oauth_state", None):
            messages.error(request, "Invalid OAuth state. Please try connecting again.")
            return redirect("seo:workspace-seo")

        import requests as _req
        # Exchange code for tokens
        try:
            token_resp = _req.post(
                self.TOKEN_URL,
                data={
                    "code": code,
                    "client_id": settings.GOOGLE_GSC_CLIENT_ID,
                    "client_secret": settings.GOOGLE_GSC_CLIENT_SECRET,
                    "redirect_uri": settings.GOOGLE_GSC_REDIRECT_URI,
                    "grant_type": "authorization_code",
                },
                timeout=20,
            )
            token_resp.raise_for_status()
            token_data = token_resp.json()
        except Exception as exc:
            messages.error(request, f"Failed to exchange authorisation code: {exc}")
            return redirect("seo:workspace-seo")

        access_token = token_data.get("access_token", "")
        refresh_token = token_data.get("refresh_token", "")
        expires_in = token_data.get("expires_in", 3600)

        from django.utils import timezone as _tz
        from datetime import timedelta as _td

        expiry = _tz.now() + _td(seconds=expires_in)

        # Fetch user info (email)
        google_email = ""
        try:
            info_resp = _req.get(
                self.USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10,
            )
            if info_resp.ok:
                google_email = info_resp.json().get("email", "")
        except Exception:
            pass

        # Try to detect the SC property for this project's domain
        project = resolve_workspace_project(request.user)
        sc_property = ""
        if project and project.normalized_domain:
            sc_property = f"sc-domain:{project.normalized_domain}"

        if project:
            from apps.leads.models import GSCConnection
            conn, _ = GSCConnection.objects.update_or_create(
                project=project,
                defaults={
                    "google_email": google_email,
                    "sc_property": sc_property,
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "token_expiry": expiry,
                    "is_active": True,
                    "error_message": "",
                },
            )
            messages.success(
                request,
                f"Google Search Console connected for {google_email}. "
                f"Real search data is now available for {project.name}.",
            )
        else:
            messages.warning(
                request,
                "GSC connected but no active workspace project found. "
                "Create or open a project first, then reconnect.",
            )
        return redirect("seo:workspace-seo")


class WorkspaceGSCDisconnectView(LoginRequiredMixin, View):
    """POST — Removes the GSC connection for the active workspace project."""

    def post(self, request, *args, **kwargs):
        project = resolve_workspace_project(request.user)
        if project:
            from apps.leads.models import GSCConnection
            GSCConnection.objects.filter(project=project).delete()
            messages.success(request, "Google Search Console disconnected.")
        return redirect("seo:workspace-seo")


class WorkspaceGSCDataView(LoginRequiredMixin, View):
    """
    GET — Returns top Search Console queries for the project's SC property.

    Uses the stored access token (refreshing if expired) to query the
    Search Analytics API for clicks, impressions, CTR, and average position.
    Results are returned as JSON for the workspace to consume.
    """

    SC_API = "https://searchconsole.googleapis.com/webmasters/v3/sites/{property}/searchAnalytics/query"

    def get(self, request, *args, **kwargs):
        from apps.leads.models import GSCConnection
        import requests as _req

        project = resolve_workspace_project(request.user)
        if not project:
            return JsonResponse({"error": "No active project."}, status=400)

        conn = GSCConnection.objects.filter(project=project, is_active=True).first()
        if not conn:
            return JsonResponse({"error": "No GSC connection for this project."}, status=400)

        # Refresh token if expired
        access_token = conn.access_token
        if not conn.is_token_fresh and conn.refresh_token:
            try:
                refresh_resp = _req.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "client_id": settings.GOOGLE_GSC_CLIENT_ID,
                        "client_secret": settings.GOOGLE_GSC_CLIENT_SECRET,
                        "refresh_token": conn.refresh_token,
                        "grant_type": "refresh_token",
                    },
                    timeout=15,
                )
                refresh_resp.raise_for_status()
                new_tokens = refresh_resp.json()
                access_token = new_tokens.get("access_token", access_token)
                from django.utils import timezone as _tz
                from datetime import timedelta as _td
                conn.access_token = access_token
                conn.token_expiry = _tz.now() + _td(seconds=new_tokens.get("expires_in", 3600))
                conn.save(update_fields=["access_token", "token_expiry", "updated_at"])
            except Exception as exc:
                return JsonResponse({"error": f"Token refresh failed: {exc}"}, status=502)

        # Query last 28 days
        from datetime import date, timedelta
        end_date = date.today()
        start_date = end_date - timedelta(days=28)
        sc_property = conn.sc_property

        payload = {
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "dimensions": ["query"],
            "rowLimit": 50,
            "startRow": 0,
        }
        try:
            resp = _req.post(
                self.SC_API.format(property=sc_property),
                headers={"Authorization": f"Bearer {access_token}"},
                json=payload,
                timeout=20,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            conn.error_message = str(exc)[:400]
            conn.save(update_fields=["error_message", "updated_at"])
            return JsonResponse({"error": f"GSC API error: {exc}"}, status=502)

        from django.utils import timezone as _tz
        conn.last_synced_at = _tz.now()
        conn.error_message = ""
        conn.save(update_fields=["last_synced_at", "error_message", "updated_at"])

        rows = data.get("rows", [])
        queries = [
            {
                "query": row.get("keys", [""])[0],
                "clicks": row.get("clicks", 0),
                "impressions": row.get("impressions", 0),
                "ctr": round(row.get("ctr", 0) * 100, 2),
                "position": round(row.get("position", 0), 1),
            }
            for row in rows
        ]
        return JsonResponse({"queries": queries, "property": sc_property, "rows": len(queries)})
