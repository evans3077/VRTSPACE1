from django.urls import path

from .views import OperationsDashboardView

app_name = "analytics"

urlpatterns = [
    path("ops/dashboard/", OperationsDashboardView.as_view(), name="operations-dashboard"),
]
