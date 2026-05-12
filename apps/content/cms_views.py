"""
P4 — Views for connecting a CMS and pushing editorial drafts.
"""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View

from apps.leads.models import ClientProject
from apps.leads.billing import spend_action_credits, BillingError

from .cms_publishers import CMSPushError, push_to_wordpress
from .models import CMSCredential, ContentEditorialTask


def _active_project(user, request):
    project_id = request.session.get("active_project_id")
    qs = ClientProject.objects.filter(owner=user)
    if project_id:
        proj = qs.filter(pk=project_id).first()
        if proj:
            return proj
    return qs.first()


class WorkspaceCMSCredentialView(LoginRequiredMixin, View):
    """List + manage CMS credentials for the active project."""

    template_name = "content/workspace_cms_credentials.html"

    def get(self, request, *args, **kwargs):
        project = _active_project(request.user, request)
        credentials = (
            CMSCredential.objects.filter(project=project).order_by("platform")
            if project
            else []
        )
        return render(
            request,
            self.template_name,
            {
                "project": project,
                "credentials": credentials,
                "platform_choices": CMSCredential.Platform.choices,
                "page_title": "Connect your CMS | VRT SPACE AGENCY",
                "meta_description": "Connect WordPress to push generated drafts straight into your CMS.",
                "meta_robots": "noindex, nofollow",
                "canonical_url": request.build_absolute_uri(request.path),
                "shell_theme": "shell-light",
            },
        )

    def post(self, request, *args, **kwargs):
        project = _active_project(request.user, request)
        if not project:
            messages.error(request, "Create a project before connecting a CMS.")
            return redirect("tools:workspace-dashboard")

        platform = (request.POST.get("platform") or "").strip().lower() or CMSCredential.Platform.WORDPRESS
        site_url = (request.POST.get("site_url") or "").strip()
        username = (request.POST.get("username") or "").strip()
        app_password = (request.POST.get("app_password") or "").strip()
        api_token = (request.POST.get("api_token") or "").strip()

        if not site_url:
            messages.error(request, "Provide the site URL.")
            return redirect("content:workspace-cms-credentials")

        defaults = {
            "site_url": site_url,
            "username": username,
            "app_password": app_password,
            "api_token": api_token,
            "is_active": True,
        }
        CMSCredential.objects.update_or_create(
            project=project, platform=platform, defaults=defaults
        )
        messages.success(request, f"{platform.title()} credential saved.")
        return redirect("content:workspace-cms-credentials")


class WorkspaceEditorialTaskPushView(LoginRequiredMixin, View):
    """POST-only — push a single editorial task to the connected CMS.

    Costs workspace credits via spend_action_credits('content', ...).
    """

    def post(self, request, pk, *args, **kwargs):
        task = get_object_or_404(
            ContentEditorialTask.objects.select_related("project"),
            pk=pk,
            project__owner=request.user,
        )

        # Best-effort credit debit; never blocks if billing is in shadow mode.
        try:
            spend_action_credits(
                request.user,
                "content",
                project=task.project,
                note=f"Push to CMS — {task.title[:60]}",
                reference_key=f"cms-push:{task.pk}",
            )
        except BillingError as exc:
            messages.error(request, str(exc))
            return redirect("content:workspace-content")
        except Exception:  # pragma: no cover - defensive
            pass

        try:
            log = push_to_wordpress(
                task=task,
                triggered_by=request.user,
            )
        except CMSPushError as exc:
            messages.error(request, str(exc))
            return redirect("content:workspace-cms-credentials")

        if log.status == log.Status.SUCCESS:
            messages.success(
                request,
                f"Draft pushed to WordPress. Open it in your dashboard: {log.remote_post_url}",
            )
            task.status = ContentEditorialTask.Status.APPLIED
            task.save(update_fields=["status", "updated_at"])
        else:
            messages.error(request, f"Push failed: {log.response_summary[:200]}")
        return redirect("content:workspace-content")
