from django.contrib import messages
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils.dateparse import parse_date
from django.utils import timezone
from django.views import View

from apps.leads.services import get_workspace_projects, resolve_workspace_project
from apps.leads.models import ClientProject

from .backlinks import refresh_project_backlink_intelligence
from .forms import SEOProjectProfileForm
from .models import BacklinkProspect, SEOCampaign, SEOCompetitor, SEOProjectProfile
from .jobs import enqueue_project_seo_refresh
from .services import infer_business_type_for_project
from .services import (
    build_campaign_value_summary,
    build_campaign_workspace_items,
    build_competitor_trend_summary,
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
            messages.success(request, "SEO refresh queued. The workspace will update when competitor profiling finishes.")
            return redirect("seo:workspace-seo")
        else:
            snapshot, opportunity_snapshot = refresh_project_seo_intelligence(project)
            backlink_snapshot = refresh_project_backlink_intelligence(
                project,
                context_snapshot=snapshot,
                opportunity_snapshot=opportunity_snapshot,
            )
            messages.success(request, "SEO context saved and refreshed for this workspace.")
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
        initial = {
            "competitor_urls": "\n".join(competitor_urls),
            "location": getattr(project, "location", ""),
            "target_goal": getattr(project, "target_goal", ""),
            "primary_service": getattr(project, "primary_service", ""),
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
            "seo_competitors": payload.get("competitors", []),
            "seo_competitor_trace": payload.get("competitor_trace", []),
            "seo_competitor_patterns": payload.get("competitor_patterns", []),
            "seo_page_comparisons": payload.get("page_comparisons", []),
            "seo_serp_history": build_serp_evidence_history(project) if project else [],
            "seo_competitor_trends": build_competitor_trend_summary(project) if project else [],
            "seo_campaigns": campaign_items,
            "seo_chain_value_summary": build_campaign_value_summary(project, campaign_items=campaign_items) if project else {},
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
        }


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
