from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from apps.leads.billing import (
    BillingError,
    create_billing_portal_session,
    create_checkout_session,
    create_workspace_rerun_for_user,
    get_plan_by_slug,
    get_workspace_subscription,
    handle_stripe_webhook_event,
    verify_stripe_signature,
)
from apps.tools.automation import update_workspace_schedule
from apps.tools.models import WorkspaceAuditSchedule

from .jobs import enqueue_public_site_audit


class WorkspaceCheckoutCreateView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        plan_slug = request.POST.get("plan", "").strip().lower()
        plan = get_plan_by_slug(plan_slug)
        if not plan:
            messages.error(request, "That plan is not available.")
            return redirect("tools:workspace-dashboard")

        if plan.slug == "enterprise":
            messages.info(request, "Enterprise work is handled through a direct custom scope.")
            return redirect("core:home")

        try:
            session = create_checkout_session(
                user=request.user,
                plan=plan,
                success_url=request.build_absolute_uri(reverse("tools:workspace-billing-success")),
                cancel_url=request.build_absolute_uri(reverse("tools:workspace-billing-cancel")),
            )
        except BillingError as exc:
            messages.error(request, str(exc))
            return redirect("tools:workspace-dashboard")

        return redirect(session["url"])


class WorkspaceBillingPortalView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        subscription = get_workspace_subscription(request.user)
        try:
            session = create_billing_portal_session(
                subscription=subscription,
                return_url=request.build_absolute_uri(reverse("tools:workspace-dashboard")),
            )
        except BillingError as exc:
            messages.error(request, str(exc))
            return redirect("tools:workspace-dashboard")
        return redirect(session["url"])


class WorkspaceBillingSuccessView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        messages.success(request, "Billing completed. Your workspace plan will update after Stripe confirms the subscription.")
        return redirect("tools:workspace-dashboard")


class WorkspaceBillingCancelView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        messages.info(request, "Billing checkout was cancelled.")
        return redirect("tools:workspace-dashboard")


class WorkspaceAuditRerunView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        try:
            audit_run = create_workspace_rerun_for_user(request.user)
        except BillingError as exc:
            messages.error(request, str(exc))
            return redirect("tools:workspace-dashboard")

        enqueue_public_site_audit(audit_run.pk)
        messages.success(request, "Workspace rerun started.")
        return redirect("tools:audit-result", pk=audit_run.pk)


class WorkspaceAuditScheduleView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        cadence = request.POST.get("cadence", WorkspaceAuditSchedule.Cadence.WEEKLY)
        valid_cadences = {choice[0] for choice in WorkspaceAuditSchedule.Cadence.choices}
        if cadence not in valid_cadences:
            messages.error(request, "That recurring audit cadence is not available.")
            return redirect("tools:workspace-dashboard")

        is_active = request.POST.get("is_active") == "1"
        try:
            schedule = update_workspace_schedule(
                user=request.user,
                cadence=cadence,
                is_active=is_active,
            )
        except BillingError as exc:
            messages.error(request, str(exc))
            return redirect("tools:workspace-dashboard")

        if schedule.is_active:
            messages.success(request, f"Recurring audits are active on a {schedule.get_cadence_display().lower()} cadence.")
        else:
            messages.info(request, "Recurring audits are paused for this workspace.")
        return redirect("tools:workspace-dashboard")


@method_decorator(csrf_exempt, name="dispatch")
class StripeWebhookView(View):
    def post(self, request, *args, **kwargs):
        try:
            event = verify_stripe_signature(
                request.body,
                request.headers.get("Stripe-Signature", ""),
            )
            handle_stripe_webhook_event(event)
        except BillingError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        return HttpResponse(status=200)
