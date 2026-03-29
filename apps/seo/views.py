from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.views import View

from apps.leads.models import ClientProject
from apps.leads.billing import record_usage
from apps.leads.models import UsageRecord

from .forms import SEOProjectProfileForm
from .models import SEOProjectProfile
from .services import (
    can_generate_seo_snapshot,
    get_or_build_seo_opportunity_snapshot,
    get_or_build_seo_snapshot,
    sync_project_competitors,
)


class WorkspaceSEOView(LoginRequiredMixin, View):
    template_name = "seo/workspace_seo.html"

    def get(self, request, *args, **kwargs):
        project = self._get_project(request.user)
        profile = getattr(project, "seo_profile", None) if project else None
        form = SEOProjectProfileForm(instance=profile, initial=self._initial_form_data(project))
        snapshot = self._get_snapshot(project, profile)
        opportunity_snapshot = self._get_opportunity_snapshot(project, profile, snapshot)
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
            snapshot = self._get_snapshot(project, profile)
            opportunity_snapshot = self._get_opportunity_snapshot(project, profile, snapshot)
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
        snapshot = self._get_snapshot(project, profile, force_refresh=True)
        opportunity_snapshot = self._get_opportunity_snapshot(
            project,
            profile,
            snapshot,
            force_refresh=True,
        )
        record_usage(request.user, UsageRecord.Metric.SEO_SNAPSHOT)
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

    def _get_snapshot(self, project, profile, force_refresh=False):
        if not profile or not can_generate_seo_snapshot(project):
            return None
        if force_refresh:
            latest_audit = project.latest_audit_run
            from .models import SEOContextSnapshot
            from .services import build_seo_context_payload

            return SEOContextSnapshot.objects.create(
                project=project,
                profile=profile,
                source_audit_run=latest_audit,
                output_json=build_seo_context_payload(project, profile, latest_audit),
            )
        return get_or_build_seo_snapshot(project=project, profile=profile, audit_run=project.latest_audit_run)

    def _initial_form_data(self, project):
        if not project:
            return {}
        competitor_urls = [
            competitor.homepage_url
            for competitor in project.seo_competitors.filter(is_active=True).order_by("homepage_url")
        ]
        if not competitor_urls and getattr(project, "audit_request", None):
            competitor_urls = getattr(project.audit_request, "competitor_urls", [])
        return {"competitor_urls": "\n".join(competitor_urls)}

    def _get_opportunity_snapshot(self, project, profile, snapshot, force_refresh=False):
        if not snapshot or not profile or not can_generate_seo_snapshot(project):
            return None
        if force_refresh:
            from .models import SEOOpportunitySnapshot
            from .services import build_seo_opportunity_payload

            return SEOOpportunitySnapshot.objects.create(
                project=project,
                profile=profile,
                source_audit_run=project.latest_audit_run,
                source_context_snapshot=snapshot,
                output_json=build_seo_opportunity_payload(
                    project,
                    profile,
                    project.latest_audit_run,
                    context_snapshot=snapshot,
                ),
            )
        return get_or_build_seo_opportunity_snapshot(
            project=project,
            profile=profile,
            audit_run=project.latest_audit_run,
            context_snapshot=snapshot,
        )

    def _build_context(self, *, project, form, profile, snapshot, opportunity_snapshot):
        payload = snapshot.output_json if snapshot else {}
        opportunity_payload = opportunity_snapshot.output_json if opportunity_snapshot else {}
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
            "seo_competitors": payload.get("competitors", []),
            "seo_value_summary": opportunity_payload.get("value_summary", {}),
            "seo_keyword_opportunities": opportunity_payload.get("keyword_opportunities", []),
            "seo_page_map": opportunity_payload.get("page_map", []),
            "seo_execution_queue": opportunity_payload.get("execution_queue", []),
            "can_generate_snapshot": can_generate_seo_snapshot(project),
        }
