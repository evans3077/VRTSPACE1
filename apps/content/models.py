from django.conf import settings
from django.db import models

from apps.core.models import SEOFieldsMixin, TimestampedModel


class Service(TimestampedModel, SEOFieldsMixin):
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    summary = models.TextField()
    value_proposition = models.CharField(max_length=255)
    body = models.TextField(blank=True)
    featured = models.BooleanField(default=False)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("order", "title")

    def __str__(self):
        return self.title


class Article(TimestampedModel, SEOFieldsMixin):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"

    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    excerpt = models.TextField(blank=True)
    content = models.TextField()
    pillar = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="clusters",
    )
    is_pillar = models.BooleanField(default=False)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-published_at", "-created_at")

    def __str__(self):
        return self.title


class GeneratedContent(TimestampedModel, SEOFieldsMixin):
    class OutputType(models.TextChoices):
        SERVICE_PAGE = "service_page", "Service Page"
        LANDING_PAGE = "landing_page", "Landing Page"
        ARTICLE = "article", "Article"
        ANSWER_BLOCK = "answer_block", "Answer Block"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        REVIEWED = "reviewed", "Reviewed"
        APPLIED = "applied", "Applied"
        ARCHIVED = "archived", "Archived"

    project = models.ForeignKey(
        "leads.ClientProject",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="generated_content",
    )
    source_audit_run = models.ForeignKey(
        "tools.AuditRun",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="generated_content",
    )
    source_seo_snapshot = models.ForeignKey(
        "seo.SEOContextSnapshot",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="generated_content",
    )
    source_seo_opportunity_snapshot = models.ForeignKey(
        "seo.SEOOpportunitySnapshot",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="generated_content",
    )
    source_seo_campaign = models.ForeignKey(
        "seo.SEOCampaign",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="generated_content",
    )
    source_editorial_task = models.ForeignKey(
        "content.ContentEditorialTask",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="generated_drafts",
    )
    applied_service = models.ForeignKey(
        "content.Service",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="generated_drafts",
    )
    applied_article = models.ForeignKey(
        "content.Article",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="generated_drafts",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="generated_content",
    )
    output_type = models.CharField(max_length=24, choices=OutputType.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    title = models.CharField(max_length=255)
    business_type = models.CharField(max_length=160, blank=True)
    location = models.CharField(max_length=160, blank=True)
    target_audience = models.CharField(max_length=255, blank=True)
    page_goal = models.CharField(max_length=255, blank=True)
    offer_summary = models.CharField(max_length=255, blank=True)
    search_intent = models.CharField(max_length=120, blank=True)
    target_keywords = models.JSONField(default=list, blank=True)
    body = models.TextField(blank=True)
    cta = models.CharField(max_length=255, blank=True)
    faq_items = models.JSONField(default=list, blank=True)
    suggested_internal_links = models.JSONField(default=list, blank=True)
    keywords_used = models.JSONField(default=list, blank=True)
    brief_json = models.JSONField(default=dict, blank=True)
    prompt_context = models.JSONField(default=dict, blank=True)
    output_json = models.JSONField(default=dict, blank=True)
    validation_json = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.get_output_type_display()}: {self.title}"


class ContentEditorialTask(TimestampedModel):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        DRAFTED = "drafted", "Drafted"
        APPLIED = "applied", "Applied"
        STALE = "stale", "Stale"
        ARCHIVED = "archived", "Archived"

    project = models.ForeignKey(
        "leads.ClientProject",
        on_delete=models.CASCADE,
        related_name="editorial_tasks",
    )
    source_seo_snapshot = models.ForeignKey(
        "seo.SEOContextSnapshot",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="editorial_tasks",
    )
    source_seo_opportunity_snapshot = models.ForeignKey(
        "seo.SEOOpportunitySnapshot",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="editorial_tasks",
    )
    seo_campaign = models.ForeignKey(
        "seo.SEOCampaign",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="editorial_tasks",
    )
    latest_generated_content = models.ForeignKey(
        "content.GeneratedContent",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="editorial_task_links",
    )
    brief_key = models.CharField(max_length=120)
    brief_hash = models.CharField(max_length=64, blank=True)
    title = models.CharField(max_length=255)
    output_type = models.CharField(max_length=24, choices=GeneratedContent.OutputType.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED)
    priority_score = models.PositiveSmallIntegerField(default=0)
    brief_json = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-priority_score", "-updated_at")
        constraints = [
            models.UniqueConstraint(
                fields=("project", "brief_key"),
                name="unique_editorial_task_per_project_brief",
            )
        ]

    def __str__(self):
        return f"{self.project} - {self.title}"


class CMSCredential(TimestampedModel):
    """P4 — credentials for pushing GeneratedContent to a connected CMS.

    Currently supports WordPress (REST API + Application Passwords).
    Webflow / Ghost can be added by introducing a `platform` value here.
    """

    class Platform(models.TextChoices):
        WORDPRESS = "wordpress", "WordPress"
        WEBFLOW = "webflow", "Webflow"

    project = models.ForeignKey(
        "leads.ClientProject",
        on_delete=models.CASCADE,
        related_name="cms_credentials",
    )
    platform = models.CharField(
        max_length=24,
        choices=Platform.choices,
        default=Platform.WORDPRESS,
    )
    site_url = models.URLField(
        help_text="WordPress site URL (e.g. https://yourdomain.com).",
    )
    username = models.CharField(
        max_length=120,
        blank=True,
        help_text="WordPress username (only for password-auth).",
    )
    app_password = models.CharField(
        max_length=255,
        blank=True,
        help_text="WordPress Application Password (stored verbatim; treat as secret).",
    )
    api_token = models.CharField(
        max_length=255,
        blank=True,
        help_text="Webflow API token (when platform=webflow).",
    )
    is_active = models.BooleanField(default=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-updated_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("project", "platform"),
                name="unique_cms_credential_per_platform_per_project",
            ),
        ]

    def __str__(self):
        return f"{self.project} -> {self.get_platform_display()}"


class CMSPushLog(TimestampedModel):
    """Append-only log of each push attempt for an editorial task."""

    class Status(models.TextChoices):
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"

    task = models.ForeignKey(
        ContentEditorialTask,
        on_delete=models.CASCADE,
        related_name="push_logs",
    )
    credential = models.ForeignKey(
        CMSCredential,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="push_logs",
    )
    status = models.CharField(max_length=16, choices=Status.choices)
    remote_post_id = models.CharField(max_length=64, blank=True)
    remote_post_url = models.URLField(blank=True)
    response_summary = models.TextField(blank=True)
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cms_push_triggers",
    )

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.task} -> {self.status} ({self.created_at:%Y-%m-%d})"
