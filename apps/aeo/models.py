from django.db import models

from apps.core.models import TimestampedModel


class VisibilitySnapshot(TimestampedModel):
    class Engine(models.TextChoices):
        CHATGPT = "chatgpt", "ChatGPT"
        GEMINI = "gemini", "Gemini"
        PERPLEXITY = "perplexity", "Perplexity"

    engine = models.CharField(max_length=24, choices=Engine.choices)
    prompt = models.TextField()
    cited_url = models.URLField(blank=True)
    answer_present = models.BooleanField(default=False)
    citation_frequency = models.PositiveSmallIntegerField(default=0)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("engine", "-created_at")

    def __str__(self):
        return f"{self.engine}: {self.prompt[:40]}"

# Create your models here.
