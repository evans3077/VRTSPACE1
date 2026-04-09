from django.urls import path

from .views import WorkspaceAEOView

app_name = "aeo"

urlpatterns = [
    path("workspace/aeo/", WorkspaceAEOView.as_view(), name="workspace-aeo"),
]
