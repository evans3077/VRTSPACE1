from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, ListView

from apps.leads.billing import BillingError, build_credit_action_guide, can_access_workspace_feature, record_usage, spend_action_credits
from apps.leads.models import UsageRecord
from apps.leads.services import get_workspace_projects

from .forms import GeneratedContentEditForm, GeneratedContentRequestForm
from .models import GeneratedContent
from .services import (
    apply_generated_content,
    create_generated_content,
    get_editorial_task,
    get_editorial_tasks,
    get_workspace_content_project,
    refresh_generated_content_validation,
    sync_project_editorial_tasks,
)


class WorkspaceGeneratedContentAccessMixin(LoginRequiredMixin):
    def get_generated_content(self, pk):
        obj = (
            GeneratedContent.objects.select_related(
                "project",
                "source_audit_run",
                "source_seo_snapshot",
                "source_seo_opportunity_snapshot",
                "source_seo_campaign",
                "source_editorial_task",
                "source_editorial_task__seo_campaign",
                "created_by",
                "applied_article",
                "applied_service",
            )
            .filter(pk=pk)
            .first()
        )
        if not obj or not obj.project_id or obj.project.owner_id != self.request.user.id:
            raise Http404
        return obj


class WorkspaceGeneratedContentListView(LoginRequiredMixin, ListView):
    template_name = "content/workspace_content.html"
    context_object_name = "generated_content_list"

    def get_queryset(self):
        project = get_workspace_content_project(user=self.request.user, request=self.request)
        if not project:
            return GeneratedContent.objects.none()
        return (
            GeneratedContent.objects.select_related(
                "project",
                "source_audit_run",
                "source_seo_snapshot",
                "source_seo_opportunity_snapshot",
                "source_seo_campaign",
            )
            .filter(project=project)
            .order_by("-created_at")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        project = get_workspace_content_project(user=self.request.user, request=self.request)
        context["project"] = project
        context["workspace_projects"] = get_workspace_projects(self.request.user)
        context["form"] = GeneratedContentRequestForm()
        context["editorial_tasks"] = get_editorial_tasks(project)
        context["workspace_credit_actions"] = build_credit_action_guide(project, self.request.user) if project else []
        return context


class WorkspaceGeneratedContentCreateView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        project = get_workspace_content_project(user=request.user, request=request)
        if not project:
            messages.error(request, "Create or connect a workspace project before generating drafts.")
            return redirect("tools:workspace-dashboard")
        allowed, _ = can_access_workspace_feature(request.user, "content_workspace_enabled")
        if not allowed:
            messages.error(request, "Content generation requires a plan that includes content credits.")
            return redirect("tools:workspace-dashboard")

        form = GeneratedContentRequestForm(request.POST)
        if not form.is_valid():
            queryset = (
                GeneratedContent.objects.select_related("project", "source_audit_run")
                .select_related(
                    "source_seo_snapshot",
                    "source_seo_opportunity_snapshot",
                    "source_seo_campaign",
                )
                .filter(project=project)
                .order_by("-created_at")
            )
            return render(
                request,
                "content/workspace_content.html",
                {
                    "project": project,
                    "workspace_projects": get_workspace_projects(request.user),
                    "generated_content_list": queryset,
                    "form": form,
                    "editorial_tasks": get_editorial_tasks(project),
                },
                status=400,
            )

        try:
            _entry, estimate = spend_action_credits(
                request.user,
                "content",
                project=project,
                payload={"output_type": form.cleaned_data["output_type"]},
                note="Manual content draft generation",
                reference_key=f"content-draft:{project.pk}:{request.user.pk}",
            )
            draft = create_generated_content(
                user=request.user,
                project=project,
                output_type=form.cleaned_data["output_type"],
                input_data=form.cleaned_data,
            )
            record_usage(request.user, UsageRecord.Metric.CONTENT_DRAFT)
        except BillingError as exc:
            messages.error(request, str(exc))
            return redirect("content:workspace-content")
        messages.success(request, f"AI content draft created. This draft used {estimate['amount']} workspace credits.")
        return redirect("content:workspace-content-detail", pk=draft.pk)


class WorkspaceGeneratedContentFromSEOView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        project = get_workspace_content_project(user=request.user, request=request)
        if not project:
            messages.error(request, "Create or connect a workspace project before generating drafts.")
            return redirect("tools:workspace-dashboard")
        allowed, _ = can_access_workspace_feature(request.user, "content_workspace_enabled")
        if not allowed:
            messages.error(request, "Content generation requires a plan that includes content credits.")
            return redirect("tools:workspace-dashboard")

        brief_key = request.POST.get("brief_key", "").strip()
        task = get_editorial_task(project, brief_key)
        if not task:
            messages.error(request, "That SEO brief is no longer available. Refresh the SEO hub and try again.")
            return redirect("content:workspace-content")
        brief = task.brief_json or {}

        try:
            _entry, estimate = spend_action_credits(
                request.user,
                "content",
                project=project,
                payload={"output_type": brief["output_type"]},
                note="SEO-driven content draft generation",
                reference_key=f"content-brief:{task.brief_key}",
            )
            draft = create_generated_content(
                user=request.user,
                project=project,
                output_type=brief["output_type"],
                input_data={
                    "business_type": brief["business_type"],
                    "location": brief["location"],
                    "target_audience": brief["target_audience"],
                    "page_goal": brief["page_goal"],
                    "offer_summary": brief["offer_summary"],
                    "target_keywords": [brief["primary_keyword"], *brief.get("secondary_keywords", [])],
                    "search_intent": brief["search_intent"],
                    "seo_brief": brief,
                    "source_editorial_task": task,
                },
            )
            record_usage(request.user, UsageRecord.Metric.CONTENT_DRAFT)
        except BillingError as exc:
            messages.error(request, str(exc))
            return redirect("content:workspace-content")
        messages.success(request, f"SEO-driven content brief converted into a draft using {estimate['amount']} workspace credits.")
        return redirect("content:workspace-content-detail", pk=draft.pk)


class WorkspaceEditorialQueueSyncView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        project = get_workspace_content_project(user=request.user, request=request)
        if not project:
            messages.error(request, "Create or connect a workspace project before syncing the editorial queue.")
            return redirect("tools:workspace-dashboard")
        tasks = sync_project_editorial_tasks(project)
        messages.success(request, f"Editorial queue synced. {len(tasks)} active item(s) are now tracked.")
        return redirect("content:workspace-content")


class WorkspaceGeneratedContentDetailView(WorkspaceGeneratedContentAccessMixin, DetailView):
    model = GeneratedContent
    template_name = "content/generated_content_detail.html"
    context_object_name = "generated_content"

    def get_queryset(self):
        return GeneratedContent.objects.select_related(
            "project",
            "source_audit_run",
            "source_seo_snapshot",
            "source_seo_opportunity_snapshot",
            "source_seo_campaign",
            "source_editorial_task",
            "source_editorial_task__seo_campaign",
            "created_by",
            "applied_article",
            "applied_service",
        )

    def get_object(self, queryset=None):
        return self.get_generated_content(self.kwargs["pk"])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["project"] = self.object.project
        context["back_url"] = reverse("content:workspace-content")
        context["edit_form"] = kwargs.get("edit_form") or GeneratedContentEditForm(instance=self.object)
        return context


class WorkspaceGeneratedContentUpdateView(WorkspaceGeneratedContentAccessMixin, View):
    def post(self, request, *args, **kwargs):
        draft = self.get_generated_content(kwargs["pk"])
        form = GeneratedContentEditForm(request.POST, instance=draft)
        if not form.is_valid():
            detail_view = WorkspaceGeneratedContentDetailView()
            detail_view.request = request
            detail_view.object = draft
            context = detail_view.get_context_data(edit_form=form)
            return render(request, detail_view.template_name, context, status=400)

        draft = form.save()
        refresh_generated_content_validation(draft)
        messages.success(request, "Draft updated.")
        return redirect("content:workspace-content-detail", pk=draft.pk)


class WorkspaceGeneratedContentApplyView(WorkspaceGeneratedContentAccessMixin, View):
    def post(self, request, *args, **kwargs):
        draft = self.get_generated_content(kwargs["pk"])
        apply_generated_content(draft)
        messages.success(request, "Draft applied to the content library.")
        return redirect("content:workspace-content-detail", pk=draft.pk)


class WorkspaceGeneratedContentJsonView(WorkspaceGeneratedContentAccessMixin, View):
    def get(self, request, *args, **kwargs):
        draft = self.get_generated_content(kwargs["pk"])
        return JsonResponse(draft.output_json or {}, status=200)
