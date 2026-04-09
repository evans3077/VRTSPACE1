from django.db import models

from apps.core.models import TimestampedModel


class AnalyticsEvent(TimestampedModel):
    event_name = models.CharField(max_length=120)
    path = models.CharField(max_length=255)
    session_key = models.CharField(max_length=80, blank=True)
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.event_name} @ {self.path}"

# Create your models here.
