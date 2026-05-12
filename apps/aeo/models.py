import secrets

from django.db import models
from django.utils import timezone

from apps.core.models import TimestampedModel


def _generate_share_token():
    return secrets.token_urlsafe(24)


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
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

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
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.COMPLETED,
    )
    queries_sent = models.PositiveSmallIntegerField(default=0)
    engines_used = models.JSONField(default=list, blank=True)
    competitor_visibility = models.JSONField(default=dict, blank=True)
    queries_log = models.JSONField(default=list, blank=True)
    share_token = models.CharField(
        max_length=64,
        blank=True,
        default="",
        db_index=True,
    )
    share_expires_at = models.DateTimeField(null=True, blank=True)
    precision_mode = models.CharField(
        max_length=16,
        default="derived",
        help_text="'derived' = on-page heuristic; 'live' = real LLM API calls",
    )

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"AEO audit for {self.project}"

    @property
    def share_active(self):
        if not self.share_expires_at:
            return True
        return self.share_expires_at >= timezone.now()

    def save(self, *args, **kwargs):
        if not self.share_token:
            self.share_token = _generate_share_token()
        super().save(*args, **kwargs)


class AEOIndexEntry(TimestampedModel):
    """
    Public, indexable AEO visibility cache for the /aeo-index/ tool.

    Anyone can look up a domain to see if it's cited by ChatGPT/Gemini/
    Perplexity.  We populate this lazily — entries that don't exist are
    queued (rate-limited to 50/day) so the public index never costs us
    more than a hard daily ceiling of LLM calls.
    """

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    domain = models.CharField(max_length=255, unique=True, db_index=True)
    brand_name = models.CharField(max_length=200, blank=True)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.QUEUED,
    )
    overall_score = models.PositiveSmallIntegerField(default=0)
    chatgpt_cited = models.BooleanField(default=False)
    gemini_cited = models.BooleanField(default=False)
    perplexity_cited = models.BooleanField(default=False)
    chatgpt_frequency = models.PositiveSmallIntegerField(default=0)
    gemini_frequency = models.PositiveSmallIntegerField(default=0)
    perplexity_frequency = models.PositiveSmallIntegerField(default=0)
    queries_log = models.JSONField(default=list, blank=True)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    lookup_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("-last_checked_at", "-created_at")
        verbose_name_plural = "AEO index entries"

    def __str__(self):
        return self.domain

    @property
    def engines_cited_count(self):
        return sum(
            1
            for cited in (self.chatgpt_cited, self.gemini_cited, self.perplexity_cited)
            if cited
        )

    @property
    def overall_score(self):
        """Composite score: average of all four dimension scores."""
        scores = [
            self.visibility_score,
            self.entity_score,
            self.structure_score,
            self.completeness_score,
        ]
        non_zero = [s for s in scores if s]
        if not non_zero:
            return 0
        return round(sum(non_zero) / len(non_zero))


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
