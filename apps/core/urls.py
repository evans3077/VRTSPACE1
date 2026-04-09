from django.urls import path

from .views import HomePageView, ServiceDetailView, ServicesIndexView, PackagesView, location_autocomplete

app_name = "core"

urlpatterns = [
    path("", HomePageView.as_view(), name="home"),
    path("api/location/search/", location_autocomplete, name="location-search"),
    path("services/", ServicesIndexView.as_view(), name="services"),
    path("services/<slug:slug>/", ServiceDetailView.as_view(), name="service-detail"),
    path("packages/", PackagesView.as_view(), name="packages"),
]
