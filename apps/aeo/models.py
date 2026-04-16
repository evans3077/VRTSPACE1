from django.db import models

from apps.core.models import TimestampedModel


class VisibilitySnapshot(TimestampedModel):
    class Engine(models.TextChoices):
        CHATGPT = "chatgpt", "ChatGPT"
        GEMINI = "gemini", "Gemini"
        PERPLEXITY = "perplexity", "Perplexity"

    engine = models.CharField(max_length=24, choices=Engine.choices)
    aeo_audit = models.ForeignKey(
        "aeo.AEOAudit",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="visibility_snapshots",
    )
    prompt = models.TextField()
    cited_url = models.URLField(blank=True)
    answer_present = models.BooleanField(default=False)
    citation_frequency = models.PositiveSmallIntegerField(default=0)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("engine", "-created_at")

    def __str__(self):
        return f"{self.engine}: {self.prompt[:40]}"


class AEOAudit(TimestampedModel):
    project = models.ForeignKey(
        "leads.ClientProject",
        on_delete=models.CASCADE,
        related_name="aeo_audits",
    )
    seo_profile = models.ForeignKey(
        "seo.SEOProjectProfile",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="aeo_audits",
    )
    source_audit_run = models.ForeignKey(
        "tools.AuditRun",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="aeo_audits",
    )
    target_keyword = models.CharField(max_length=160, blank=True)
    visibility_score = models.PositiveSmallIntegerField(default=0)
    entity_score = models.PositiveSmallIntegerField(default=0)
    structure_score = models.PositiveSmallIntegerField(default=0)
    completeness_score = models.PositiveSmallIntegerField(default=0)
    output_json = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"AEO audit for {self.project}"


class AIRecommendation(TimestampedModel):
    aeo_audit = models.ForeignKey(
        AEOAudit,
        on_delete=models.CASCADE,
        related_name="recommendations",
    )
    issue = models.CharField(max_length=255)
    why_ai_ignores_this = models.TextField(blank=True)
    fix = models.TextField(blank=True)
    example_rewrite = models.TextField(blank=True)
    expected_impact = models.TextField(blank=True)
    priority_score = models.PositiveSmallIntegerField(default=0)
    category = models.CharField(max_length=80, blank=True)

    class Meta:
        ordering = ("-priority_score", "created_at")

    def __str__(self):
        return self.issue
