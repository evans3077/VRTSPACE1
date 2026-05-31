from django.contrib.auth import views as auth_views
from django.urls import path

from .views import (
    AffiliateDashboardView,
    AffiliateLoginView,
    AffiliateLogoutView,
    AffiliateSettingsView,
    PartnerInquiryThanksView,
    PartnerInquiryView,
    ReferralLandingView,
    StripeConnectOnboardingStartView,
    StripeConnectRefreshView,
    StripeConnectReturnView,
)

app_name = "affiliates"

urlpatterns = [
    # Public referral redirect
    path("r/<slug:slug>/", ReferralLandingView.as_view(), name="referral-landing"),

    # Public partner application
    path("partners/", PartnerInquiryView.as_view(), name="partner-inquiry"),
    path("partners/thanks/", PartnerInquiryThanksView.as_view(), name="partner-inquiry-thanks"),

    # Dedicated affiliate auth
    path("affiliate/login/", AffiliateLoginView.as_view(), name="login"),
    path("affiliate/logout/", AffiliateLogoutView.as_view(), name="logout"),

    # Password reset flow (no Django branding)
    path("affiliate/password-reset/", auth_views.PasswordResetView.as_view(
        template_name="affiliates/password_reset.html",
        email_template_name="affiliates/emails/password_reset_email.txt",
        subject_template_name="affiliates/emails/password_reset_subject.txt",
        success_url="/affiliate/password-reset/sent/",
    ), name="password-reset"),
    path("affiliate/password-reset/sent/", auth_views.PasswordResetDoneView.as_view(
        template_name="affiliates/password_reset_done.html",
    ), name="password-reset-done"),
    path("affiliate/password-reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="affiliates/password_reset_confirm.html",
        success_url="/affiliate/password-reset/complete/",
    ), name="password-reset-confirm"),
    path("affiliate/password-reset/complete/", auth_views.PasswordResetCompleteView.as_view(
        template_name="affiliates/password_reset_complete.html",
    ), name="password-reset-complete"),

    # Affiliate portal
    path("affiliate/", AffiliateDashboardView.as_view(), name="dashboard"),
    path("affiliate/settings/", AffiliateSettingsView.as_view(), name="settings"),
    path("affiliate/stripe/onboard/", StripeConnectOnboardingStartView.as_view(), name="connect-onboard"),
    path("affiliate/stripe/return/", StripeConnectReturnView.as_view(), name="connect-return"),
    path("affiliate/stripe/refresh/", StripeConnectRefreshView.as_view(), name="connect-refresh"),
]
