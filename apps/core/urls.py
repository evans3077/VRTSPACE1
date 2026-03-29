from django.urls import path

from .views import HomePageView, ServiceDetailView, ServicesIndexView

app_name = "core"

urlpatterns = [
    path("", HomePageView.as_view(), name="home"),
    path("services/", ServicesIndexView.as_view(), name="services"),
    path("services/<slug:slug>/", ServiceDetailView.as_view(), name="service-detail"),
]
