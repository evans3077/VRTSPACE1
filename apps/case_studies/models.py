from django.db import models

from apps.core.models import SEOFieldsMixin, TimestampedModel


class CaseStudy(TimestampedModel, SEOFieldsMixin):
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    client_name = models.CharField(max_length=255)
    industry = models.CharField(max_length=120)
    challenge = models.TextField()
    solution = models.TextField()
    results = models.TextField()
    key_metric = models.CharField(max_length=120)
    featured = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = "case studies"
        ordering = ("-featured", "-created_at")

    def __str__(self):
        return self.title

# Create your models here.
