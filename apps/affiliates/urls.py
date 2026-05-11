from django.urls import path

from .views import (
    AffiliateDashboardView,
    PartnerInquiryThanksView,
    PartnerInquiryView,
    ReferralLandingView,
    StripeConnectOnboardingStartView,
    StripeConnectRefreshView,
    StripeConnectReturnView,
)

app_name = "affiliates"

urlpatterns = [
    path("r/<slug:slug>/", ReferralLandingView.as_view(), name="referral-landing"),
    path("partners/", PartnerInquiryView.as_view(), name="partner-inquiry"),
    path("partners/thanks/", PartnerInquiryThanksView.as_view(), name="partner-inquiry-thanks"),
    path("affiliate/", AffiliateDashboardView.as_view(), name="dashboard"),
    path("affiliate/stripe/onboard/", StripeConnectOnboardingStartView.as_view(), name="connect-onboard"),
    path("affiliate/stripe/return/", StripeConnectReturnView.as_view(), name="connect-return"),
    path("affiliate/stripe/refresh/", StripeConnectRefreshView.as_view(), name="connect-refresh"),
]
