from urllib.parse import urlencode, urlparse

from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout, update_session_auth_hash
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.conf import settings
from django.core.cache import cache
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView, TemplateView

from apps.core.site_content import PACKAGES
from apps.leads.billing import (
    BillingError,
    build_action_access_context,
    build_audit_run_access_context,
    build_credit_action_guide,
    can_access_audit_feature,
    can_create_workspace_project,
    get_billing_state,
    get_audit_result_profile,
    get_effective_capabilities,
    get_limited_audit_history,
    get_limited_recommendations,
    record_usage,
    spend_action_credits,
)
from apps.leads.auth import (
    GoogleOAuthError,
    build_google_authorize_url,
    create_google_oauth_state,
    exchange_google_code_for_userinfo,
    get_or_create_user_from_google_profile,
    is_google_oauth_enabled,
)
from apps.leads.forms import (
    AuditRequestForm,
    AccountPasswordForm,
    AccountProfileForm,
    WorkspaceAuditStartForm,
    WorkspaceLoginForm,
    WorkspaceProjectForm,
    WorkspaceSignupForm,
)
from apps.leads.models import ClientProject, UsageRecord
from apps.leads.services import (
    create_workspace_project_for_user,
    create_audit_request_from_form,
    get_workspace_projects,
    get_workspace_project_summaries,
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
from .recommendations import build_audit_summary
from .services import build_cross_module_decision_summary, build_executive_outcome_summary, extract_domain, normalize_url


def _attribute_affiliate_signup(request, user):
    """Best-effort attribution of a new signup to a referring affiliate.

    Reads the ?ref= param or the persisted vrt_ref cookie, then hands off to
    apps.affiliates.services. Always defensive — never block signup if the
    affiliates app fails or isn't installed.
    """
    try:
        from apps.affiliates.middleware import get_referral_slug_from_request
        from apps.affiliates.services import attribute_signup
    except Exception:
        return

    slug = get_referral_slug_from_request(request)
    if not slug:
        return
    try:
        signup_ip = (
            request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
            or request.META.get("REMOTE_ADDR")
        )
        attribute_signup(
            user=user,
            affiliate_slug=slug,
            signup_ip=signup_ip or None,
        )
    except Exception:
        # Attribution failures must never break signup.
        return


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


def _audit_summary_needs_refresh(summary):
    if not isinstance(summary, dict):
        return True
    top_issues = summary.get("top_issues") or []
    quick_wins = summary.get("quick_wins") or []
    featured = summary.get("featured_recommendations") or []
    next_step = summary.get("recommended_next_step") or {}
    return bool(
        (top_issues and "summary" not in top_issues[0])
        or (quick_wins and "summary" not in quick_wins[0])
        or (featured and "page_examples" not in featured[0])
        or (next_step and "checklist" not in next_step)
    )


def _ensure_fresh_audit_summary(audit_run):
    if not audit_run or audit_run.status != AuditRun.Status.COMPLETED:
        return audit_run.summary if audit_run and isinstance(audit_run.summary, dict) else {}
    summary = audit_run.summary if isinstance(audit_run.summary, dict) else {}
    if not _audit_summary_needs_refresh(summary):
        return summary
    summary = build_audit_summary(audit_run)
    audit_run.summary = summary
    audit_run.save(update_fields=["summary", "updated_at"])
    return summary


def _short_workspace_url(url):
    if not url:
        return ""
    parsed = urlparse(url)
    if not parsed.netloc:
        return str(url)
    path = parsed.path.rstrip("/") or "/"
    return f"{parsed.netloc}{path}" if path != "/" else parsed.netloc


def _render_home_with_audit_form(request, form, *, status=400):
    from apps.core.views import HomePageView, build_home_context
    from apps.leads.forms import LeadCaptureForm

    context = build_home_context(
        request,
        lead_form=LeadCaptureForm(),
        audit_form=form,
    )
    return render(request, HomePageView.template_name, context, status=status)


def _get_audit_account_user(request, email=""):
    if getattr(request.user, "is_authenticated", False):
        return request.user
    normalized_email = str(email or "").strip().lower()
    if not normalized_email:
        return None
    return get_user_model().objects.filter(email__iexact=normalized_email).first()


def _get_audit_viewer_user(request, audit_run):
    if not getattr(request.user, "is_authenticated", False):
        return None
    if request.user.is_staff:
        return request.user
    project = getattr(getattr(audit_run, "audit_request", None), "client_project", None)
    if project and project.owner_id == request.user.id:
        return request.user
    return None


def _slice_for_limit(items, limit):
    items = list(items or [])
    if limit is None:
        return items, 0
    return items[:limit], max(len(items) - limit, 0)


def _render_landing_with_audit_form(request, form, *, status=400):
    return render(
        request,
        "tools/free_audit_landing.html",
        {"audit_form": form},
        status=status,
    )


class PublicAuditCreateView(View):
    rate_limit = 3
    rate_window = 900

    def get(self, request, *args, **kwargs):
        return _render_landing_with_audit_form(request, AuditRequestForm(), status=200)

    def post(self, request, *args, **kwargs):
        from_landing = request.POST.get("_source") == "landing"
        ip_address = request.META.get("REMOTE_ADDR", "unknown")
        cache_key = f"rate-limit:{self.__class__.__name__}:{ip_address}"
        attempts = cache.get(cache_key, 0)

        # Bypass rate limit for staff users
        if not request.user.is_staff and attempts >= self.rate_limit:
            messages.error(request, "Too many audit requests. Try again in a few minutes.")
            return redirect("tools:free-seo-audit") if from_landing else redirect("/#audit")

        cache.set(cache_key, attempts + 1, timeout=self.rate_window)

        form = AuditRequestForm(request.POST)
        if not form.is_valid():
            if from_landing:
                return _render_landing_with_audit_form(request, form, status=400)
            return _render_home_with_audit_form(request, form, status=400)

        normalized_start_url = normalize_url(form.cleaned_data["website"])
        normalized_domain = extract_domain(normalized_start_url)
        account_user = _get_audit_account_user(request, form.cleaned_data.get("email", ""))
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

        project = None
        if account_user:
            allowed_project, project_capacity = can_create_workspace_project(
                account_user,
                normalized_domain=normalized_domain,
            )
            if not allowed_project:
                form.add_error(
                    None,
                    project_capacity["blocked_message"] or project_capacity["next_unlock_message"],
                )
                return _render_home_with_audit_form(request, form, status=400)
            project = (
                ClientProject.objects.select_related("latest_audit_run", "audit_request")
                .filter(owner=account_user, normalized_domain=normalized_domain)
                .first()
            )
            audit_access = build_audit_run_access_context(account_user, project=project)
            if settings.AUDIT_TIER_ENFORCEMENT and not audit_access["available"]:
                form.add_error(
                    None,
                    audit_access["blocked_message"] or audit_access["next_unlock_message"],
                )
                return _render_home_with_audit_form(request, form, status=400)

        audit_request = create_audit_request_from_form(form, request=request)
        audit_run = AuditRun.objects.create(
            audit_request=audit_request,
            normalized_domain=normalized_domain or "pending",
            start_url=normalized_start_url,
        )

        if account_user:
            try:
                spend_action_credits(
                    account_user,
                    "audit",
                    project=project,
                    note="Public audit run",
                    reference_key=f"audit-run:{audit_run.pk}",
                    metadata={"audit_run_id": audit_run.pk, "source": "public_audit"},
                )
                record_usage(account_user, UsageRecord.Metric.AUDIT_RUN, quantity=1)
            except BillingError as exc:
                audit_run.delete()
                form.add_error(None, str(exc))
                return _render_home_with_audit_form(request, form, status=400)

        project = sync_client_project_from_audit_run(audit_run)
        if account_user and (not project.owner_id or project.owner_id != account_user.id):
            project.owner = account_user
            project.save(update_fields=["owner", "updated_at"])
        enqueue_public_site_audit(audit_run.pk)
        messages.success(request, "Audit started. We are analyzing the site now.")
        return redirect("tools:audit-result", pk=audit_run.pk)


class AuditResultDetailView(DetailView):
    model = AuditRun
    template_name = "tools/audit_result.html"
    context_object_name = "audit_run"

    def get_queryset(self):
        return AuditRun.objects.select_related("audit_request", "audit_request__client_project").prefetch_related("pages", "issues")

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
        summary = _ensure_fresh_audit_summary(audit_run)
        viewer_user = _get_audit_viewer_user(self.request, audit_run)
        audit_profile = get_audit_result_profile(viewer_user)
        scores = summary.get("scores", {})
        raw_score_breakdown = summary.get("score_breakdown", {})
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
                "key": key,
                "label": label,
                "score": score,
                "offset": small_offset,
                "color": "#16a34a" if score >= 90 else "#ea580c" if score >= 50 else "#dc2626",
                "tone": "strong" if score >= 90 else "warning" if score >= 50 else "critical",
            })
        score_breakdown_keys = audit_profile.get("score_breakdown_keys")
        if score_breakdown_keys:
            score_breakdown = {
                key: raw_score_breakdown[key]
                for key in score_breakdown_keys
                if key in raw_score_breakdown
            }
            gauge_list = [item for item in gauge_list if item["key"] in score_breakdown_keys]
        else:
            score_breakdown = raw_score_breakdown

        context["gauge_list"] = gauge_list
        context["score_breakdown"] = score_breakdown
        visible_recommendations, locked_recommendation_count = get_limited_recommendations(
            recommendations,
            viewer_user,
        )
        recommendation_limit = get_effective_capabilities(viewer_user)["premium_recommendation_limit"]
        if settings.AUDIT_TIER_ENFORCEMENT and recommendation_limit is not None:
            product_modules = product_modules[:recommendation_limit]
        visible_featured_recommendations, featured_locked_count = _slice_for_limit(
            featured_recommendations,
            audit_profile.get("featured_recommendation_limit"),
        )
        featured_root_causes = {
            item.get("root_cause_key")
            for item in visible_featured_recommendations
            if item.get("root_cause_key")
        }
        secondary_recommendations = [
            item
            for item in visible_recommendations
            if item.get("root_cause_key") not in featured_root_causes
        ]
        visible_secondary_recommendations, secondary_locked_count = _slice_for_limit(
            secondary_recommendations,
            audit_profile.get("secondary_recommendation_limit"),
        )
        top_issues, top_issues_locked_count = _slice_for_limit(
            summary.get("top_issues", []),
            audit_profile.get("top_issue_limit"),
        )
        quick_wins, quick_wins_locked_count = _slice_for_limit(
            summary.get("quick_wins", []),
            audit_profile.get("quick_win_limit"),
        )
        performance_metrics, performance_metrics_locked_count = _slice_for_limit(
            summary.get("performance_metrics", []),
            audit_profile.get("performance_metric_limit"),
        )
        technical_pages, hidden_pages_count = _slice_for_limit(
            audit_run.pages.all(),
            audit_profile.get("technical_page_limit"),
        )
        context["recommendations"] = visible_recommendations
        context["featured_recommendations"] = visible_featured_recommendations
        context["secondary_recommendations"] = visible_secondary_recommendations
        context["top_issues"] = top_issues
        context["quick_wins"] = quick_wins
        context["performance_metrics"] = performance_metrics
        context["product_modules"] = product_modules[:4]
        context["custom_work_items"] = custom_work_items if audit_profile.get("show_custom_work_items") else []
        context["packages"] = PACKAGES
        context["audit_tier_enforcement"] = settings.AUDIT_TIER_ENFORCEMENT
        context["pages"] = technical_pages
        context["is_processing"] = audit_run.status in {AuditRun.Status.PENDING, AuditRun.Status.RUNNING}
        context["locked_recommendation_count"] = locked_recommendation_count + featured_locked_count + secondary_locked_count
        context["top_issues_locked_count"] = top_issues_locked_count
        context["quick_wins_locked_count"] = quick_wins_locked_count
        context["performance_metrics_locked_count"] = performance_metrics_locked_count
        context["hidden_pages_count"] = hidden_pages_count
        context["audit_profile"] = audit_profile
        context["diagnosis"] = summary.get("diagnosis", {})
        context["recommended_next_step"] = summary.get("recommended_next_step", {})
        context["captured_context"] = summary.get("captured_context", {})
        context["show_context_analysis"] = audit_profile.get("show_context_analysis") and bool(summary.get("context_analysis"))
        context["show_secondary_recommendations"] = audit_profile.get("show_secondary_recommendations")
        context["show_custom_work_items"] = audit_profile.get("show_custom_work_items") and bool(custom_work_items)
        context["show_technical_footprint"] = audit_profile.get("technical_page_limit") is None or audit_profile.get("technical_page_limit", 0) > 0
        context["viewer_has_workspace"] = bool(viewer_user)
        context["shell_theme"] = "shell-light"
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
        context["page_title"] = f"Agency Audit | {audit_run.normalized_domain}"
        context["meta_description"] = f"Internal agency audit workspace for {audit_run.normalized_domain}."
        context["meta_robots"] = "noindex, nofollow"
        context["canonical_url"] = self.request.build_absolute_uri(self.request.path)
        context["shell_theme"] = "shell-light"

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
        context["page_title"] = f"{project.name} Project Dashboard | VRT SPACE AGENCY"
        context["meta_description"] = f"Internal project dashboard for {project.normalized_domain or project.website}."
        context["meta_robots"] = "noindex, nofollow"
        context["canonical_url"] = self.request.build_absolute_uri(self.request.path)
        context["shell_theme"] = "shell-light"
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
                "shell_theme": "shell-light",
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
                    "shell_theme": "shell-light",
                },
                status=400,
            )

        email = form.cleaned_data["email"]
        password = form.cleaned_data["password"]
        user = get_user_model().objects.create_user(username=email, email=email, password=password)
        login(request, user)
        _attribute_affiliate_signup(request, user)

        if audit_run and audit_run.audit_request_id:
            project = sync_client_project_from_audit_run(audit_run)
            project.owner = user
            project.save(update_fields=["owner", "updated_at"])

        # New users land on the welcome screen first — a warm greeting
        # before we ask for any information.
        return redirect("tools:workspace-welcome")

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
            "shell_theme": "shell-light",
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

        user, created = get_or_create_user_from_google_profile(profile)
        login(request, user)
        if created:
            _attribute_affiliate_signup(request, user)
        self._link_audit_to_user(request, user)
        self._clear_google_session(request)
        # New users go through onboarding; returning users go to dashboard
        if created:
            return redirect("tools:workspace-onboarding")
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


class AccountDashboardView(LoginRequiredMixin, View):
    template_name = "tools/account_dashboard.html"

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self._build_context(request))

    def _build_context(self, request, *, profile_form=None, password_form=None):
        from apps.leads.billing import get_topup_packs

        billing_state = get_billing_state(request.user)
        subscription = billing_state["subscription"]
        topup_packs = [pack for pack in get_topup_packs() if pack.get("stripe_price_id")]
        return {
            "profile_form": profile_form or AccountProfileForm(instance=request.user),
            "password_form": password_form or AccountPasswordForm(user=request.user),
            "billing_state": billing_state,
            "current_subscription": subscription,
            "workspace_count": len(get_workspace_projects(request.user)),
            "topup_packs": topup_packs,
            "page_title": "Account | VRT SPACE AGENCY",
            "meta_description": "Personal account settings, billing, and security controls.",
            "meta_robots": "noindex, nofollow",
            "canonical_url": request.build_absolute_uri(request.path),
            "shell_theme": "shell-light",
        }


class AccountProfileUpdateView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        form = AccountProfileForm(request.POST, instance=request.user)
        if not form.is_valid():
            view = AccountDashboardView()
            return render(
                request,
                view.template_name,
                view._build_context(request, profile_form=form),
                status=400,
            )
        form.save()
        messages.success(request, "Account profile updated.")
        return redirect("tools:account-dashboard")


class AccountPasswordUpdateView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        form = AccountPasswordForm(user=request.user, data=request.POST)
        if not form.is_valid():
            view = AccountDashboardView()
            return render(
                request,
                view.template_name,
                view._build_context(request, password_form=form),
                status=400,
            )
        user = form.save()
        update_session_auth_hash(request, user)
        messages.success(request, "Password updated.")
        return redirect("tools:account-dashboard")


class WorkspaceDemoView(TemplateView):
    """Public sample workspace — no login required. Shows hardcoded demo data."""
    template_name = "tools/workspace_demo.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["page_title"] = "Sample Workspace | VRT SPACE AGENCY"
        ctx["meta_robots"] = "noindex, nofollow"
        ctx["shell_theme"] = "shell-light"
        ctx["demo_domain"] = "example-agency.com"
        ctx["demo_aeo_score"] = 67
        ctx["demo_audit_score"] = 84
        ctx["demo_score_delta"] = 8
        ctx["demo_citation_count"] = 4
        ctx["demo_engines"] = ["ChatGPT", "Gemini", "Perplexity"]
        ctx["demo_pages_crawled"] = 48
        ctx["demo_aeo_scores"] = {
            "visibility": 72,
            "entity": 65,
            "structure": 58,
            "completeness": 73,
        }
        ctx["demo_competitors"] = [
            {"domain": "competitor-a.com", "aeo_score": 81},
            {"domain": "competitor-b.com", "aeo_score": 74},
            {"domain": "competitor-c.com", "aeo_score": 52},
        ]
        ctx["demo_opportunities"] = [
            "Ranks #3 in search for 'AI SEO tools' but not cited by ChatGPT or Gemini.",
            "Homepage missing FAQ schema — reduces eligibility for AI Overviews.",
            "Core topic cluster 'answer engine optimization' has no dedicated page.",
        ]
        return ctx


class WorkspaceDashboardView(LoginRequiredMixin, DetailView):
    model = ClientProject
    template_name = "tools/workspace_dashboard.html"
    context_object_name = "project"

    def get(self, request, *args, **kwargs):
        # Hard gate: users without any project must complete step 1 of onboarding
        has_project = ClientProject.objects.filter(owner=request.user).exists()
        if not has_project:
            return redirect("tools:workspace-onboarding")
        return super().get(request, *args, **kwargs)

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
        latest_generated_content = None
        content_draft_count = 0
        if getattr(project, "pk", None):
            from apps.content.models import GeneratedContent

            content_qs = GeneratedContent.objects.filter(project=project)
            generated_content_count = content_qs.count()
            content_draft_count = generated_content_count
            latest_generated_content = content_qs.order_by("-created_at").first()
        latest_audit = getattr(project, "latest_audit_run", None)
        latest_summary = _ensure_fresh_audit_summary(latest_audit)
        latest_seo_snapshot = project.seo_snapshots.order_by("-created_at").first() if getattr(project, "pk", None) else None
        latest_aeo_audit = project.aeo_audits.order_by("-created_at").first() if getattr(project, "pk", None) else None
        # SEO campaign/execution counts for the Command Card
        seo_active_campaign_count = 0
        seo_execution_item_count = 0
        if latest_seo_snapshot and getattr(project, "pk", None):
            try:
                from apps.seo.models import SEOCampaign
                seo_active_campaign_count = SEOCampaign.objects.filter(
                    project=project
                ).exclude(status="completed").count()
                # Execution items live in the snapshot JSON
                snap_data = latest_seo_snapshot.data if hasattr(latest_seo_snapshot, "data") else {}
                if isinstance(snap_data, dict):
                    seo_execution_item_count = len(snap_data.get("execution_queue", []))
            except Exception:
                pass
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
        fix_queue_recommendations = (latest_summary.get("featured_recommendations") or recommendations[:6])[:4]
        issue_summary = latest_summary.get("issue_summary", {}) if isinstance(latest_summary, dict) else {}
        audit_issue_total = issue_summary.get("total", 0) or len(fix_queue_recommendations)
        workspace_fix_queue = []
        for recommendation in fix_queue_recommendations:
            page_examples = list(recommendation.get("page_examples") or [])
            if recommendation.get("page_url") and recommendation["page_url"] not in page_examples:
                page_examples.insert(0, recommendation["page_url"])
            page_count = recommendation.get("affected_pages_count") or len(page_examples) or recommendation.get("category_issue_count") or 0
            workspace_fix_queue.append(
                {
                    **recommendation,
                    "display_urls": [_short_workspace_url(url) for url in page_examples[:3]],
                    "display_page_count": page_count,
                    "display_steps": list(recommendation.get("technical_steps") or [])[:3],
                }
            )

        workspace_modules = [
            {
                "label": "Audit",
                "value": f"{latest_audit.overall_score}/100" if latest_audit else "Required",
                "summary": (
                    f"{audit_issue_total} grouped issue{'s' if audit_issue_total != 1 else ''} are waiting in the current fix queue."
                    if latest_audit
                    else "Run the first audit to unlock the rest of the workspace."
                ),
                "meta": latest_audit.created_at.strftime("%b %d, %Y") if latest_audit else "Needs first run",
                "href": reverse("tools:audit-result", args=[latest_audit.pk]) if latest_audit else "#start-audit",
                "cta_label": "Open audit" if latest_audit else "Run first audit",
                "tone": "audit",
            },
            {
                "label": "SEO",
                "value": (
                    f"{seo_active_campaign_count} active"
                    if latest_seo_snapshot
                    else ("Ready to run" if latest_audit else "Waiting on audit")
                ),
                "summary": (
                    f"{seo_execution_item_count} execution item{'s' if seo_execution_item_count != 1 else ''} mapped across current SEO work."
                    if latest_seo_snapshot
                    else ("Use the audit base to benchmark competitors and map search gaps." if latest_audit else "Audit must finish before SEO can open.")
                ),
                "meta": latest_seo_snapshot.created_at.strftime("%b %d, %Y") if latest_seo_snapshot else "",
                "href": reverse("seo:workspace-seo") if latest_audit else "#start-audit",
                "cta_label": "Open SEO" if latest_audit else "Start with audit",
                "tone": "seo",
            },
            {
                "label": "AI Visibility",
                "value": (
                    f"{latest_aeo_audit.overall_score}/100"
                    if latest_aeo_audit and latest_aeo_audit.overall_score is not None
                    else ("Ready to run" if latest_audit else "Waiting on audit")
                ),
                "summary": (
                    "Track where AI chatbots cite you, check answer readiness, and fix the gaps that block AI citations."
                    if latest_audit
                    else "Audit must finish before AI Visibility can open."
                ),
                "meta": latest_aeo_audit.created_at.strftime("%b %d, %Y") if latest_aeo_audit else "",
                "href": reverse("aeo:workspace-aeo") if latest_audit else "#start-audit",
                "cta_label": "Open AI Visibility" if latest_audit else "Start with audit",
                "tone": "aeo",
            },
        ]
        if latest_generated_content or content_draft_count:
            workspace_modules.append(
                {
                    "label": "Content support",
                    "value": f"{content_draft_count} draft{'s' if content_draft_count != 1 else ''}",
                    "summary": "Generated drafts stay secondary to Audit, SEO, and AEO, and only appear here when there is work ready.",
                    "meta": latest_generated_content.created_at.strftime("%b %d, %Y") if latest_generated_content else "",
                    "href": reverse("content:workspace-content"),
                    "cta_label": "Open content",
                    "tone": "content",
                }
            )
        latest_share_link = (
            AuditShareLink.objects.filter(audit_run=latest_audit).order_by("-created_at").first()
            if latest_audit
            else None
        )
        share_allowed, _ = can_access_audit_feature(self.request.user, "stakeholder_sharing_enabled")
        export_allowed, _ = can_access_audit_feature(self.request.user, "export_reports_enabled")
        email_allowed, _ = can_access_audit_feature(self.request.user, "email_reports_enabled")
        decision_summary = build_cross_module_decision_summary(
            project,
            latest_audit=latest_audit,
            latest_seo_snapshot=latest_seo_snapshot,
            latest_aeo_audit=latest_aeo_audit,
            seo_active_campaign_count=seo_active_campaign_count,
            seo_execution_item_count=seo_execution_item_count,
            content_draft_count=content_draft_count,
            audit_summary=latest_summary,
            change_report=latest_change_report,
        )
        context["latest_audit"] = latest_audit
        context["audit_history"] = audit_history
        context["audit_history_with_delta"] = audit_history_with_delta
        context["score_breakdown"] = latest_summary.get("score_breakdown", {})
        context["recommendations"] = recommendations
        context["fix_queue_recommendations"] = workspace_fix_queue
        context["latest_generated_content"] = latest_generated_content
        context["content_draft_count"] = content_draft_count
        context["seo_active_campaign_count"] = seo_active_campaign_count
        context["seo_execution_item_count"] = seo_execution_item_count
        context["audit_issue_total"] = audit_issue_total
        context["workspace_modules"] = workspace_modules
        context["decision_summary"] = decision_summary
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

        from apps.leads.credit_alerts import get_alert_band, get_credit_usage_percentage

        credit_usage_pct = get_credit_usage_percentage(billing_state["credit_overview"])
        context["credit_usage_pct"] = credit_usage_pct
        context["credit_alert_band"] = get_alert_band(credit_usage_pct)

        # Executive outcome summary — plain-language workspace-state overview
        _seo_campaigns_qs = (
            project.seo_campaigns.prefetch_related("edit_items")
            if getattr(project, "pk", None)
            else []
        )
        _backlink_prospect_count = (
            project.backlink_prospects.count()
            if getattr(project, "pk", None)
            else 0
        )
        context["executive_summary"] = build_executive_outcome_summary(
            project,
            latest_audit=latest_audit,
            previous_audit=(
                audit_history_with_delta[1]["audit"]
                if audit_history_with_delta and len(audit_history_with_delta) > 1
                else None
            ),
            change_report=latest_change_report,
            seo_campaigns=_seo_campaigns_qs,
            content_draft_count=content_draft_count,
            backlink_prospect_count=_backlink_prospect_count,
            credit_usage_pct=credit_usage_pct,
        )
        context["credit_action_guide"] = (
            build_credit_action_guide(project, self.request.user)
            if getattr(project, "pk", None)
            else []
        )
        context["audit_export_action"] = (
            build_action_access_context(
                self.request.user,
                "export",
                project=project,
                feature_name="export_reports_enabled",
                label="Audit exports",
            )
            if getattr(project, "pk", None)
            else {}
        )
        context["audit_share_action"] = (
            build_action_access_context(
                self.request.user,
                "share",
                project=project,
                feature_name="stakeholder_sharing_enabled",
                label="Stakeholder sharing",
            )
            if getattr(project, "pk", None)
            else {}
        )
        context["billing_plans"] = billing_state["plans"]
        context["audit_schedule"] = schedule
        context["latest_change_report"] = latest_change_report
        context["generated_content_count"] = generated_content_count
        context["latest_seo_snapshot"] = latest_seo_snapshot
        context["latest_aeo_audit"] = latest_aeo_audit
        context["aeo_citation_count"] = (
            latest_aeo_audit.visibility_snapshots.filter(answer_present=True).count()
            if latest_aeo_audit else 0
        )
        if latest_aeo_audit:
            from collections import defaultdict
            _engine_labels = {
                "chatgpt": "ChatGPT", "gemini": "Gemini", "perplexity": "Perplexity",
                "google_aio": "Google AI Overviews", "claude": "Claude", "copilot": "Bing Copilot",
            }
            _eng_data = defaultdict(lambda: {"total": 0, "cited": 0})
            for _snap in latest_aeo_audit.visibility_snapshots.all():
                _eng_data[_snap.engine]["total"] += 1
                if _snap.answer_present:
                    _eng_data[_snap.engine]["cited"] += 1
            _breakdown = []
            for _eng, _d in _eng_data.items():
                _pct = round(100 * _d["cited"] / _d["total"]) if _d["total"] else 0
                _breakdown.append({
                    "engine": _eng,
                    "label": _engine_labels.get(_eng, _eng.replace("_", " ").title()),
                    "pct": _pct, "cited": _d["cited"], "total": _d["total"],
                })
            context["engine_breakdown"] = sorted(_breakdown, key=lambda x: -x["pct"])
        else:
            context["engine_breakdown"] = []
        # Tracked prompts count — used by the activation checklist.
        if getattr(project, "pk", None):
            from apps.aeo.models import TrackedPrompt
            context["tracked_prompt_count"] = TrackedPrompt.objects.filter(
                project=project, is_active=True
            ).count()
        else:
            context["tracked_prompt_count"] = 0

        # Pre-compute activation checklist progress so the template doesn't
        # need to do arithmetic on conditional booleans.
        _act_steps = [
            bool(latest_audit),
            bool(latest_aeo_audit),
            bool(context["tracked_prompt_count"]),
            bool(latest_seo_snapshot),
            bool(schedule),
        ]
        _done = sum(1 for s in _act_steps if s)
        _total = len(_act_steps)
        context["activation_done_count"] = _done
        context["activation_total_count"] = _total
        context["activation_progress_pct"] = round(100 * _done / _total) if _total else 0
        context["activation_complete"] = _done == _total
        context["audit_score_delta"] = (
            audit_history_with_delta[0]["delta"]
            if audit_history_with_delta and audit_history_with_delta[0]["delta"] is not None
            else None
        )
        context["latest_share_link"] = latest_share_link
        context["latest_share_url"] = build_absolute_app_url(f"/share/audits/{latest_share_link.token}/") if latest_share_link else ""
        context["share_reports_allowed"] = share_allowed
        context["export_reports_allowed"] = export_allowed
        context["email_reports_allowed"] = email_allowed
        context["workspace_projects"] = get_workspace_projects(self.request.user)
        context["workspace_project_summaries"] = get_workspace_project_summaries(self.request.user)
        context["page_title"] = f"{project.name if getattr(project, 'pk', None) else 'Workspace'} | VRT SPACE AGENCY"
        context["meta_description"] = "Workspace overview for audits, SEO, AEO, content, credits, and rerun progress."
        context["meta_robots"] = "noindex, nofollow"
        context["canonical_url"] = self.request.build_absolute_uri(self.request.path)
        context["shell_theme"] = "shell-light"
        context["project_form"] = WorkspaceProjectForm(
            prefix="project",
            initial={
                "business_type": getattr(project, "business_type", "") if getattr(project, "pk", None) else "",
                "business_subtype": getattr(project, "business_subtype", "") if getattr(project, "pk", None) else "",
                "target_audience": getattr(project, "target_audience", "") if getattr(project, "pk", None) else "",
                "location_mode": getattr(project, "location_mode", "targeted") if getattr(project, "pk", None) else "targeted",
                "location_country": getattr(project, "location_country", "") if getattr(project, "pk", None) else "",
                "location_scope": getattr(project, "location_scope", "") if getattr(project, "pk", None) else "",
                "location_area": getattr(project, "location_area", "") if getattr(project, "pk", None) else "",
                "location": getattr(project, "location", "") if getattr(project, "pk", None) else "",
                "target_goal": getattr(project, "target_goal", "") if getattr(project, "pk", None) else "",
                "primary_service": getattr(project, "primary_service", "") if getattr(project, "pk", None) else "",
            }
        )
        context["audit_start_form"] = WorkspaceAuditStartForm(
            prefix="audit",
            initial={
                "email": self.request.user.email,
                "company_name": project.name if getattr(project, "pk", None) else "",
                "website": getattr(project, "website", "") if getattr(project, "pk", None) else "",
                "business_type": getattr(project, "business_type", "") if getattr(project, "pk", None) else "",
                "business_subtype": getattr(project, "business_subtype", "") if getattr(project, "pk", None) else "",
                "target_audience": getattr(project, "target_audience", "") if getattr(project, "pk", None) else "",
                "location_mode": getattr(project, "location_mode", "targeted") if getattr(project, "pk", None) else "targeted",
                "location_country": getattr(project, "location_country", "") if getattr(project, "pk", None) else "",
                "location_scope": getattr(project, "location_scope", "") if getattr(project, "pk", None) else "",
                "location_area": getattr(project, "location_area", "") if getattr(project, "pk", None) else "",
                "location": getattr(project, "location", "") if getattr(project, "pk", None) else "",
                "target_goal": getattr(project, "target_goal", "") if getattr(project, "pk", None) else "",
                "primary_service": getattr(project, "primary_service", "") if getattr(project, "pk", None) else "",
            }
        )
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


class WorkspaceProjectCreateView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        form = WorkspaceProjectForm(request.POST, prefix="project")
        if not form.is_valid():
            dashboard_view = WorkspaceDashboardView()
            dashboard_view.request = request
            dashboard_view.object = dashboard_view.get_object()
            context = dashboard_view.get_context_data(object=dashboard_view.object)
            context["project_form"] = form
            return dashboard_view.render_to_response(context, status=400)

        normalized_start_url = normalize_url(form.cleaned_data["website"])
        normalized_domain = extract_domain(normalized_start_url)
        allowed_project, project_capacity = can_create_workspace_project(
            request.user,
            normalized_domain=normalized_domain,
        )
        if not allowed_project:
            form.add_error(
                None,
                project_capacity["blocked_message"] or project_capacity["next_unlock_message"],
            )
            dashboard_view = WorkspaceDashboardView()
            dashboard_view.request = request
            dashboard_view.object = dashboard_view.get_object()
            context = dashboard_view.get_context_data(object=dashboard_view.object)
            context["project_form"] = form
            return dashboard_view.render_to_response(context, status=400)

        project, created = create_workspace_project_for_user(
            request.user,
            name=form.cleaned_data["name"],
            website=form.cleaned_data["website"],
            business_type=form.cleaned_data.get("business_type", ""),
            business_subtype=form.cleaned_data.get("business_subtype", ""),
            location=form.cleaned_data.get("location", ""),
            location_mode=form.cleaned_data.get("location_mode", "targeted"),
            location_country=form.cleaned_data.get("location_country", ""),
            location_scope=form.cleaned_data.get("location_scope", ""),
            location_area=form.cleaned_data.get("location_area", ""),
            target_goal=form.cleaned_data.get("target_goal", ""),
            primary_service=form.cleaned_data.get("primary_service", ""),
            target_audience=form.cleaned_data.get("target_audience", ""),
        )
        set_active_workspace_project(request, project)
        if created:
            messages.success(request, f"{project.name} is ready. Run an audit when you want a fresh crawl, or move straight into SEO, AEO, or content setup.")
        else:
            messages.info(request, f"{project.name} already existed, so the workspace reopened that project instead of creating a duplicate.")
        return redirect("tools:workspace-dashboard")


class WorkspaceAuditStartView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        active_project = resolve_workspace_project(request, request.user)
        form = WorkspaceAuditStartForm(request.POST, prefix="audit")
        if not form.is_valid():
            dashboard_view = WorkspaceDashboardView()
            dashboard_view.request = request
            dashboard_view.object = dashboard_view.get_object()
            context = dashboard_view.get_context_data(object=dashboard_view.object)
            context["audit_start_form"] = form
            return dashboard_view.render_to_response(context, status=400)

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

        matching_project = (
            ClientProject.objects.select_related("latest_audit_run", "audit_request")
            .filter(owner=request.user, normalized_domain=normalized_domain)
            .first()
        )
        allowed_project, project_capacity = can_create_workspace_project(
            request.user,
            normalized_domain=normalized_domain,
        )
        if not allowed_project:
            form.add_error(
                None,
                project_capacity["blocked_message"] or project_capacity["next_unlock_message"],
            )
            dashboard_view = WorkspaceDashboardView()
            dashboard_view.request = request
            dashboard_view.object = dashboard_view.get_object()
            context = dashboard_view.get_context_data(object=dashboard_view.object)
            context["audit_start_form"] = form
            return dashboard_view.render_to_response(context, status=400)

        cost_project = matching_project
        if cost_project is None and active_project and active_project.normalized_domain == normalized_domain:
            cost_project = active_project
        audit_access = build_audit_run_access_context(request.user, project=cost_project)
        if settings.AUDIT_TIER_ENFORCEMENT and not audit_access["available"]:
            form.add_error(
                None,
                audit_access["blocked_message"] or audit_access["next_unlock_message"],
            )
            dashboard_view = WorkspaceDashboardView()
            dashboard_view.request = request
            dashboard_view.object = dashboard_view.get_object()
            context = dashboard_view.get_context_data(object=dashboard_view.object)
            context["audit_start_form"] = form
            return dashboard_view.render_to_response(context, status=400)

        audit_request = create_audit_request_from_form(form, request=request)
        audit_run = AuditRun.objects.create(
            audit_request=audit_request,
            normalized_domain=normalized_domain or "pending",
            start_url=normalized_start_url,
        )
        try:
            spend_action_credits(
                request.user,
                "audit",
                project=cost_project,
                note="Workspace audit run",
                reference_key=f"audit-run:{audit_run.pk}",
                metadata={"audit_run_id": audit_run.pk, "source": "workspace_audit"},
            )
            record_usage(request.user, UsageRecord.Metric.AUDIT_RUN, quantity=1)
        except BillingError as exc:
            audit_run.delete()
            form.add_error(None, str(exc))
            dashboard_view = WorkspaceDashboardView()
            dashboard_view.request = request
            dashboard_view.object = dashboard_view.get_object()
            context = dashboard_view.get_context_data(object=dashboard_view.object)
            context["audit_start_form"] = form
            return dashboard_view.render_to_response(context, status=400)

        project = sync_client_project_from_audit_run(audit_run)
        update_fields = ["updated_at"]
        if not project.owner_id or project.owner_id != request.user.id:
            project.owner = request.user
            update_fields.append("owner")
        if active_project and getattr(active_project, "pk", None) and active_project.owner_id == request.user.id and not project.audit_request_id:
            project.audit_request = audit_request
            update_fields.append("audit_request")
        project.save(update_fields=update_fields)
        set_active_workspace_project(request, project)
        enqueue_public_site_audit(audit_run.pk)
        messages.success(request, "Audit started. The workspace will attach to this audit automatically as the results are saved.")
        return redirect("tools:audit-result", pk=audit_run.pk)


class AuditReportPdfView(DetailView):
    model = AuditRun

    def get_queryset(self):
        return AuditRun.objects.prefetch_related("pages", "issues")

    def get(self, request, *args, **kwargs):
        audit_run = self.get_object()
        if audit_run.status != AuditRun.Status.COMPLETED:
            return HttpResponse("Audit report is not available until the audit completes.", status=409)

        viewer = request.user if request.user.is_authenticated else None
        viewer_profile = get_audit_result_profile(viewer)
        if not viewer_profile.get("pdf_export_enabled", False):
            return redirect(f"{reverse('tools:audit-result', kwargs={'pk': audit_run.pk})}?pdf_locked=1")

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
        audit_run = self.get_workspace_audit(kwargs["pk"])
        action = build_action_access_context(
            request.user,
            "export",
            project=getattr(getattr(audit_run, "audit_request", None), "client_project", None),
            feature_name="export_reports_enabled",
            label="Audit exports",
        )
        if settings.AUDIT_TIER_ENFORCEMENT and not action["available"]:
            return JsonResponse({"error": action["blocked_message"] or action["next_unlock_message"]}, status=403)
        if audit_run.status != AuditRun.Status.COMPLETED:
            return JsonResponse({"error": "Exports are only available after the audit completes."}, status=409)
        self.ensure_completed_audit(audit_run)
        try:
            _entry, estimate = spend_action_credits(
                request.user,
                "export",
                project=getattr(getattr(audit_run, "audit_request", None), "client_project", None),
                note="Audit JSON export",
                reference_key=f"audit-export-json:{audit_run.pk}",
                metadata={"audit_run_id": audit_run.pk, "format": "json"},
                reuse_reference=True,
            )
            if not estimate.get("reused_existing_charge"):
                record_usage(request.user, UsageRecord.Metric.EXPORT)
        except BillingError as exc:
            return JsonResponse({"error": str(exc)}, status=403)
        return JsonResponse(build_audit_export_payload(audit_run), status=200)


class WorkspaceAuditExportCsvView(WorkspaceAuditAccessMixin, View):
    def get(self, request, *args, **kwargs):
        audit_run = self.get_workspace_audit(kwargs["pk"])
        action = build_action_access_context(
            request.user,
            "export",
            project=getattr(getattr(audit_run, "audit_request", None), "client_project", None),
            feature_name="export_reports_enabled",
            label="Audit exports",
        )
        if settings.AUDIT_TIER_ENFORCEMENT and not action["available"]:
            return HttpResponse(action["blocked_message"] or action["next_unlock_message"], status=403)
        if audit_run.status != AuditRun.Status.COMPLETED:
            return HttpResponse("Exports are only available after the audit completes.", status=409)
        self.ensure_completed_audit(audit_run)
        try:
            _entry, estimate = spend_action_credits(
                request.user,
                "export",
                project=getattr(getattr(audit_run, "audit_request", None), "client_project", None),
                note="Audit CSV export",
                reference_key=f"audit-export-csv:{audit_run.pk}",
                metadata={"audit_run_id": audit_run.pk, "format": "csv"},
                reuse_reference=True,
            )
            if not estimate.get("reused_existing_charge"):
                record_usage(request.user, UsageRecord.Metric.EXPORT)
        except BillingError as exc:
            return HttpResponse(str(exc), status=403)
        response = HttpResponse(build_audit_csv_export(audit_run), content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="audit-export-{audit_run.pk}.csv"'
        return response


class WorkspaceAuditShareCreateView(WorkspaceAuditAccessMixin, View):
    def post(self, request, *args, **kwargs):
        audit_run = self.get_workspace_audit(kwargs["pk"])
        action = build_action_access_context(
            request.user,
            "share",
            project=getattr(getattr(audit_run, "audit_request", None), "client_project", None),
            feature_name="stakeholder_sharing_enabled",
            label="Stakeholder sharing",
        )
        if settings.AUDIT_TIER_ENFORCEMENT and not action["available"]:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"error": action["blocked_message"] or action["next_unlock_message"]}, status=403)
            raise Http404

        if audit_run.status != AuditRun.Status.COMPLETED:
            return JsonResponse({"error": "Shared reports are only available after the audit completes."}, status=409)
        self.ensure_completed_audit(audit_run)
        try:
            spend_action_credits(
                request.user,
                "share",
                project=getattr(getattr(audit_run, "audit_request", None), "client_project", None),
                note="Audit stakeholder share link",
                reference_key=f"audit-share:{audit_run.pk}",
                metadata={"audit_run_id": audit_run.pk},
                reuse_reference=True,
            )
        except BillingError as exc:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"error": str(exc)}, status=403)
            messages.error(request, str(exc))
            return redirect("tools:workspace-dashboard")
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
        context["shell_theme"] = "shell-light"
        context["page_title"] = f"{audit_run.normalized_domain} Audit Report | VRT SPACE AGENCY"
        context["meta_description"] = (
            f"Shared audit report for {audit_run.normalized_domain} with score breakdown, recommendations, and next steps."
        )
        context["meta_robots"] = "noindex, nofollow"
        context["score_breakdown"] = summary.get("score_breakdown", {})
        # Apply the project owner's plan profile so a shared report reflects
        # the tier of whoever created it — a Free owner's share shows Free-level
        # detail, a Growth owner's stays rich. Falls back to the Free profile
        # when no owner can be resolved (orphaned / pre-account audits).
        owner_project = (
            ClientProject.objects.filter(latest_audit_run=audit_run)
            .select_related("owner")
            .first()
        )
        if owner_project is None and audit_run.audit_request_id:
            owner_project = (
                ClientProject.objects.filter(audit_request_id=audit_run.audit_request_id)
                .select_related("owner")
                .first()
            )
        owner = getattr(owner_project, "owner", None)
        audit_profile = get_audit_result_profile(owner)
        recommendations = summary.get("featured_recommendations") or summary.get("recommendations", [])
        visible_recommendations, _ = _slice_for_limit(
            recommendations,
            audit_profile.get("featured_recommendation_limit") or 6,
        )
        context["recommendations"] = visible_recommendations
        context["context_analysis"] = summary.get("context_analysis", {})
        context["issue_summary"] = summary.get("issue_summary", {})
        context["product_modules"] = summary.get("product_modules", [])[:4]
        context["change_report"] = getattr(audit_run, "change_report", None)
        return context


# ---------------------------------------------------------------------------
# P2 – Guided Onboarding Wizard
# ---------------------------------------------------------------------------

def _resolve_onboarding_step(user):
    """Return (step, ctx) describing where the user is in the onboarding flow.

    step=1  No project yet — enter website URL.
    step=2  Project exists, no completed audit — run first audit.
    step=3  Completed audit exists, no competitors saved — add competitors.
    step=0  All done — wizard complete.
    """
    project = (
        ClientProject.objects.filter(owner=user)
        .select_related("latest_audit_run", "audit_request")
        .order_by("-created_at")
        .first()
    )

    if not project:
        return 1, {"project": None, "running_audit": None, "completed_audit": None}

    completed_audit = None
    running_audit = None

    # Prefer audits linked via audit_request (canonical path)
    if project.audit_request_id:
        completed_audit = (
            AuditRun.objects.filter(
                audit_request__client_project=project,
                status=AuditRun.Status.COMPLETED,
            )
            .order_by("-created_at")
            .first()
        )
        running_audit = (
            AuditRun.objects.filter(
                audit_request__client_project=project,
                status__in={AuditRun.Status.PENDING, AuditRun.Status.RUNNING},
            )
            .order_by("-created_at")
            .first()
        )

    # Fallback: project.latest_audit_run (pre-existing projects that already ran an audit)
    if not completed_audit and project.latest_audit_run and project.latest_audit_run.status == AuditRun.Status.COMPLETED:
        completed_audit = project.latest_audit_run

    if not completed_audit:
        return 2, {"project": project, "running_audit": running_audit, "completed_audit": None}

    # Competitors live on the linked AuditRequest, not on the project itself.
    existing_competitors = []
    if project.audit_request_id:
        existing_competitors = list(project.audit_request.competitor_urls or [])
    if not existing_competitors:
        return 3, {"project": project, "running_audit": None, "completed_audit": completed_audit}

    return 0, {"project": project, "running_audit": None, "completed_audit": completed_audit}


class WorkspaceOnboardingCompleteView(LoginRequiredMixin, View):
    """Tasteful 'you're set' celebration after onboarding finishes.

    Shows the AI Visibility Score, three highest-value next steps, and a
    direct CTA into the workspace. No confetti — just a strong moment of
    arrival before they hit the busy dashboard.
    """

    template_name = "tools/workspace_onboarding_complete.html"

    def get(self, request, *args, **kwargs):
        project = (
            ClientProject.objects.filter(owner=request.user)
            .select_related("latest_audit_run")
            .order_by("-created_at")
            .first()
        )
        if not project:
            return redirect("tools:workspace-onboarding")

        from apps.aeo.models import AEOAudit, TrackedPrompt

        aeo_audit = (
            AEOAudit.objects.filter(project=project)
            .order_by("-created_at").first()
        )
        prompt_count = TrackedPrompt.objects.filter(project=project, is_active=True).count()
        audit_score = project.latest_audit_run.overall_score if project.latest_audit_run else 0
        aeo_score = aeo_audit.overall_score if aeo_audit else 0

        return render(
            request,
            self.template_name,
            {
                "project": project,
                "audit_score": audit_score,
                "aeo_score": aeo_score,
                "prompt_count": prompt_count,
                "page_title": "You're set — VRT SPACE AGENCY",
                "meta_robots": "noindex, nofollow",
                "shell_theme": "shell-light",
            },
        )


class WorkspaceWelcomeView(LoginRequiredMixin, View):
    """Warm 'you're in' page shown immediately after signup.

    Single CTA into the onboarding wizard. Bypasses if the user already has
    a project (no point welcoming them twice).
    """

    template_name = "tools/workspace_welcome.html"

    def get(self, request, *args, **kwargs):
        has_project = ClientProject.objects.filter(owner=request.user).exists()
        if has_project:
            return redirect("tools:workspace-onboarding")
        first_name = (request.user.first_name or request.user.username or "").split("@")[0].strip().title()
        return render(
            request,
            self.template_name,
            {
                "first_name": first_name or "there",
                "page_title": "Welcome to VRT SPACE AGENCY",
                "meta_description": "Set up your AI visibility workspace in 90 seconds.",
                "meta_robots": "noindex, nofollow",
                "shell_theme": "shell-light",
            },
        )


class WorkspaceOnboardingView(LoginRequiredMixin, View):
    """Wizard shell — renders the full onboarding page at the correct step."""

    template_name = "tools/onboarding.html"

    def get(self, request, *args, **kwargs):
        from apps.leads.intake_options import BUSINESS_TYPE_CHOICES

        step, ctx = _resolve_onboarding_step(request.user)
        if step == 0:
            return redirect("tools:workspace-dashboard")

        # Step 3 needs both competitor and prompt suggestions
        extra_ctx = {}
        if step == 3 and ctx.get("project"):
            extra_ctx["competitor_suggestions"] = _get_competitor_suggestions(ctx["project"])
            extra_ctx["prompt_suggestions"] = _get_prompt_suggestions(ctx["project"])

        return render(request, self.template_name, {
            **ctx,
            **extra_ctx,
            "current_step": step,
            "business_type_choices": BUSINESS_TYPE_CHOICES,
            "form_data": {},
            "page_title": "Set Up Your Workspace | VRT SPACE AGENCY",
            "meta_robots": "noindex, nofollow",
            "canonical_url": request.build_absolute_uri(request.path),
            "shell_theme": "shell-light",
        })


class WorkspaceOnboardingStep1View(LoginRequiredMixin, View):
    """Step 1 POST — create the project from the submitted URL + business
    context.  Business type + location are required so the SERP discovery
    that fires at step 3 actually returns relevant competitors instead of
    Instagram / random aggregators.
    """

    def post(self, request, *args, **kwargs):
        from apps.leads.intake_options import BUSINESS_TYPE_CHOICES, BUSINESS_TYPE_LABELS

        website = (request.POST.get("website") or "").strip()
        business_type = (request.POST.get("business_type") or "").strip()
        location = (request.POST.get("location") or "").strip()
        is_htmx = bool(request.headers.get("HX-Request"))

        form_data = {
            "website": website,
            "business_type": business_type,
            "location": location,
        }

        if not website:
            return self._error(request, is_htmx, "Please enter your website URL.", step=1, form_data=form_data)

        if not business_type or business_type not in BUSINESS_TYPE_LABELS:
            return self._error(request, is_htmx, "Pick the business type that best describes you.", step=1, form_data=form_data)

        if not location:
            return self._error(request, is_htmx, "Tell us where you operate — even 'Worldwide' is fine.", step=1, form_data=form_data)

        normalized_start_url = normalize_url(website)
        normalized_domain = extract_domain(normalized_start_url)

        if not normalized_domain:
            return self._error(
                request, is_htmx,
                "That doesn't look like a valid website address — please include the domain, e.g. example.com",
                step=1,
                form_data=form_data,
            )

        allowed, capacity = can_create_workspace_project(request.user, normalized_domain=normalized_domain)
        if not allowed:
            msg = capacity.get("blocked_message") or "Unable to create project — you may have reached your plan limit."
            return self._error(request, is_htmx, msg, step=1, form_data=form_data)

        # 'Worldwide' / 'global' triggers the worldwide mode used elsewhere.
        location_mode = "worldwide" if location.strip().lower() in {"worldwide", "global", "everywhere", "international"} else "targeted"

        project, _ = create_workspace_project_for_user(
            request.user,
            name=normalized_domain,
            website=normalized_start_url,
            business_type=business_type,
            location=location,
            location_mode=location_mode,
        )
        set_active_workspace_project(request, project)

        # Claim an existing audit for this domain if one exists (e.g. user
        # ran /#audit before signing up). Lets the wizard skip step 2 entirely
        # so we don't run a duplicate audit on the same site.
        adopted = _claim_existing_audit_for_project(project, request.user)
        if adopted:
            messages.info(request, "We found your previous audit — reusing it instead of running a duplicate.")
            if is_htmx:
                suggestions = _get_competitor_suggestions(project)
                prompt_suggestions = _get_prompt_suggestions(project)
                return render(request, "tools/onboarding/_step3_competitors.html", {
                    "project": project,
                    "completed_audit": adopted,
                    "competitor_suggestions": suggestions,
                    "prompt_suggestions": prompt_suggestions,
                    "current_step": 3,
                })
            return redirect("tools:workspace-onboarding")

        if is_htmx:
            return render(request, "tools/onboarding/_step2_audit.html", {
                "project": project,
                "running_audit": None,
                "completed_audit": None,
                "current_step": 2,
            })
        return redirect("tools:workspace-onboarding")

    def _error(self, request, is_htmx, message, *, step, form_data=None):
        from apps.leads.intake_options import BUSINESS_TYPE_CHOICES

        if is_htmx:
            return render(request, "tools/onboarding/_step1_site.html", {
                "error": message,
                "current_step": 1,
                "form_data": form_data or {},
                "business_type_choices": BUSINESS_TYPE_CHOICES,
            }, status=422)
        messages.error(request, message)
        return redirect("tools:workspace-onboarding")


def _claim_existing_audit_for_project(project, user):
    """If a completed AuditRun already exists for this domain (e.g. the user
    ran the free `/#audit` flow before signing up), adopt it onto the project
    instead of running a duplicate audit.

    Returns the AuditRun that was adopted, or None.
    """
    if not project or not project.normalized_domain:
        return None
    user_email = (getattr(user, "email", "") or "").strip().lower()

    # Prefer audits whose AuditRequest matches the user's email (most certain
    # ownership signal); fall back to any unowned audit for that domain.
    candidates_qs = (
        AuditRun.objects.filter(
            normalized_domain=project.normalized_domain,
            status=AuditRun.Status.COMPLETED,
        )
        .select_related("audit_request")
        .order_by("-created_at")
    )

    chosen = None
    if user_email:
        chosen = candidates_qs.filter(audit_request__email__iexact=user_email).first()
    if not chosen:
        # Domain-only match — only adopt if the audit isn't already attached
        # to another project owner. (audit_request.client_project is a
        # OneToOneField with related_name="client_project".)
        for run in candidates_qs[:5]:
            existing_project = getattr(getattr(run, "audit_request", None), "client_project", None)
            if existing_project is None or existing_project.pk == project.pk:
                chosen = run
                break

    if not chosen:
        return None

    # Link the AuditRequest + AuditRun to the project if not already linked
    changed = False
    if not project.audit_request_id and chosen.audit_request_id:
        # Make sure no other project already owns this audit_request
        if not ClientProject.objects.filter(audit_request=chosen.audit_request).exclude(pk=project.pk).exists():
            project.audit_request = chosen.audit_request
            changed = True
    if project.latest_audit_run_id != chosen.pk:
        project.latest_audit_run = chosen
        changed = True
    if changed:
        project.save(update_fields=["audit_request", "latest_audit_run", "updated_at"])
    return chosen


class WorkspaceOnboardingStep2View(LoginRequiredMixin, View):
    """Step 2 POST — kick off the first audit against the user's project,
    OR adopt an existing completed audit (e.g. one created via /#audit
    before signup) and skip ahead to step 3.
    """

    def post(self, request, *args, **kwargs):
        is_htmx = bool(request.headers.get("HX-Request"))
        project = ClientProject.objects.filter(owner=request.user).order_by("-created_at").first()

        if not project:
            return redirect("tools:workspace-onboarding")

        normalized_domain = project.normalized_domain or extract_domain(normalize_url(project.website))
        normalized_start_url = project.website

        # Dedup #1 — adopt a previously-run audit for this domain (anonymous
        # /#audit before signup, or earlier session). Skips straight to step 3.
        adopted = _claim_existing_audit_for_project(project, request.user)
        if adopted:
            messages.info(request, "We found your previous audit — reusing it instead of running a duplicate.")
            suggestions = _get_competitor_suggestions(project)
            prompt_suggestions = _get_prompt_suggestions(project)
            if is_htmx:
                return render(request, "tools/onboarding/_step3_competitors.html", {
                    "project": project,
                    "completed_audit": adopted,
                    "competitor_suggestions": suggestions,
                    "prompt_suggestions": prompt_suggestions,
                    "current_step": 3,
                })
            return redirect("tools:workspace-onboarding")

        # Dedup #2 — if an audit is already in-flight for this domain, attach
        # to it and return the running partial.
        existing_run = (
            AuditRun.objects.filter(
                normalized_domain=normalized_domain,
                status__in={AuditRun.Status.PENDING, AuditRun.Status.RUNNING},
            )
            .order_by("-created_at")
            .first()
        )
        if existing_run:
            if is_htmx:
                return render(request, "tools/onboarding/_step2_running.html", {
                    "project": project,
                    "running_audit": existing_run,
                    "current_step": 2,
                })
            return redirect("tools:workspace-onboarding")

        # Build a minimal AuditRequest linked to the project
        from apps.leads.models import AuditRequest as AuditRequestModel

        audit_request = AuditRequestModel.objects.create(
            email=request.user.email,
            website=normalized_start_url,
            company_name=project.name or normalized_domain,
        )
        if not project.audit_request_id:
            project.audit_request = audit_request
            project.save(update_fields=["audit_request", "updated_at"])

        audit_run = AuditRun.objects.create(
            audit_request=audit_request,
            normalized_domain=normalized_domain or "pending",
            start_url=normalized_start_url,
        )

        # Credit deduction is best-effort — onboarding must never be blocked by credits
        try:
            spend_action_credits(
                request.user,
                "audit",
                project=project,
                note="Onboarding first audit",
                reference_key=f"onboarding-audit:{audit_run.pk}",
                metadata={"audit_run_id": audit_run.pk, "source": "onboarding"},
            )
            record_usage(request.user, UsageRecord.Metric.AUDIT_RUN, quantity=1)
        except BillingError:
            pass

        enqueue_public_site_audit(audit_run.pk)

        if is_htmx:
            return render(request, "tools/onboarding/_step2_running.html", {
                "project": project,
                "running_audit": audit_run,
                "current_step": 2,
            })
        return redirect("tools:workspace-onboarding")


class WorkspaceOnboardingAuditPollView(LoginRequiredMixin, View):
    """HTMX polling endpoint — returns the right partial based on audit status.

    Reliability guarantees:
      - Only the audit's owner can poll it (auth check via project ownership).
      - If the audit has been PENDING/RUNNING > 5 minutes it's considered
        stuck; we surface a "try again" state instead of polling forever.
      - Friendly failure UI with a retry CTA.
    """

    # If an audit has been pending/running this long, assume the worker died
    STUCK_AUDIT_TIMEOUT_SECONDS = 300  # 5 minutes

    def get(self, request, pk, *args, **kwargs):
        from django.utils import timezone as _tz
        from datetime import timedelta as _td

        # Resolve project by user FIRST so we can scope the audit lookup
        project = ClientProject.objects.filter(owner=request.user).order_by("-created_at").first()
        if not project:
            return self._render_failed(request, None, "Workspace not found — please start onboarding again.")

        # Auth: only fetch audits owned by this user's projects
        audit_run = (
            AuditRun.objects.filter(pk=pk)
            .select_related("audit_request")
            .filter(
                # The audit_request links to the user's project (preferred)
                # OR the audit_request was submitted with this user's email
                # (handles claimed audits from before signup)
            )
            .first()
        )
        if not audit_run:
            return self._render_failed(request, project, "Could not find that audit run.")

        # Owner check — audit must be tied to this user (via project or email)
        user_email = (getattr(request.user, "email", "") or "").strip().lower()
        owned = False
        ar = audit_run.audit_request
        if ar:
            # client_project is a reverse OneToOne — access via try/except since
            # accessing a missing reverse OneToOne raises DoesNotExist
            try:
                linked_project = ar.client_project
                if linked_project and linked_project.pk == project.pk:
                    owned = True
            except Exception:
                pass
            if not owned and (ar.email or "").strip().lower() == user_email and user_email:
                owned = True
        if not owned and not request.user.is_staff:
            return self._render_failed(request, project, "You don't have access to that audit.")

        # Stuck-audit detection
        if audit_run.status in (AuditRun.Status.PENDING, AuditRun.Status.RUNNING):
            age = _tz.now() - audit_run.created_at
            if age > _td(seconds=self.STUCK_AUDIT_TIMEOUT_SECONDS):
                # Mark as failed so the user can retry. Don't keep them spinning.
                if audit_run.status != AuditRun.Status.FAILED:
                    audit_run.status = AuditRun.Status.FAILED
                    audit_run.error_message = (
                        audit_run.error_message
                        or "Audit timed out — the background worker may be busy. Please try again."
                    )
                    audit_run.save(update_fields=["status", "error_message", "updated_at"])
                return self._render_failed(
                    request, project,
                    "The audit took longer than expected. This usually means the queue is busy — "
                    "click below to try again.",
                )

        if audit_run.status == AuditRun.Status.FAILED:
            return self._render_failed(
                request, project,
                audit_run.error_message or "The audit failed. Click below to try again.",
            )

        if audit_run.status == AuditRun.Status.COMPLETED:
            # Advance to step 3 — pull SERP competitor suggestions
            suggestions = _get_competitor_suggestions(project)
            prompt_suggestions = _get_prompt_suggestions(project)
            return render(request, "tools/onboarding/_step3_competitors.html", {
                "project": project,
                "completed_audit": audit_run,
                "competitor_suggestions": suggestions,
                "prompt_suggestions": prompt_suggestions,
                "current_step": 3,
            })

        # Still pending/running — keep polling. Tie the cosmetic scan-step
        # animation to real progress signals (pages_crawled + status).
        pages = audit_run.pages_crawled or 0
        if audit_run.status == AuditRun.Status.PENDING:
            progress_step = 0
        elif pages <= 1:
            progress_step = 1
        elif pages <= 3:
            progress_step = 2
        elif pages <= 5:
            progress_step = 3
        elif pages <= 7:
            progress_step = 4
        else:
            progress_step = 5
        # 6 scan phases (indices 0-5); each one accounts for ~16% of the bar.
        # We hold at 90% while the final phase finishes so the bar never reads
        # "100% but still working".
        progress_percent = min(95, 10 + progress_step * 16)
        return render(request, "tools/onboarding/_step2_running.html", {
            "project": project,
            "running_audit": audit_run,
            "current_step": 2,
            "progress_step": progress_step,
            "progress_percent": progress_percent,
            "progress_pages_crawled": pages,
        })

    def _render_failed(self, request, project, message):
        """Render the step-2 kickoff template with an error + retry CTA."""
        return render(request, "tools/onboarding/_step2_audit.html", {
            "project": project,
            "running_audit": None,
            "completed_audit": None,
            "current_step": 2,
            "error": message,
            "show_retry": True,
        })


class WorkspaceOnboardingStep3View(LoginRequiredMixin, View):
    """Step 3 POST — save competitor URLs and complete onboarding."""

    def post(self, request, *args, **kwargs):
        project = ClientProject.objects.filter(owner=request.user).order_by("-created_at").first()
        if not project:
            return redirect("tools:workspace-onboarding")

        raw_competitors = request.POST.getlist("competitors")
        competitor_urls = [
            url.strip() for url in raw_competitors
            if url.strip() and url.strip().startswith(("http://", "https://", "www."))
        ]
        # Accept bare domains too
        competitor_urls += [
            f"https://{url.strip()}"
            for url in raw_competitors
            if url.strip()
            and not url.strip().startswith(("http://", "https://", "www."))
            and "." in url.strip()
        ]
        competitor_urls = list(dict.fromkeys(competitor_urls))[:settings.SEO_COMPETITOR_LIMIT]

        key_topics = request.POST.get("key_topics", "").strip()
        if key_topics:
            project.notes = key_topics
            project.save(update_fields=["notes"])

        # Competitors live on the project's linked AuditRequest.
        if project.audit_request_id:
            project.audit_request.competitor_urls = competitor_urls
            project.audit_request.save(update_fields=["competitor_urls", "updated_at"])
        else:
            # No audit request yet (edge case) — silently skip; user can re-enter later.
            pass

        # Selected prompt suggestions become TrackedPrompts so the Prompts tab
        # is pre-populated when the user lands on the dashboard.
        selected_prompts = request.POST.getlist("selected_prompts")
        clean_prompts = [p.strip() for p in selected_prompts if p.strip()]
        prompts_created = 0
        if clean_prompts:
            from apps.aeo.models import TrackedPrompt
            for prompt_text in clean_prompts[:10]:
                _p, was_created = TrackedPrompt.objects.get_or_create(
                    project=project,
                    prompt=prompt_text[:300],
                    defaults={"intent": TrackedPrompt.Intent.INFORMATIONAL, "is_active": True},
                )
                if was_created:
                    prompts_created += 1

        comp_msg = f"{len(competitor_urls)} competitor{'s' if len(competitor_urls) != 1 else ''} saved"
        prompt_msg = f", {prompts_created} prompts tracked" if prompts_created else ""
        messages.success(request, f"Workspace ready. {comp_msg}{prompt_msg}.")
        # Send first-time finishers to the celebration screen
        return redirect("tools:workspace-onboarding-complete")


def _get_prompt_suggestions(project):
    """Return 6-8 starter prompt suggestions tailored to the project.

    Uses business_type + location + primary_service to generate the kinds of
    AI queries the project's customers are likely to ask. Cheap, local, no
    SERP call needed — these are starting points the user can keep or edit.
    """
    if not project:
        return []

    bt = (project.business_type or "").lower()
    loc = (project.location or "").strip()
    svc = (project.primary_service or "").strip()
    brand = (project.name or "").strip()
    domain = (project.normalized_domain or "").strip()
    loc_phrase = f" in {loc}" if loc and loc.lower() not in ("worldwide", "global", "online") else ""

    suggestions = []
    # Type-specific seed templates
    templates_by_type = {
        "agency": [
            f"best {svc or 'agency'}{loc_phrase}",
            f"top digital marketing agencies{loc_phrase}",
            f"how to choose an {svc or 'agency'}",
            f"affordable {svc or 'agency'} for startups",
            f"{svc or 'agency'} pricing 2026",
        ],
        "saas": [
            f"best {svc or 'SaaS tool'} for small business",
            f"{svc or 'SaaS'} vs competitors",
            f"how to integrate {svc or 'this tool'} with existing systems",
            f"{svc or 'SaaS tool'} pricing comparison",
            f"alternatives to leading {svc or 'SaaS'} platforms",
        ],
        "ecommerce": [
            f"best {svc or 'products'} to buy{loc_phrase}",
            f"where to buy {svc or 'this product'} online",
            f"{svc or 'product'} reviews 2026",
            f"how to choose the right {svc or 'product'}",
        ],
        "healthcare": [
            f"best {svc or 'healthcare provider'}{loc_phrase}",
            f"how to choose a {svc or 'healthcare provider'}",
            f"{svc or 'treatment'} cost{loc_phrase}",
            f"affordable {svc or 'healthcare services'}{loc_phrase}",
        ],
        "real_estate": [
            f"best real estate agents{loc_phrase}",
            f"how to buy a home{loc_phrase}",
            f"real estate market trends{loc_phrase}",
            f"mortgage options{loc_phrase}",
        ],
        "local_service": [
            f"best {svc or 'local service'}{loc_phrase}",
            f"affordable {svc or 'service'}{loc_phrase}",
            f"emergency {svc or 'service'}{loc_phrase}",
            f"how to find a reliable {svc or 'service provider'}{loc_phrase}",
        ],
        "restaurant_food": [
            f"best restaurants{loc_phrase}",
            f"{svc or 'restaurant'} delivery{loc_phrase}",
            f"top food spots{loc_phrase}",
            f"where to eat{loc_phrase}",
        ],
        "hotel": [
            f"best hotels{loc_phrase}",
            f"affordable accommodation{loc_phrase}",
            f"{svc or 'hotel'} reviews{loc_phrase}",
            f"things to do{loc_phrase}",
        ],
        "finance": [
            f"best {svc or 'financial advisor'}{loc_phrase}",
            f"how to invest{loc_phrase}",
            f"{svc or 'financial planning'} for small business",
            f"{svc or 'fintech'} alternatives 2026",
        ],
        "legal": [
            f"best {svc or 'lawyer'}{loc_phrase}",
            f"how to find a {svc or 'lawyer'}{loc_phrase}",
            f"{svc or 'legal service'} cost{loc_phrase}",
        ],
        "education": [
            f"best {svc or 'courses'} for beginners",
            f"how to learn {svc or 'this topic'}",
            f"{svc or 'training'} certification programs",
        ],
    }
    seeds = templates_by_type.get(bt, [
        f"best {svc or 'solution'} for businesses{loc_phrase}",
        f"how to choose a {svc or 'provider'}{loc_phrase}",
        f"{svc or 'this service'} pricing 2026",
        f"top {svc or 'companies'}{loc_phrase}",
    ])

    # Add brand-specific prompts (high-intent)
    if brand:
        seeds.append(f"is {brand} a good choice?")
        seeds.append(f"{brand} reviews")

    # Clean and dedupe
    seen = set()
    for s in seeds:
        s = " ".join(s.split())  # collapse whitespace
        if s.lower() not in seen and len(s) >= 6:
            seen.add(s.lower())
            suggestions.append(s)
    return suggestions[:8]


def _get_competitor_suggestions(project):
    """Return up to SEO_COMPETITOR_LIMIT SERP-discovered competitor URLs.

    Rate-limited: one SERP lookup per onboarding session (cache key per project).
    Falls back silently to an empty list if discovery is unavailable.

    IMPORTANT: discover_serp_competitors expects an SEOProjectProfile-shaped
    object with .primary_service, .business_type, .location attributes. We
    use the real profile when it exists; otherwise we synthesize one from
    the project's own fields so SERP queries are properly targeted (without
    these, we get Instagram + travel aggregators in the results).
    """
    if not project or not getattr(settings, "SERP_DISCOVERY_ENABLED", False):
        return []

    cache_key = f"onboarding-serp-suggestions:{project.pk}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        from apps.seo.discovery import discover_serp_competitors
        from apps.seo.models import SEOProjectProfile
        from types import SimpleNamespace

        profile = SEOProjectProfile.objects.filter(project=project).first()
        if profile is None:
            # Synthesize from ClientProject fields so discovery has the
            # context it needs (service + location + business type).
            profile = SimpleNamespace(
                primary_service=project.primary_service or "",
                business_type=project.business_type or "",
                business_subtype=project.business_subtype or "",
                location=project.location or "",
                target_goal=project.target_goal or "",
                target_audience=project.target_audience or "",
                target_keyword="",
                target_keywords=[],
                metadata={},
            )

        # Bail out if we still don't have enough context — better to show
        # blank slots than irrelevant Instagram/aggregator suggestions.
        if not (profile.primary_service or profile.business_type) or not profile.location:
            cache.set(cache_key, [], timeout=86400)
            return []

        result = discover_serp_competitors(project, profile)
        competitors = (result or {}).get("competitors", [])
        urls = [
            c.get("url") or c.get("domain") or ""
            for c in (competitors or [])
            if isinstance(c, dict)
        ]
        urls = [u for u in urls if u][:settings.SEO_COMPETITOR_LIMIT]
        # Cache for 24 hours — prevents duplicate SERP calls on page refresh
        cache.set(cache_key, urls, timeout=86400)
        return urls
    except Exception:
        return []


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


# ── Phase 13: Agency Dashboard ─────────────────────────────────────────────

class WorkspaceAgencyDashboardView(LoginRequiredMixin, TemplateView):
    """
    Bird's-eye health overview of all client projects for the authenticated user.
    Pure read-only view — all data comes from get_workspace_project_summaries().
    """

    template_name = "tools/workspace_agency_dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        summaries = get_workspace_project_summaries(self.request.user)

        # Compute summary stats for the header row
        total = len(summaries)
        healthy = sum(1 for s in summaries if s.get("health_status") == "green")
        stale = sum(1 for s in summaries if s.get("audit_is_stale"))
        needs_attention = sum(1 for s in summaries if s.get("health_status") in ("red", "amber"))

        context.update(
            {
                "projects": summaries,
                "total_count": total,
                "healthy_count": healthy,
                "stale_count": stale,
                "needs_attention_count": needs_attention,
                "healthy_pct": round(healthy / total * 100) if total else 0,
                "page_title": "Agency Overview | VRT SPACE AGENCY",
                "shell_theme": "shell-light",
            }
        )
        return context
