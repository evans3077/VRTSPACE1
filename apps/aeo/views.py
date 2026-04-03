from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View

from apps.content.services import get_workspace_content_project
from apps.leads.billing import BillingError, build_credit_action_guide, can_access_workspace_feature, record_usage, spend_action_credits
from apps.leads.services import get_workspace_projects
from apps.leads.models import UsageRecord

from .forms import AEOAuditRequestForm
from .services import create_aeo_audit, get_latest_aeo_audit


class WorkspaceAEOView(LoginRequiredMixin, View):
    template_name = "aeo/workspace_aeo.html"

    def get(self, request, *args, **kwargs):
        project = get_workspace_content_project(user=request.user, request=request)
        latest_aeo_audit = get_latest_aeo_audit(project)
        return render(
            request,
            self.template_name,
            {
                "project": project,
                "workspace_projects": get_workspace_projects(request.user),
                "form": AEOAuditRequestForm(initial={"target_keyword": getattr(latest_aeo_audit, "target_keyword", "")}),
                "latest_aeo_audit": latest_aeo_audit,
                "aeo_payload": latest_aeo_audit.output_json if latest_aeo_audit else {},
                "workspace_credit_actions": build_credit_action_guide(project, request.user) if project else [],
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
        return render(
            request,
            self.template_name,
            {
                "project": project,
                "workspace_projects": get_workspace_projects(request.user),
                "form": AEOAuditRequestForm(initial={"target_keyword": aeo_audit.target_keyword}),
                "latest_aeo_audit": aeo_audit,
                "aeo_payload": aeo_audit.output_json,
                "workspace_credit_actions": build_credit_action_guide(project, request.user),
            },
        )
