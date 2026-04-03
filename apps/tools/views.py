from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.conf import settings
from django.core.cache import cache
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView

from apps.core.site_content import PACKAGES
from apps.leads.billing import (
    build_credit_action_guide,
    can_access_audit_feature,
    get_billing_state,
    get_effective_capabilities,
    get_limited_audit_history,
    get_limited_recommendations,
)
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
from apps.leads.services import (
    create_audit_request_from_form,
    get_workspace_projects,
    resolve_workspace_project,
    set_active_workspace_project,
    sync_client_project_from_audit_run,
)

from .audit_exports import (
    build_absolute_app_url,
    build_audit_csv_export,
    build_audit_export_payload,
    get_or_create_audit_share_link,
)
from .automation import get_workspace_schedule
from .jobs import enqueue_public_site_audit
from .models import AuditRun, AuditShareLink
from .pdf_reports import build_audit_report_pdf
from .services import extract_domain, normalize_url


def _decorate_product_modules(product_modules, billing_plans):
    plan_map = {card["slug"]: card for card in billing_plans}
    decorated = []
    for module in product_modules or []:
        plan_slug = str(module.get("plan", "")).strip().lower()
        card = plan_map.get(plan_slug)
        item = dict(module)
        item["plan_slug"] = plan_slug
        item["cta_label"] = module.get("cta_label") or f"Upgrade to {module.get('plan', 'Plan')}"
        item["can_checkout"] = bool(card and not card.get("is_current") and not card.get("is_custom"))
        item["is_current_plan"] = bool(card and card.get("is_current"))
        item["is_custom_scope"] = bool(card and card.get("is_custom"))
        decorated.append(item)
    return decorated


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

        normalized_start_url = normalize_url(form.cleaned_data["website"])
        normalized_domain = extract_domain(normalized_start_url)
        existing_run = (
            AuditRun.objects.filter(
                normalized_domain=normalized_domain,
                status__in={AuditRun.Status.PENDING, AuditRun.Status.RUNNING},
            )
            .order_by("-created_at")
            .first()
        )
        if existing_run:
            messages.info(
                request,
                "An audit for this website is already in progress. Opening the current result instead of creating a duplicate run.",
            )
            return redirect("tools:audit-result", pk=existing_run.pk)

        audit_request = create_audit_request_from_form(form, request=request)
        audit_run = AuditRun.objects.create(
            audit_request=audit_request,
            normalized_domain=normalized_domain or "pending",
            start_url=normalized_start_url,
        )

        sync_client_project_from_audit_run(audit_run)
        enqueue_public_site_audit(audit_run.pk)
        messages.success(request, "Audit started. We are analyzing the site now.")
        return redirect("tools:audit-result", pk=audit_run.pk)


class AuditResultDetailView(DetailView):
    model = AuditRun
    template_name = "tools/audit_result.html"
    context_object_name = "audit_run"

    def get_queryset(self):
        return AuditRun.objects.prefetch_related("pages", "issues")

    def get(self, request, *args, **kwargs):
        self.object = self.get_queryset().filter(pk=kwargs.get("pk")).first()
        if not self.object:
            messages.warning(
                request,
                "That audit report is no longer available. Run a new audit or open your workspace for the latest saved results.",
            )
            if request.user.is_authenticated:
                return redirect("tools:workspace-dashboard")
            return redirect("core:home")
        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)

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
            raw_score = scores.get(key, 0)
            score = raw_score if isinstance(raw_score, (int, float)) else 0
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
        visible_recommendations, locked_recommendation_count = get_limited_recommendations(
            recommendations,
            self.request.user,
        )
        recommendation_limit = get_effective_capabilities(self.request.user)["premium_recommendation_limit"]
        if settings.AUDIT_TIER_ENFORCEMENT and recommendation_limit is not None:
            product_modules = product_modules[:recommendation_limit]
        context["recommendations"] = visible_recommendations
        context["featured_recommendations"] = featured_recommendations
        context["secondary_recommendations"] = [item for item in visible_recommendations if item not in featured_recommendations]
        context["product_modules"] = product_modules
        context["custom_work_items"] = custom_work_items
        context["packages"] = PACKAGES
        context["audit_tier_enforcement"] = settings.AUDIT_TIER_ENFORCEMENT
        context["pages"] = audit_run.pages.all()
        context["is_processing"] = audit_run.status in {AuditRun.Status.PENDING, AuditRun.Status.RUNNING}
        context["locked_recommendation_count"] = locked_recommendation_count
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
        project = resolve_workspace_project(self.request, self.request.user)
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
        generated_content_count = 0
        if getattr(project, "pk", None):
            from apps.content.models import GeneratedContent

            generated_content_count = GeneratedContent.objects.filter(project=project).count()
        latest_audit = getattr(project, "latest_audit_run", None)
        latest_summary = latest_audit.summary if latest_audit and isinstance(latest_audit.summary, dict) else {}
        latest_seo_snapshot = project.seo_snapshots.order_by("-created_at").first() if getattr(project, "pk", None) else None
        latest_aeo_audit = project.aeo_audits.order_by("-created_at").first() if getattr(project, "pk", None) else None
        audit_history, locked_history_count = get_limited_audit_history(project, self.request.user)
        audit_history_list = list(audit_history)
        change_report_map = {
            report.audit_run_id: report
            for report in project.change_reports.select_related("audit_run", "previous_audit_run")[:5]
        } if getattr(project, "pk", None) else {}
        audit_history_with_delta = []
        for index, audit in enumerate(audit_history_list):
            next_older = audit_history_list[index + 1] if index + 1 < len(audit_history_list) else None
            delta = None if next_older is None else audit.overall_score - next_older.overall_score
            audit_history_with_delta.append(
                {
                    "audit": audit,
                    "delta": delta,
                    "change_report": change_report_map.get(audit.pk),
                }
            )
        recommendations, locked_recommendation_count = get_limited_recommendations(
            latest_summary.get("recommendations", []),
            self.request.user,
        )
        billing_state = get_billing_state(self.request.user)
        schedule = get_workspace_schedule(project)
        latest_change_report = getattr(latest_audit, "change_report", None) if latest_audit else None
        fix_queue_recommendations = latest_summary.get("featured_recommendations") or recommendations[:6]
        latest_share_link = (
            AuditShareLink.objects.filter(audit_run=latest_audit).order_by("-created_at").first()
            if latest_audit
            else None
        )
        share_allowed, _ = can_access_audit_feature(self.request.user, "stakeholder_sharing_enabled")
        export_allowed, _ = can_access_audit_feature(self.request.user, "export_reports_enabled")
        email_allowed, _ = can_access_audit_feature(self.request.user, "email_reports_enabled")
        context["latest_audit"] = latest_audit
        context["audit_history"] = audit_history
        context["audit_history_with_delta"] = audit_history_with_delta
        context["score_breakdown"] = latest_summary.get("score_breakdown", {})
        context["recommendations"] = recommendations
        context["fix_queue_recommendations"] = fix_queue_recommendations
        context["product_modules"] = _decorate_product_modules(
            latest_summary.get("product_modules", []),
            billing_state["plans"],
        )
        context["custom_work_items"] = latest_summary.get("custom_work_items", [])
        context["context_analysis"] = latest_summary.get("context_analysis", {})
        context["packages"] = PACKAGES
        context["audit_tier_enforcement"] = settings.AUDIT_TIER_ENFORCEMENT
        context["locked_history_count"] = locked_history_count
        context["locked_recommendation_count"] = locked_recommendation_count
        context["billing_state"] = billing_state
        context["current_subscription"] = billing_state["subscription"]
        context["current_capabilities"] = billing_state["capabilities"]
        context["usage_summary"] = billing_state["usage"]
        context["credit_summary"] = billing_state["credits"]
        context["credit_overview"] = billing_state["credit_overview"]
        context["credit_activity"] = billing_state["credit_activity"]
        context["recent_credit_entries"] = billing_state["recent_credit_entries"]
        context["credit_action_guide"] = build_credit_action_guide(project) if getattr(project, "pk", None) else []
        context["billing_plans"] = billing_state["plans"]
        context["audit_schedule"] = schedule
        context["latest_change_report"] = latest_change_report
        context["generated_content_count"] = generated_content_count
        context["latest_seo_snapshot"] = latest_seo_snapshot
        context["latest_aeo_audit"] = latest_aeo_audit
        context["latest_share_link"] = latest_share_link
        context["latest_share_url"] = build_absolute_app_url(f"/share/audits/{latest_share_link.token}/") if latest_share_link else ""
        context["share_reports_allowed"] = share_allowed
        context["export_reports_allowed"] = export_allowed
        context["email_reports_allowed"] = email_allowed
        context["workspace_projects"] = get_workspace_projects(self.request.user)
        return context


class WorkspaceProjectSelectView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        project = resolve_workspace_project(
            request,
            request.user,
            project_id=request.POST.get("project_id"),
            fallback=False,
        )
        if project is None:
            messages.error(request, "That workspace project is not available for this account.")
            return redirect("tools:workspace-dashboard")

        set_active_workspace_project(request, project)
        messages.success(request, f"Workspace switched to {project.name}.")
        next_url = request.POST.get("next", "").strip()
        if next_url.startswith("/"):
            return redirect(next_url)
        return redirect("tools:workspace-dashboard")


class AuditReportPdfView(DetailView):
    model = AuditRun

    def get_queryset(self):
        return AuditRun.objects.prefetch_related("pages", "issues")

    def get(self, request, *args, **kwargs):
        audit_run = self.get_object()
        if audit_run.status != AuditRun.Status.COMPLETED:
            return HttpResponse("Audit report is not available until the audit completes.", status=409)

        pdf_bytes = build_audit_report_pdf(audit_run)
        disposition = "attachment" if request.GET.get("download") == "1" else "inline"
        filename = f"audit-report-{audit_run.normalized_domain or audit_run.pk}.pdf"
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'{disposition}; filename="{filename}"'
        return response


class WorkspaceAuditAccessMixin(LoginRequiredMixin):
    def get_workspace_audit(self, pk):
        audit_run = (
            AuditRun.objects.select_related("audit_request", "audit_request__client_project")
            .filter(pk=pk)
            .first()
        )
        project = getattr(getattr(audit_run, "audit_request", None), "client_project", None)
        if not audit_run or not project:
            raise Http404
        if self.request.user.is_staff or project.owner_id == self.request.user.id:
            return audit_run
        raise Http404

    def ensure_completed_audit(self, audit_run):
        if audit_run.status != AuditRun.Status.COMPLETED:
            raise Http404
        return audit_run


class WorkspaceAuditExportJsonView(WorkspaceAuditAccessMixin, View):
    def get(self, request, *args, **kwargs):
        allowed, _ = can_access_audit_feature(request.user, "export_reports_enabled")
        if not allowed:
            return JsonResponse({"error": "JSON exports require a plan that supports advanced exports."}, status=403)

        audit_run = self.get_workspace_audit(kwargs["pk"])
        if audit_run.status != AuditRun.Status.COMPLETED:
            return JsonResponse({"error": "Exports are only available after the audit completes."}, status=409)
        self.ensure_completed_audit(audit_run)
        return JsonResponse(build_audit_export_payload(audit_run), status=200)


class WorkspaceAuditExportCsvView(WorkspaceAuditAccessMixin, View):
    def get(self, request, *args, **kwargs):
        allowed, _ = can_access_audit_feature(request.user, "export_reports_enabled")
        if not allowed:
            return HttpResponse("CSV exports require a plan that supports advanced exports.", status=403)

        audit_run = self.get_workspace_audit(kwargs["pk"])
        if audit_run.status != AuditRun.Status.COMPLETED:
            return HttpResponse("Exports are only available after the audit completes.", status=409)
        self.ensure_completed_audit(audit_run)
        response = HttpResponse(build_audit_csv_export(audit_run), content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="audit-export-{audit_run.pk}.csv"'
        return response


class WorkspaceAuditShareCreateView(WorkspaceAuditAccessMixin, View):
    def post(self, request, *args, **kwargs):
        allowed, _ = can_access_audit_feature(request.user, "stakeholder_sharing_enabled")
        if not allowed:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"error": "Stakeholder sharing requires a plan that supports shared reports."}, status=403)
            raise Http404

        audit_run = self.get_workspace_audit(kwargs["pk"])
        if audit_run.status != AuditRun.Status.COMPLETED:
            return JsonResponse({"error": "Shared reports are only available after the audit completes."}, status=409)
        self.ensure_completed_audit(audit_run)
        share_link = get_or_create_audit_share_link(audit_run, created_by=request.user)
        payload = {
            "share_url": build_absolute_app_url(f"/share/audits/{share_link.token}/"),
            "pdf_url": build_absolute_app_url(f"/share/audits/{share_link.token}/report.pdf"),
            "expires_at": share_link.expires_at.isoformat() if share_link.expires_at else None,
        }
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse(payload, status=200)

        request.session["latest_share_url"] = payload["share_url"]
        return redirect("tools:workspace-dashboard")


class SharedAuditReportView(DetailView):
    model = AuditShareLink
    slug_field = "token"
    slug_url_kwarg = "token"
    template_name = "tools/shared_audit_report.html"
    context_object_name = "share_link"

    def get_queryset(self):
        return AuditShareLink.objects.select_related("audit_run")

    def get_object(self, queryset=None):
        share_link = super().get_object(queryset=queryset)
        if share_link.expires_at and share_link.expires_at <= timezone.now():
            raise Http404
        if share_link.audit_run.status != AuditRun.Status.COMPLETED:
            raise Http404
        share_link.access_count += 1
        share_link.last_accessed_at = timezone.now()
        share_link.save(update_fields=["access_count", "last_accessed_at", "updated_at"])
        return share_link

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        audit_run = self.object.audit_run
        summary = audit_run.summary or {}
        context["audit_run"] = audit_run
        context["score_breakdown"] = summary.get("score_breakdown", {})
        context["recommendations"] = (summary.get("featured_recommendations") or summary.get("recommendations", []))[:6]
        context["context_analysis"] = summary.get("context_analysis", {})
        context["issue_summary"] = summary.get("issue_summary", {})
        context["product_modules"] = summary.get("product_modules", [])[:4]
        context["change_report"] = getattr(audit_run, "change_report", None)
        return context


class SharedAuditReportPdfView(DetailView):
    model = AuditShareLink
    slug_field = "token"
    slug_url_kwarg = "token"

    def get_queryset(self):
        return AuditShareLink.objects.select_related("audit_run")

    def get(self, request, *args, **kwargs):
        share_link = self.get_object()
        if share_link.expires_at and share_link.expires_at <= timezone.now():
            raise Http404
        if share_link.audit_run.status != AuditRun.Status.COMPLETED:
            raise Http404
        pdf_bytes = build_audit_report_pdf(share_link.audit_run)
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="shared-audit-report-{share_link.audit_run.pk}.pdf"'
        return response
