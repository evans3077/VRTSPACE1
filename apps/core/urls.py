from django.urls import path

from .views import (
    GlossaryView,
    HelpCenterView,
    HomePageView,
    HowItWorksView,
    IndustryLandingView,
    ServiceDetailView,
    ServicesIndexView,
    PackagesView,
    ForAgenciesView,
    location_autocomplete,
)

app_name = "core"

urlpatterns = [
    path("", HomePageView.as_view(), name="home"),
    path("how-it-works/", HowItWorksView.as_view(), name="how-it-works"),
    path("glossary/", GlossaryView.as_view(), name="glossary"),
    path("help/", HelpCenterView.as_view(), name="help-center"),
    path("for-agencies/", ForAgenciesView.as_view(), name="for-agencies"),
    path("api/location/search/", location_autocomplete, name="location-search"),
    path("services/", ServicesIndexView.as_view(), name="services"),
    path("services/<slug:slug>/", ServiceDetailView.as_view(), name="service-detail"),
    path("packages/", PackagesView.as_view(), name="packages"),
    path("ai-visibility-for/<slug:slug>/", IndustryLandingView.as_view(), name="industry-landing"),
]
