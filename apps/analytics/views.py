from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView

from .services import build_admin_dashboard_snapshot


class OperationsDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = "analytics/operations_dashboard.html"

    def test_func(self):
        return self.request.user.is_staff

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(build_admin_dashboard_snapshot())
        context["page_title"] = "Operations Dashboard | VRT SPACE AGENCY"
        context["meta_description"] = "Internal operations dashboard for leads, audits, pipeline stages, and geography signals."
        context["canonical_url"] = self.request.build_absolute_uri(self.request.path)
        context["meta_robots"] = "noindex, nofollow"
        context["shell_theme"] = "shell-light"
        return context
