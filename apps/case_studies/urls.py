from django.urls import path

from .views import CaseStudyDetailView, CaseStudyIndexView

app_name = "case_studies"

urlpatterns = [
    path("case-studies/", CaseStudyIndexView.as_view(), name="case-study-index"),
    path("case-studies/<slug:slug>/", CaseStudyDetailView.as_view(), name="case-study-detail"),
]
