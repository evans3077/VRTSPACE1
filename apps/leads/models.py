from django.db import models
from django.conf import settings

from apps.core.models import TimestampedModel


class Lead(TimestampedModel):
    class InterestArea(models.TextChoices):
        AEO = "aeo", "Answer Engine Optimization"
        SEO = "seo", "SEO"
        CONTENT = "content", "Content Marketing"
        WEB = "web", "Web Development"

    name = models.CharField(max_length=120)
    email = models.EmailField()
    company = models.CharField(max_length=160, blank=True)
    website = models.URLField(blank=True)
    message = models.TextField(blank=True)
    interest_area = models.CharField(max_length=24, choices=InterestArea.choices)
    source_page = models.CharField(max_length=255, blank=True)
    submission_context = models.JSONField(default=dict, blank=True)
    score = models.PositiveSmallIntegerField(default=0)
    consent_to_contact = models.BooleanField(default=False)
    qualified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.name} ({self.email})"


class AuditRequest(TimestampedModel):
    class Status(models.TextChoices):
        NEW = "new", "New"
        REVIEWED = "reviewed", "Reviewed"
        QUALIFIED = "qualified", "Qualified"

    company_name = models.CharField(max_length=160, blank=True)
    email = models.EmailField()
    website = models.URLField()
    monthly_leads_goal = models.PositiveIntegerField(default=20)
    notes = models.TextField(blank=True)
    submission_context = models.JSONField(default=dict, blank=True)
    score = models.PositiveSmallIntegerField(default=0)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.NEW)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.website} ({self.email})"


class ClientProject(TimestampedModel):
    class Stage(models.TextChoices):
        DISCOVERY = "discovery", "Discovery"
        PROPOSAL = "proposal", "Proposal"
        ACTIVE = "active", "Active"
        RETAINED = "retained", "Retained"
        ARCHIVED = "archived", "Archived"

    audit_request = models.OneToOneField(
        AuditRequest,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="client_project",
    )
    latest_audit_run = models.ForeignKey(
        "tools.AuditRun",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="project_snapshots",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="client_projects",
    )
    name = models.CharField(max_length=160)
    website = models.URLField()
    normalized_domain = models.CharField(max_length=255, blank=True)
    contact_email = models.EmailField(blank=True)
    stage = models.CharField(max_length=16, choices=Stage.choices, default=Stage.DISCOVERY)
    latest_score = models.PositiveSmallIntegerField(default=0)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name

# Create your models here.
