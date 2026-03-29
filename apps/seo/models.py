from django.db import models

from apps.core.models import TimestampedModel


class FAQ(TimestampedModel):
    question = models.CharField(max_length=255)
    answer = models.TextField()
    service = models.ForeignKey(
        "content.Service",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="faqs",
    )
    article = models.ForeignKey(
        "content.Article",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="faqs",
    )
    case_study = models.ForeignKey(
        "case_studies.CaseStudy",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="faqs",
    )
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("order", "created_at")

    def __str__(self):
        return self.question

# Create your models here.
