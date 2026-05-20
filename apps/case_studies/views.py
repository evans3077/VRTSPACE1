from django.views.generic import DetailView, ListView

from .models import CaseStudy


class CaseStudyIndexView(ListView):
    """Public case studies index."""

    model = CaseStudy
    template_name = "case_studies/case_study_index.html"
    context_object_name = "case_studies"
    paginate_by = 12

    def get_queryset(self):
        return CaseStudy.objects.all().order_by("-featured", "-created_at")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update({
            "page_title": "Case Studies — VRT SPACE AGENCY",
            "meta_description": "Real outcomes from brands and agencies using VRT SPACE to win AI citations across ChatGPT, Gemini, and Perplexity.",
            "canonical_url": self.request.build_absolute_uri(self.request.path),
            "meta_robots": "index,follow",
            "shell_theme": "shell-light",
        })
        return ctx


class CaseStudyDetailView(DetailView):
    """Public case study detail."""

    model = CaseStudy
    template_name = "case_studies/case_study_detail.html"
    context_object_name = "case_study"
    slug_field = "slug"
    slug_url_kwarg = "slug"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        case_study = self.object
        # Related: 3 other case studies, prefer same industry
        related = (
            CaseStudy.objects.exclude(pk=case_study.pk)
            .filter(industry=case_study.industry)
            .order_by("-featured", "-created_at")[:3]
        )
        if related.count() < 3:
            extras = CaseStudy.objects.exclude(pk=case_study.pk).exclude(
                pk__in=related.values_list("pk", flat=True)
            ).order_by("-featured", "-created_at")[: 3 - related.count()]
            related = list(related) + list(extras)
        ctx.update({
            "related_case_studies": related,
            "page_title": f"{case_study.title} | VRT SPACE Case Study",
            "meta_description": case_study.challenge[:160] if case_study.challenge else case_study.title,
            "canonical_url": self.request.build_absolute_uri(self.request.path),
            "meta_robots": "index,follow",
            "shell_theme": "shell-light",
        })
        return ctx
