from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from urllib.parse import quote
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from apps.leads.billing import (
    BillingError,
    create_billing_portal_session,
    create_checkout_session,
    create_topup_checkout_session,
    create_workspace_rerun_for_user,
    get_plan_by_slug,
    get_topup_pack,
    get_workspace_subscription,
    handle_stripe_webhook_event,
    is_active_subscription,
    sync_subscription_from_checkout_session_id,
    verify_stripe_signature,
)
from apps.leads.services import resolve_workspace_project
from apps.tools.automation import update_workspace_schedule
from apps.tools.models import WorkspaceAuditSchedule

from .jobs import enqueue_public_site_audit


class WorkspaceCheckoutCreateView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        return self._handle(request, request.GET)

    def post(self, request, *args, **kwargs):
        return self._handle(request, request.POST)

    def _handle(self, request, data):
        plan_slug = data.get("plan", "").strip().lower()
        return_to = data.get("return_to", "").strip()
        
        if not plan_slug:
            return redirect("tools:account-dashboard")

        plan = get_plan_by_slug(plan_slug)
        if not plan:
            messages.error(request, "That plan is not available.")
            return redirect("tools:account-dashboard")

        if plan.slug == "enterprise":
            messages.info(request, "Enterprise work is handled through a direct custom scope.")
            return redirect("core:home")

        try:
            success_path = f"{reverse('tools:workspace-billing-success')}?session_id={{CHECKOUT_SESSION_ID}}"
            cancel_path = reverse("tools:workspace-billing-cancel")
            if return_to.startswith("/"):
                quoted_return_to = quote(return_to, safe="/#?=&")
                success_path = f"{success_path}&next={quoted_return_to}"
                cancel_path = f"{cancel_path}?next={quoted_return_to}"
            session = create_checkout_session(
                user=request.user,
                plan=plan,
                success_url=request.build_absolute_uri(success_path),
                cancel_url=request.build_absolute_uri(cancel_path),
            )
        except BillingError as exc:
            messages.error(request, str(exc))
            return redirect("tools:account-dashboard")

        return redirect(session["url"])


class WorkspaceTopupCreateView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        return self._handle(request, request.GET)

    def post(self, request, *args, **kwargs):
        return self._handle(request, request.POST)

    def _handle(self, request, data):
        pack_slug = data.get("pack", "").strip()
        return_to = data.get("return_to", "").strip()

        pack = get_topup_pack(pack_slug)
        if not pack:
            messages.error(request, "That credit top-up is not available.")
            return redirect("tools:account-dashboard")

        try:
            success_path = f"{reverse('tools:workspace-billing-success')}?session_id={{CHECKOUT_SESSION_ID}}"
            cancel_path = reverse("tools:workspace-billing-cancel")
            if return_to.startswith("/"):
                quoted_return_to = quote(return_to, safe="/#?=&")
                success_path = f"{success_path}&next={quoted_return_to}"
                cancel_path = f"{cancel_path}?next={quoted_return_to}"
            session = create_topup_checkout_session(
                user=request.user,
                pack=pack,
                success_url=request.build_absolute_uri(success_path),
                cancel_url=request.build_absolute_uri(cancel_path),
            )
        except BillingError as exc:
            messages.error(request, str(exc))
            return redirect("tools:account-dashboard")

        return redirect(session["url"])


class WorkspaceBillingPortalView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        return self._handle(request, request.GET)

    def post(self, request, *args, **kwargs):
        return self._handle(request, request.POST)

    def _handle(self, request, data):
        subscription = get_workspace_subscription(request.user)
        return_to = data.get("return_to", "").strip()
        try:
            return_url = reverse("tools:account-dashboard")
            if return_to.startswith("/"):
                return_url = return_to
            session = create_billing_portal_session(
                subscription=subscription,
                return_url=request.build_absolute_uri(return_url),
            )
        except BillingError as exc:
            messages.error(request, str(exc))
            return redirect("tools:account-dashboard")
        return redirect(session["url"])


class WorkspaceBillingSuccessView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        session_id = request.GET.get("session_id", "").strip()
        subscription = get_workspace_subscription(request.user)
        session_placeholder_received = (
            not session_id
            or session_id == "{CHECKOUT_SESSION_ID}"
            or "{CHECKOUT_SESSION_ID}" in session_id
        )
        if session_placeholder_received and subscription and subscription.stripe_checkout_session_id:
            session_id = subscription.stripe_checkout_session_id

        if session_id:
            try:
                sync_subscription_from_checkout_session_id(session_id)
            except BillingError as exc:
                refreshed_subscription = get_workspace_subscription(request.user)
                if is_active_subscription(refreshed_subscription):
                    messages.success(request, "Billing completed and the subscription is active.")
                else:
                    messages.warning(
                        request,
                        f"Billing completed, but the subscription refresh is still pending. {exc}",
                    )
            else:
                messages.success(request, "Billing completed and workspace credits are now available.")
        else:
            messages.success(request, "Billing completed. Your workspace plan will update after Stripe confirms the subscription.")
        next_url = request.GET.get("next", "").strip()
        if next_url.startswith("/"):
            return redirect(next_url)
        return redirect("tools:workspace-dashboard")


class WorkspaceBillingCancelView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        messages.info(request, "Billing checkout was cancelled.")
        next_url = request.GET.get("next", "").strip()
        if next_url.startswith("/"):
            return redirect(next_url)
        return redirect("tools:workspace-dashboard")


class WorkspaceAuditRerunView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        project = resolve_workspace_project(request, request.user)
        if project is None:
            messages.error(request, "Create a project first before running an audit.")
            return redirect(f"{reverse('tools:workspace-dashboard')}#new-project")
        try:
            audit_run = create_workspace_rerun_for_user(request.user, project=project)
        except BillingError as exc:
            messages.error(request, str(exc))
            return redirect("tools:account-dashboard")

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
        project = resolve_workspace_project(request, request.user)
        if project is None:
            messages.error(request, "Create a project first before setting recurring audit rules.")
            return redirect(f"{reverse('tools:workspace-dashboard')}#new-project")
        try:
            schedule = update_workspace_schedule(
                user=request.user,
                project=project,
                cadence=cadence,
                is_active=is_active,
                report_recipients=request.POST.get("report_recipients", ""),
                email_reports_enabled=request.POST.get("email_reports_enabled") == "1",
                alert_on_score_drop=request.POST.get("alert_on_score_drop") == "1",
                alert_on_new_issues=request.POST.get("alert_on_new_issues") == "1",
            )
        except BillingError as exc:
            messages.error(request, str(exc))
            return redirect("tools:account-dashboard")

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
