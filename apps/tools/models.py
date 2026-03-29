from django.db import models

from apps.core.models import SEOFieldsMixin, TimestampedModel


class ToolDefinition(TimestampedModel, SEOFieldsMixin):
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    description = models.TextField()
    endpoint_path = models.CharField(max_length=255)
    is_public = models.BooleanField(default=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name


class AuditRun(TimestampedModel):
    class ToolType(models.TextChoices):
        SEO = "seo", "SEO Audit"
        AEO = "aeo", "AEO Audit"
        COMBINED = "combined", "Combined Audit"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    audit_request = models.ForeignKey(
        "leads.AuditRequest",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_runs",
    )
    tool_type = models.CharField(max_length=24, choices=ToolType.choices, default=ToolType.COMBINED)
    normalized_domain = models.CharField(max_length=255)
    start_url = models.URLField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    overall_score = models.PositiveSmallIntegerField(default=0)
    technical_score = models.PositiveSmallIntegerField(default=0)
    on_page_score = models.PositiveSmallIntegerField(default=0)
    content_score = models.PositiveSmallIntegerField(default=0)
    aeo_score = models.PositiveSmallIntegerField(default=0)
    internal_linking_score = models.PositiveSmallIntegerField(default=0)
    performance_score = models.PositiveSmallIntegerField(default=0)
    accessibility_score = models.PositiveSmallIntegerField(null=True, blank=True)
    best_practices_score = models.PositiveSmallIntegerField(null=True, blank=True)
    seo_score = models.PositiveSmallIntegerField(null=True, blank=True)
    
    pages_crawled = models.PositiveSmallIntegerField(default=0)
    summary = models.JSONField(default=dict, blank=True)
    tech_summary = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.normalized_domain} ({self.status})"


class AuditPage(TimestampedModel):
    audit_run = models.ForeignKey(AuditRun, on_delete=models.CASCADE, related_name="pages")
    url = models.URLField()
    status_code = models.PositiveSmallIntegerField(default=0)
    title = models.CharField(max_length=255, blank=True)
    meta_description = models.TextField(blank=True)
    h1 = models.CharField(max_length=255, blank=True)
    canonical_url = models.URLField(blank=True)
    robots = models.CharField(max_length=255, blank=True)
    word_count = models.PositiveIntegerField(default=0)
    internal_link_count = models.PositiveSmallIntegerField(default=0)
    images_missing_alt = models.PositiveSmallIntegerField(default=0)
    schema_count = models.PositiveSmallIntegerField(default=0)
    has_faq_schema = models.BooleanField(default=False)
    response_time_ms = models.PositiveIntegerField(default=0)
    pagespeed_score = models.PositiveSmallIntegerField(null=True, blank=True)
    accessibility_score = models.PositiveSmallIntegerField(null=True, blank=True)
    best_practices_score = models.PositiveSmallIntegerField(null=True, blank=True)
    seo_score = models.PositiveSmallIntegerField(null=True, blank=True)
    pagespeed_data = models.JSONField(default=dict, blank=True)
    tech_stack = models.JSONField(default=dict, blank=True)
    asset_stats = models.JSONField(default=dict, blank=True)
    readability_score = models.PositiveSmallIntegerField(null=True, blank=True)
    security_headers = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("url",)

    def __str__(self):
        return self.url


class AuditIssue(TimestampedModel):
    class Category(models.TextChoices):
        TECHNICAL = "technical", "Technical"
        ON_PAGE = "on_page", "On-page"
        CONTENT = "content", "Content"
        AEO = "aeo", "AEO"
        INTERNAL_LINKING = "internal_linking", "Internal Linking"
        PERFORMANCE = "performance", "Performance"

    class Severity(models.TextChoices):
        CRITICAL = "critical", "Critical"
        HIGH = "high", "High"
        MEDIUM = "medium", "Medium"
        LOW = "low", "Low"

    audit_run = models.ForeignKey(AuditRun, on_delete=models.CASCADE, related_name="issues")
    page = models.ForeignKey(
        AuditPage,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="issues",
    )
    code = models.CharField(max_length=80)
    category = models.CharField(max_length=24, choices=Category.choices)
    severity = models.CharField(max_length=16, choices=Severity.choices)
    message = models.CharField(max_length=255)
    recommendation = models.TextField(blank=True)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("severity", "category", "created_at")

    def __str__(self):
        return f"{self.code} ({self.severity})"
