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
    prompt_context = models.JSONField(default=dict, blank=True)
    output_json = models.JSONField(default=dict, blank=True)
    validation_json = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.get_output_type_display()}: {self.title}"

# Create your models here.
