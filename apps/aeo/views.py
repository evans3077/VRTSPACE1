from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.views import View

from apps.content.services import get_workspace_content_project
from apps.leads.billing import record_usage
from apps.leads.models import UsageRecord

from .forms import AEOAuditRequestForm
from .services import create_aeo_audit, get_latest_aeo_audit


class WorkspaceAEOView(LoginRequiredMixin, View):
    template_name = "aeo/workspace_aeo.html"

    def get(self, request, *args, **kwargs):
        project = get_workspace_content_project(request.user)
        latest_aeo_audit = get_latest_aeo_audit(project)
        return render(
            request,
            self.template_name,
            {
                "project": project,
                "form": AEOAuditRequestForm(initial={"target_keyword": getattr(latest_aeo_audit, "target_keyword", "")}),
                "latest_aeo_audit": latest_aeo_audit,
                "aeo_payload": latest_aeo_audit.output_json if latest_aeo_audit else {},
            },
        )

    def post(self, request, *args, **kwargs):
        project = get_workspace_content_project(request.user)
        if not project:
            messages.error(request, "Create or connect a workspace project before running AEO analysis.")
            return redirect("tools:workspace-dashboard")

        form = AEOAuditRequestForm(request.POST)
        if not form.is_valid():
            latest_aeo_audit = get_latest_aeo_audit(project)
            return render(
                request,
                self.template_name,
                {
                    "project": project,
                    "form": form,
                    "latest_aeo_audit": latest_aeo_audit,
                    "aeo_payload": latest_aeo_audit.output_json if latest_aeo_audit else {},
                },
                status=400,
            )

        try:
            aeo_audit = create_aeo_audit(
                project=project,
                target_keyword=form.cleaned_data["target_keyword"],
            )
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect("aeo:workspace-aeo")

        record_usage(request.user, UsageRecord.Metric.AEO_AUDIT)
        messages.success(request, "AEO analysis created from the latest workspace audit.")
        return render(
            request,
            self.template_name,
            {
                "project": project,
                "form": AEOAuditRequestForm(initial={"target_keyword": aeo_audit.target_keyword}),
                "latest_aeo_audit": aeo_audit,
                "aeo_payload": aeo_audit.output_json,
            },
        )
