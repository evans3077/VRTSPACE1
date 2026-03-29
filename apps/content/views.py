from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, ListView

from .forms import GeneratedContentRequestForm
from .models import GeneratedContent
from .services import create_generated_content, get_workspace_content_project


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


class WorkspaceGeneratedContentDetailView(LoginRequiredMixin, DetailView):
    model = GeneratedContent
    template_name = "content/generated_content_detail.html"
    context_object_name = "generated_content"

    def get_queryset(self):
        return GeneratedContent.objects.select_related("project", "source_audit_run", "created_by")

    def get_object(self, queryset=None):
        obj = super().get_object(queryset=queryset)
        if not obj.project_id or obj.project.owner_id != self.request.user.id:
            raise Http404
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["project"] = self.object.project
        context["back_url"] = reverse("content:workspace-content")
        return context
