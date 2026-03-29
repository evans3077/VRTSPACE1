from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, ListView

from .forms import GeneratedContentEditForm, GeneratedContentRequestForm
from .models import GeneratedContent
from .services import (
    apply_generated_content,
    create_generated_content,
    get_workspace_content_project,
    refresh_generated_content_validation,
)


class WorkspaceGeneratedContentAccessMixin(LoginRequiredMixin):
    def get_generated_content(self, pk):
        obj = (
            GeneratedContent.objects.select_related(
                "project",
                "source_audit_run",
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
        project = get_workspace_content_project(self.request.user)
        if not project:
            return GeneratedContent.objects.none()
        return (
            GeneratedContent.objects.select_related("project", "source_audit_run")
            .filter(project=project)
            .order_by("-created_at")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["project"] = get_workspace_content_project(self.request.user)
        context["form"] = GeneratedContentRequestForm()
        return context


class WorkspaceGeneratedContentCreateView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        project = get_workspace_content_project(request.user)
        if not project:
            messages.error(request, "Create or connect a workspace project before generating drafts.")
            return redirect("tools:workspace-dashboard")

        form = GeneratedContentRequestForm(request.POST)
        if not form.is_valid():
            queryset = (
                GeneratedContent.objects.select_related("project", "source_audit_run")
                .filter(project=project)
                .order_by("-created_at")
            )
            return render(
                request,
                "content/workspace_content.html",
                {
                    "project": project,
                    "generated_content_list": queryset,
                    "form": form,
                },
                status=400,
            )

        draft = create_generated_content(
            user=request.user,
            project=project,
            output_type=form.cleaned_data["output_type"],
            input_data=form.cleaned_data,
        )
        messages.success(request, "AI content draft created.")
        return redirect("content:workspace-content-detail", pk=draft.pk)


class WorkspaceGeneratedContentDetailView(WorkspaceGeneratedContentAccessMixin, DetailView):
    model = GeneratedContent
    template_name = "content/generated_content_detail.html"
    context_object_name = "generated_content"

    def get_queryset(self):
        return GeneratedContent.objects.select_related(
            "project",
            "source_audit_run",
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
