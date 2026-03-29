from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.conf import settings
from django.core.cache import cache
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView

from apps.core.site_content import PACKAGES
from apps.leads.auth import (
    GoogleOAuthError,
    build_google_authorize_url,
    create_google_oauth_state,
    exchange_google_code_for_userinfo,
    get_or_create_user_from_google_profile,
    is_google_oauth_enabled,
)
from apps.leads.forms import AuditRequestForm, WorkspaceLoginForm, WorkspaceSignupForm
from apps.leads.models import ClientProject
from apps.leads.services import create_audit_request_from_form, sync_client_project_from_audit_run

from .jobs import enqueue_public_site_audit
from .models import AuditRun
from .services import normalize_url


class PublicAuditCreateView(View):
    rate_limit = 3
    rate_window = 900

    def post(self, request, *args, **kwargs):
        ip_address = request.META.get("REMOTE_ADDR", "unknown")
        cache_key = f"rate-limit:{self.__class__.__name__}:{ip_address}"
        attempts = cache.get(cache_key, 0)
        
        # Bypass rate limit for staff users
        if not request.user.is_staff and attempts >= self.rate_limit:
            messages.error(request, "Too many audit requests. Try again in a few minutes.")
            return redirect("/#audit")
            
        cache.set(cache_key, attempts + 1, timeout=self.rate_window)

        form = AuditRequestForm(request.POST)
        if not form.is_valid():
            from apps.core.views import HomePageView, build_home_context
            from apps.leads.forms import LeadCaptureForm

            context = build_home_context(
                request,
                lead_form=LeadCaptureForm(),
                audit_form=form,
            )
            return render(request, HomePageView.template_name, context, status=400)

        audit_request = create_audit_request_from_form(form, request=request)
        audit_run = AuditRun.objects.create(
            audit_request=audit_request,
            normalized_domain="pending",
            start_url=normalize_url(audit_request.website),
        )

        enqueue_public_site_audit(audit_run.pk)
        messages.success(request, "Audit started. We are analyzing the site now.")
        return redirect("tools:audit-result", pk=audit_run.pk)


class AuditResultDetailView(DetailView):
    model = AuditRun
    template_name = "tools/audit_result.html"
    context_object_name = "audit_run"

    def get_queryset(self):
        return AuditRun.objects.prefetch_related("pages", "issues")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        audit_run = self.object
        summary = audit_run.summary or {}
        scores = summary.get("scores", {})
        score_breakdown = summary.get("score_breakdown", {})
        recommendations = summary.get("recommendations", [])
        featured_recommendations = summary.get("featured_recommendations", recommendations[:6])
        product_modules = summary.get("product_modules", [])
        custom_work_items = summary.get("custom_work_items", [])

        gauge_list = []
        metric_map = [
            ("Technical", "technical"),
            ("AEO", "aeo"),
            ("On-page", "on_page"),
            ("Content", "content"),
            ("Internal", "internal_linking"),
            ("Speed", "performance"),
            ("Accessibility", "accessibility"),
            ("Best Practices", "best_practices"),
            ("SEO", "seo"),
        ]

        for label, key in metric_map:
            score = scores.get(key, 0)
            # Normalize offset for smaller 50px gauges (circumference ~138.23)
            small_offset = round(138.23 * (1 - score / 100))
            
            gauge_list.append({
                "label": label,
                "score": score,
                "offset": small_offset,
                "color": "#16a34a" if score >= 90 else "#ea580c" if score >= 50 else "#dc2626"
            })
        context["gauge_list"] = gauge_list
        context["score_breakdown"] = score_breakdown
        context["recommendations"] = recommendations
        context["featured_recommendations"] = featured_recommendations
        context["secondary_recommendations"] = [item for item in recommendations if item not in featured_recommendations]
        context["product_modules"] = product_modules
        context["custom_work_items"] = custom_work_items
        context["packages"] = PACKAGES
        context["audit_tier_enforcement"] = settings.AUDIT_TIER_ENFORCEMENT
        context["pages"] = audit_run.pages.all()
        context["is_processing"] = audit_run.status in {AuditRun.Status.PENDING, AuditRun.Status.RUNNING}
        return context
from .admin_utils import get_service_recommendations


class AgencyAuditDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = AuditRun
    template_name = "tools/agency_audit.html"
    context_object_name = "audit_run"

    def test_func(self):
        return self.request.user.is_staff

    def get_queryset(self):
        return AuditRun.objects.prefetch_related("pages", "issues", "audit_request")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        audit_run = self.object
        context["pages"] = audit_run.pages.all()
        context["issues"] = audit_run.issues.all()
        context["service_recommendations"] = get_service_recommendations(audit_run)
        context["recommendations"] = (audit_run.summary or {}).get("recommendations", [])
        context["score_breakdown"] = (audit_run.summary or {}).get("score_breakdown", {})

        # Group issues by category
        from collections import defaultdict

        issues_by_cat = defaultdict(list)
        for issue in audit_run.issues.all():
            issues_by_cat[issue.category].append(issue)
        context["issues_by_category"] = dict(issues_by_cat)

        return context


class ProjectDashboardDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = ClientProject
    template_name = "tools/project_dashboard.html"
    context_object_name = "project"

    def test_func(self):
        return self.request.user.is_staff

    def get_queryset(self):
        return ClientProject.objects.select_related("audit_request", "latest_audit_run")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        project = self.object
        audit_history = (
            project.audit_request.audit_runs.order_by("-created_at")
            if project.audit_request_id
            else AuditRun.objects.none()
        )
        latest_audit = project.latest_audit_run or audit_history.first()
        latest_summary = latest_audit.summary if latest_audit and isinstance(latest_audit.summary, dict) else {}
        audit_history_list = list(audit_history)
        audit_history_with_delta = []
        for index, audit in enumerate(audit_history_list):
            next_older = audit_history_list[index + 1] if index + 1 < len(audit_history_list) else None
            delta = None if next_older is None else audit.overall_score - next_older.overall_score
            audit_history_with_delta.append({"audit": audit, "delta": delta})

        context["latest_audit"] = latest_audit
        context["audit_history"] = audit_history
        context["audit_history_with_delta"] = audit_history_with_delta
        context["score_breakdown"] = latest_summary.get("score_breakdown", {})
        context["recommendations"] = latest_summary.get("recommendations", [])
        context["product_modules"] = latest_summary.get("product_modules") or latest_summary.get("service_fit", [])
        context["custom_work_items"] = latest_summary.get("custom_work_items", [])
        context["packages"] = PACKAGES
        context["audit_tier_enforcement"] = settings.AUDIT_TIER_ENFORCEMENT
        return context


class WorkspaceSignupView(View):
    template_name = "tools/workspace_signup.html"

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("tools:workspace-dashboard")
        audit_run = self._get_audit_run()
        form = WorkspaceSignupForm(initial={"email": audit_run.audit_request.email if audit_run and audit_run.audit_request_id else ""})
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "audit_run": audit_run,
                "selected_package": self._get_selected_package(),
                "google_oauth_enabled": is_google_oauth_enabled(),
                "google_oauth_url": self._build_google_oauth_url(),
                "login_url": self._build_auth_url("tools:workspace-login"),
            },
        )

    def post(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("tools:workspace-dashboard")
        audit_run = self._get_audit_run()
        form = WorkspaceSignupForm(request.POST)
        if not form.is_valid():
            return render(
                request,
                self.template_name,
                {
                    "form": form,
                    "audit_run": audit_run,
                    "selected_package": self._get_selected_package(),
                    "google_oauth_enabled": is_google_oauth_enabled(),
                    "google_oauth_url": self._build_google_oauth_url(),
                    "login_url": self._build_auth_url("tools:workspace-login"),
                },
                status=400,
            )

        email = form.cleaned_data["email"]
        password = form.cleaned_data["password"]
        user = get_user_model().objects.create_user(username=email, email=email, password=password)
        login(request, user)

        if audit_run and audit_run.audit_request_id:
            project = sync_client_project_from_audit_run(audit_run)
            project.owner = user
            project.save(update_fields=["owner", "updated_at"])

        return redirect("tools:workspace-dashboard")

    def _get_audit_run(self):
        audit_pk = self.request.GET.get("audit") or self.request.POST.get("audit")
        if not audit_pk:
            return None
        return AuditRun.objects.filter(pk=audit_pk).select_related("audit_request").first()

    def _get_selected_package(self):
        package_name = (self.request.GET.get("package") or self.request.POST.get("package") or "").strip().lower()
        if not package_name:
            return None
        return next((package for package in PACKAGES if package["name"].lower() == package_name), None)

    def _build_auth_url(self, route_name):
        query = {}
        audit_pk = self.request.GET.get("audit") or self.request.POST.get("audit")
        package_name = self.request.GET.get("package") or self.request.POST.get("package")
        if audit_pk:
            query["audit"] = audit_pk
        if package_name:
            query["package"] = package_name
        base_url = reverse(route_name)
        if not query:
            return base_url
        return f"{base_url}?{urlencode(query)}"

    def _build_google_oauth_url(self):
        return self._build_auth_url("tools:google-oauth-start")


class WorkspaceLoginView(View):
    template_name = "tools/workspace_login.html"

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("tools:workspace-dashboard")
        return render(request, self.template_name, self._build_context(form=WorkspaceLoginForm(request=request)))

    def post(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("tools:workspace-dashboard")
        form = WorkspaceLoginForm(request=request, data=request.POST)
        if not form.is_valid():
            return render(request, self.template_name, self._build_context(form=form), status=400)

        login(request, form.get_user())
        self._link_audit_to_user(form.get_user())
        return redirect("tools:workspace-dashboard")

    def _build_context(self, *, form):
        signup_url = self._build_auth_url("tools:workspace-signup")
        return {
            "form": form,
            "audit_run": self._get_audit_run(),
            "selected_package": self._get_selected_package(),
            "google_oauth_enabled": is_google_oauth_enabled(),
            "google_oauth_url": self._build_auth_url("tools:google-oauth-start"),
            "signup_url": signup_url,
        }

    def _build_auth_url(self, route_name):
        query = {}
        audit_pk = self.request.GET.get("audit") or self.request.POST.get("audit")
        package_name = self.request.GET.get("package") or self.request.POST.get("package")
        if audit_pk:
            query["audit"] = audit_pk
        if package_name:
            query["package"] = package_name
        base_url = reverse(route_name)
        if not query:
            return base_url
        return f"{base_url}?{urlencode(query)}"

    def _get_audit_run(self):
        audit_pk = self.request.GET.get("audit") or self.request.POST.get("audit")
        if not audit_pk:
            return None
        return AuditRun.objects.filter(pk=audit_pk).select_related("audit_request").first()

    def _get_selected_package(self):
        package_name = (self.request.GET.get("package") or self.request.POST.get("package") or "").strip().lower()
        if not package_name:
            return None
        return next((package for package in PACKAGES if package["name"].lower() == package_name), None)

    def _link_audit_to_user(self, user):
        audit_run = self._get_audit_run()
        if not audit_run or not audit_run.audit_request_id:
            return
        project = sync_client_project_from_audit_run(audit_run)
        project.owner = user
        project.save(update_fields=["owner", "updated_at"])


class GoogleOAuthStartView(View):
    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("tools:workspace-dashboard")
        if not is_google_oauth_enabled():
            messages.error(request, "Google sign-in is not configured yet.")
            return redirect("tools:workspace-login")

        state = create_google_oauth_state()
        request.session["google_oauth_state"] = state
        request.session["google_oauth_audit"] = request.GET.get("audit", "")
        request.session["google_oauth_package"] = request.GET.get("package", "")

        redirect_uri = request.build_absolute_uri(reverse("tools:google-oauth-callback"))
        return redirect(build_google_authorize_url(redirect_uri=redirect_uri, state=state))


class GoogleOAuthCallbackView(View):
    def get(self, request, *args, **kwargs):
        if not is_google_oauth_enabled():
            messages.error(request, "Google sign-in is not configured yet.")
            return redirect("tools:workspace-login")

        session_state = request.session.get("google_oauth_state")
        callback_state = request.GET.get("state", "")
        if not session_state or session_state != callback_state:
            messages.error(request, "Google sign-in could not be verified. Try again.")
            return redirect("tools:workspace-login")

        if request.GET.get("error"):
            messages.error(request, "Google sign-in was cancelled.")
            return redirect("tools:workspace-login")

        code = request.GET.get("code", "")
        if not code:
            messages.error(request, "Google sign-in did not return an authorization code.")
            return redirect("tools:workspace-login")

        redirect_uri = request.build_absolute_uri(reverse("tools:google-oauth-callback"))
        try:
            profile = exchange_google_code_for_userinfo(code=code, redirect_uri=redirect_uri)
        except GoogleOAuthError as exc:
            messages.error(request, str(exc))
            return redirect("tools:workspace-login")

        user = get_or_create_user_from_google_profile(profile)
        login(request, user)
        self._link_audit_to_user(request, user)
        self._clear_google_session(request)
        return redirect("tools:workspace-dashboard")

    def _link_audit_to_user(self, request, user):
        audit_pk = request.session.get("google_oauth_audit")
        if not audit_pk:
            return
        audit_run = AuditRun.objects.filter(pk=audit_pk).select_related("audit_request").first()
        if not audit_run or not audit_run.audit_request_id:
            return
        project = sync_client_project_from_audit_run(audit_run)
        project.owner = user
        project.save(update_fields=["owner", "updated_at"])

    def _clear_google_session(self, request):
        for key in ("google_oauth_state", "google_oauth_audit", "google_oauth_package"):
            request.session.pop(key, None)


class WorkspaceLogoutView(View):
    def get(self, request, *args, **kwargs):
        logout(request)
        return redirect("core:home")


class WorkspaceDashboardView(LoginRequiredMixin, DetailView):
    model = ClientProject
    template_name = "tools/workspace_dashboard.html"
    context_object_name = "project"

    def get_object(self, queryset=None):
        project = (
            ClientProject.objects.select_related("latest_audit_run", "audit_request")
            .filter(owner=self.request.user)
            .order_by("-updated_at")
            .first()
        )
        if project:
            return project
        return ClientProject(
            name="Workspace",
            website="",
            normalized_domain="",
            latest_score=0,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        project = self.object
        latest_audit = getattr(project, "latest_audit_run", None)
        latest_summary = latest_audit.summary if latest_audit and isinstance(latest_audit.summary, dict) else {}
        audit_history = (
            project.audit_request.audit_runs.order_by("-created_at")
            if getattr(project, "audit_request_id", None)
            else AuditRun.objects.none()
        )
        audit_history_list = list(audit_history)
        audit_history_with_delta = []
        for index, audit in enumerate(audit_history_list):
            next_older = audit_history_list[index + 1] if index + 1 < len(audit_history_list) else None
            delta = None if next_older is None else audit.overall_score - next_older.overall_score
            audit_history_with_delta.append({"audit": audit, "delta": delta})
        context["latest_audit"] = latest_audit
        context["audit_history"] = audit_history
        context["audit_history_with_delta"] = audit_history_with_delta
        context["score_breakdown"] = latest_summary.get("score_breakdown", {})
        context["recommendations"] = latest_summary.get("recommendations", [])
        context["product_modules"] = latest_summary.get("product_modules", [])
        context["custom_work_items"] = latest_summary.get("custom_work_items", [])
        context["packages"] = PACKAGES
        context["audit_tier_enforcement"] = settings.AUDIT_TIER_ENFORCEMENT
        return context
