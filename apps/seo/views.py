from django.contrib import messages
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.views import View

from apps.leads.models import ClientProject

from .forms import SEOProjectProfileForm
from .models import SEOCompetitor, SEOProjectProfile
from .jobs import enqueue_project_seo_refresh
from .services import (
    can_generate_seo_snapshot,
    refresh_project_seo_intelligence,
    sync_project_competitors,
)


class WorkspaceSEOView(LoginRequiredMixin, View):
    template_name = "seo/workspace_seo.html"

    def get(self, request, *args, **kwargs):
        project = self._get_project(request.user)
        profile = getattr(project, "seo_profile", None) if project else None
        form = SEOProjectProfileForm(instance=profile, initial=self._initial_form_data(project))
        snapshot = self._get_latest_snapshot(project, profile)
        opportunity_snapshot = self._get_latest_opportunity_snapshot(project, profile)
        return render(
            request,
            self.template_name,
            self._build_context(
                project=project,
                form=form,
                profile=profile,
                snapshot=snapshot,
                opportunity_snapshot=opportunity_snapshot,
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
            return render(
                request,
                self.template_name,
                self._build_context(
                    project=project,
                    form=form,
                    profile=profile,
                    snapshot=snapshot,
                    opportunity_snapshot=opportunity_snapshot,
                ),
                status=400,
            )

        profile = form.save(commit=False)
        profile.project = project
        profile.save()
        sync_project_competitors(project, form.cleaned_data.get("competitor_urls", ""))
        snapshot = None
        opportunity_snapshot = None
        if settings.SEO_REFRESH_ASYNC:
            metadata = dict(profile.metadata or {})
            metadata["refresh_status"] = "queued"
            metadata["refresh_error"] = ""
            profile.metadata = metadata
            profile.save(update_fields=["metadata", "updated_at"])
            enqueue_project_seo_refresh(project.pk)
            snapshot = self._get_latest_snapshot(project, profile)
            opportunity_snapshot = self._get_latest_opportunity_snapshot(project, profile)
            messages.success(request, "SEO refresh queued. The workspace will update when competitor profiling finishes.")
        else:
            snapshot, opportunity_snapshot = refresh_project_seo_intelligence(project)
            messages.success(request, "SEO context saved and refreshed for this workspace.")
        return render(
            request,
            self.template_name,
            self._build_context(
                project=project,
                form=SEOProjectProfileForm(instance=profile, initial=self._initial_form_data(project)),
                profile=profile,
                snapshot=snapshot,
                opportunity_snapshot=opportunity_snapshot,
            ),
        )

    def _get_project(self, user):
        return (
            ClientProject.objects.select_related("latest_audit_run", "seo_profile")
            .filter(owner=user)
            .order_by("-updated_at")
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

    def _initial_form_data(self, project):
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
        return {"competitor_urls": "\n".join(competitor_urls)}

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

    def _build_context(self, *, project, form, profile, snapshot, opportunity_snapshot):
        payload = snapshot.output_json if snapshot else {}
        opportunity_payload = opportunity_snapshot.output_json if opportunity_snapshot else {}
        refresh_state = (getattr(profile, "metadata", None) or {}) if profile else {}
        return {
            "project": project,
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
            "seo_value_summary": opportunity_payload.get("value_summary", {}),
            "seo_keyword_opportunities": opportunity_payload.get("keyword_opportunities", []),
            "seo_page_map": opportunity_payload.get("page_map", []),
            "seo_execution_queue": opportunity_payload.get("execution_queue", []),
            "can_generate_snapshot": can_generate_seo_snapshot(project),
            "seo_refresh_state": refresh_state,
        }
