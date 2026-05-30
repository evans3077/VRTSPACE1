from __future__ import annotations

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.generic import CreateView, TemplateView, View

from .forms import AffiliateApplicationForm
from .middleware import get_referral_slug_from_request
from .models import (
    Affiliate,
    CommissionLedger,
    Payout,
    ReferralAttribution,
    ReferralClick,
)
from .services import (
    AffiliateError,
    build_connect_onboarding_link,
    cookie_max_age_seconds,
    portal_summary,
    record_click,
    refresh_connect_account_status,
)


SAFE_REDIRECT_BASE = "/"


def _safe_next(request) -> str:
    """Pick a same-host destination for the post-click redirect."""
    candidate = (request.GET.get("next") or "").strip()
    if not candidate:
        return SAFE_REDIRECT_BASE
    host = request.get_host()
    if url_has_allowed_host_and_scheme(candidate, allowed_hosts={host}, require_https=request.is_secure()):
        return candidate
    return SAFE_REDIRECT_BASE


@method_decorator(never_cache, name="dispatch")
class ReferralLandingView(View):
    """Public /r/<slug>/ entrypoint — stamps the cookie and bounces to the site."""

    def get(self, request, slug, *args, **kwargs):
        normalized = (slug or "").strip().lower()[:64]
        affiliate = Affiliate.objects.filter(
            slug=normalized,
            status=Affiliate.Status.ACTIVE,
        ).first()
        destination = _safe_next(request)
        response = HttpResponseRedirect(destination)
        if not affiliate:
            # Slug doesn't resolve — silent redirect, no cookie stamp.
            return response
        record_click(affiliate, request, landing_path=destination)
        response.set_cookie(
            settings.AFFILIATE_COOKIE_NAME,
            affiliate.slug,
            max_age=cookie_max_age_seconds(),
            httponly=True,
            samesite="Lax",
            secure=not settings.DEBUG,
        )
        return response


def _partner_program_context():
    """Shared brand + commission context for the public partner pages."""
    return {
        "shell_theme": "shell-light",
        "first_payment_pct": settings.AFFILIATE_COMMISSION_FIRST_PAYMENT_PCT,
        "recurring_pct": settings.AFFILIATE_COMMISSION_RECURRING_PCT,
        "payout_hold_days": settings.AFFILIATE_PAYOUT_HOLD_DAYS,
    }


class PartnerInquiryView(CreateView):
    """Public application form for prospective affiliates."""

    template_name = "affiliates/partner_inquiry.html"
    form_class = AffiliateApplicationForm
    success_url = reverse_lazy("affiliates:partner-inquiry-thanks")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(_partner_program_context())
        context.setdefault("page_title", "Partner Program | VRT SPACE AGENCY")
        context.setdefault(
            "meta_description",
            "Join the invite-only VRT SPACE partner program. Earn recurring "
            "commission referring agencies and brands to our AI visibility platform.",
        )
        return context

    def form_valid(self, form):
        application = form.save(commit=False)
        application.submission_context = {
            "ip": (self.request.META.get("HTTP_X_FORWARDED_FOR") or self.request.META.get("REMOTE_ADDR") or "")[:64],
            "user_agent": (self.request.META.get("HTTP_USER_AGENT") or "")[:255],
            "referer": (self.request.META.get("HTTP_REFERER") or "")[:255],
        }
        application.save()
        return super().form_valid(form)


class PartnerInquiryThanksView(TemplateView):
    template_name = "affiliates/partner_inquiry_thanks.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(_partner_program_context())
        context.setdefault("page_title", "Application received | VRT SPACE AGENCY")
        return context


# ---------------------------------------------------------------------------
# Affiliate portal (login required + must own an Affiliate profile)
# ---------------------------------------------------------------------------


class AffiliateOnlyMixin(LoginRequiredMixin):
    login_url = reverse_lazy("tools:workspace-login")

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        affiliate = Affiliate.objects.filter(user=request.user).first()
        if not affiliate:
            messages.error(request, "You don't have an affiliate profile on this account.")
            return redirect("tools:workspace-dashboard")
        request.affiliate = affiliate
        return super().dispatch(request, *args, **kwargs)


class AffiliateDashboardView(AffiliateOnlyMixin, TemplateView):
    template_name = "affiliates/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        affiliate: Affiliate = self.request.affiliate
        summary = portal_summary(affiliate)
        attributions = (
            ReferralAttribution.objects
            .filter(affiliate=affiliate)
            .select_related("user")
            .order_by("-created_at")[:50]
        )
        commissions = (
            CommissionLedger.objects
            .filter(affiliate=affiliate)
            .select_related("referred_user")
            .order_by("-created_at")[:25]
        )
        payouts = (
            Payout.objects
            .filter(affiliate=affiliate)
            .order_by("-created_at")[:25]
        )

        referral_url = self.request.build_absolute_uri(
            reverse("affiliates:referral-landing", kwargs={"slug": affiliate.slug})
        )

        ctx.update({
            "affiliate": affiliate,
            "summary": summary,
            "attributions": attributions,
            "commissions": commissions,
            "payouts": payouts,
            "referral_url": referral_url,
            "first_payment_pct": settings.AFFILIATE_COMMISSION_FIRST_PAYMENT_PCT,
            "recurring_pct": settings.AFFILIATE_COMMISSION_RECURRING_PCT,
            "payout_hold_days": settings.AFFILIATE_PAYOUT_HOLD_DAYS,
        })
        return ctx


class StripeConnectOnboardingStartView(AffiliateOnlyMixin, View):
    """Generate a fresh Stripe Connect onboarding link and redirect to it."""

    def post(self, request, *args, **kwargs):
        affiliate: Affiliate = request.affiliate
        return_url = request.build_absolute_uri(reverse("affiliates:connect-return"))
        refresh_url = request.build_absolute_uri(reverse("affiliates:connect-refresh"))
        try:
            url = build_connect_onboarding_link(
                affiliate,
                return_url=return_url,
                refresh_url=refresh_url,
            )
        except AffiliateError as exc:
            messages.error(request, f"Stripe Connect onboarding could not start: {exc}")
            return redirect("affiliates:dashboard")
        return redirect(url)


class StripeConnectRefreshView(AffiliateOnlyMixin, View):
    """Stripe redirects here when the onboarding link needs to be reissued."""

    def get(self, request, *args, **kwargs):
        return redirect("affiliates:dashboard")


class StripeConnectReturnView(AffiliateOnlyMixin, View):
    """Stripe redirects here after onboarding succeeds or is abandoned."""

    def get(self, request, *args, **kwargs):
        affiliate: Affiliate = request.affiliate
        try:
            refresh_connect_account_status(affiliate)
        except AffiliateError as exc:
            messages.warning(request, f"Couldn't verify Stripe Connect status: {exc}")
            return redirect("affiliates:dashboard")

        if affiliate.stripe_connect_payouts_enabled:
            messages.success(request, "Stripe Connect is ready — payouts will land automatically.")
        elif affiliate.stripe_connect_onboarded:
            messages.info(request, "Stripe received your details. Payouts unlock once verification clears.")
        else:
            messages.info(request, "Onboarding wasn't completed. You can resume any time from your dashboard.")
        return redirect("affiliates:dashboard")
