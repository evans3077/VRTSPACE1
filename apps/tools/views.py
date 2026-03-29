from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.cache import cache
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import DetailView

from apps.leads.forms import AuditRequestForm
from apps.leads.services import create_audit_request_from_form

from .models import AuditRun
from .services import normalize_url, run_public_site_audit


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

        audit_request = create_audit_request_from_form(form)
        audit_run = AuditRun.objects.create(
            audit_request=audit_request,
            normalized_domain="pending",
            start_url=normalize_url(audit_request.website),
        )

        run_public_site_audit(audit_run=audit_run)
        if audit_run.status == AuditRun.Status.FAILED:
            messages.error(request, "We could not audit that site automatically. Try a different public URL.")
            return redirect("/#audit")

        messages.success(request, "Audit complete. Review the summary below.")
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

        # Handle legacy quick_wins format (list of strings)
        quick_wins = summary.get("quick_wins", [])
        refined_wins = []
        for win in quick_wins:
            if isinstance(win, dict):
                refined_wins.append(win)
            else:
                # Convert legacy string to new format
                refined_wins.append({
                    "category": "General",
                    "problem": "Optimization Opportunity",
                    "fix": win,
                    "url": None
                })
        
        # Handle legacy top_issues format variations
        legacy_top_issues = summary.get("top_issues", [])
        refined_top_issues = []
        for issue in legacy_top_issues:
            if isinstance(issue, dict):
                # Ensure it has message/recommendation even if it came from the short-lived 'strategic_advice' format
                msg = issue.get("message") or issue.get("title") or "Issue Detected"
                rec = issue.get("recommendation") or issue.get("fix") or "View detailed report for fix."
                refined_top_issues.append({
                    "severity": issue.get("severity", "MEDIUM"),
                    "category": issue.get("category", "General"),
                    "message": msg,
                    "recommendation": rec
                })
        
        context["quick_wins"] = refined_wins
        context["top_issues"] = refined_top_issues or list(audit_run.issues.all())[:8]
        context["gauge_list"] = gauge_list
        context["pages"] = audit_run.pages.all()
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

        # Group issues by category
        from collections import defaultdict

        issues_by_cat = defaultdict(list)
        for issue in audit_run.issues.all():
            issues_by_cat[issue.category].append(issue)
        context["issues_by_category"] = dict(issues_by_cat)

        return context
