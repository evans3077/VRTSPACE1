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
    business_type = models.CharField(max_length=120, blank=True)
    location = models.CharField(max_length=160, blank=True)
    target_goal = models.CharField(max_length=160, blank=True)
    primary_service = models.CharField(max_length=160, blank=True)
    monthly_leads_goal = models.PositiveIntegerField(default=20)
    market_context = models.TextField(blank=True)
    competitor_urls = models.JSONField(default=list, blank=True)
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
    business_type = models.CharField(max_length=120, blank=True)
    location = models.CharField(max_length=160, blank=True)
    target_goal = models.CharField(max_length=160, blank=True)
    primary_service = models.CharField(max_length=160, blank=True)
    stage = models.CharField(max_length=16, choices=Stage.choices, default=Stage.DISCOVERY)
    latest_score = models.PositiveSmallIntegerField(default=0)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name


class WorkspacePlan(TimestampedModel):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=80)
    price_label = models.CharField(max_length=80, blank=True)
    stripe_price_id = models.CharField(max_length=120, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    monthly_audits_limit = models.PositiveSmallIntegerField(null=True, blank=True)
    history_limit = models.PositiveSmallIntegerField(null=True, blank=True)
    premium_recommendation_limit = models.PositiveSmallIntegerField(null=True, blank=True)
    recurring_audits_enabled = models.BooleanField(default=False)
    export_reports_enabled = models.BooleanField(default=False)
    email_reports_enabled = models.BooleanField(default=False)
    competitor_tracking_enabled = models.BooleanField(default=False)
    stakeholder_sharing_enabled = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("sort_order", "name")

    def __str__(self):
        return self.name


class WorkspaceSubscription(TimestampedModel):
    class Status(models.TextChoices):
        INACTIVE = "inactive", "Inactive"
        TRIALING = "trialing", "Trialing"
        ACTIVE = "active", "Active"
        PAST_DUE = "past_due", "Past Due"
        CANCELED = "canceled", "Canceled"
        UNPAID = "unpaid", "Unpaid"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="workspace_subscription",
    )
    plan = models.ForeignKey(
        WorkspacePlan,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="subscriptions",
    )
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.INACTIVE)
    stripe_customer_id = models.CharField(max_length=120, blank=True)
    stripe_subscription_id = models.CharField(max_length=120, blank=True)
    stripe_checkout_session_id = models.CharField(max_length=120, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)
    last_webhook_event_id = models.CharField(max_length=120, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-updated_at",)

    def __str__(self):
        plan_name = self.plan.name if self.plan_id else "No plan"
        return f"{self.user} - {plan_name}"


class UsageRecord(TimestampedModel):
    class Metric(models.TextChoices):
        AUDIT_RUN = "audit_run", "Audit Run"
        SEO_SNAPSHOT = "seo_snapshot", "SEO Snapshot"
        AEO_AUDIT = "aeo_audit", "AEO Audit"
        CONTENT_DRAFT = "content_draft", "Content Draft"
        EXPORT = "export", "Export"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="usage_records",
    )
    plan = models.ForeignKey(
        WorkspacePlan,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="usage_records",
    )
    metric = models.CharField(max_length=32, choices=Metric.choices)
    period_start = models.DateField()
    period_end = models.DateField()
    quantity = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-period_start", "-updated_at")
        constraints = [
            models.UniqueConstraint(
                fields=("user", "metric", "period_start", "period_end"),
                name="unique_usage_record_per_period",
            )
        ]

    def __str__(self):
        return f"{self.user} - {self.metric} ({self.period_start})"


class WorkspaceCreditLedger(TimestampedModel):
    class Category(models.TextChoices):
        WORKSPACE = "workspace", "Workspace"
        AUDIT = "audit", "Audit"
        SEO = "seo", "SEO"
        AEO = "aeo", "AEO"
        CONTENT = "content", "Content"
        BACKLINK = "backlink", "Backlink"
        EXPORT = "export", "Export"
        SHARE = "share", "Share"

    class Kind(models.TextChoices):
        GRANT = "grant", "Grant"
        DEBIT = "debit", "Debit"
        ADJUSTMENT = "adjustment", "Adjustment"
        BONUS = "bonus", "Bonus"
        REFUND = "refund", "Refund"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="workspace_credit_entries",
    )
    plan = models.ForeignKey(
        WorkspacePlan,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="credit_entries",
    )
    subscription = models.ForeignKey(
        WorkspaceSubscription,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="credit_entries",
    )
    project = models.ForeignKey(
        "leads.ClientProject",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="credit_entries",
    )
    category = models.CharField(max_length=24, choices=Category.choices)
    kind = models.CharField(max_length=24, choices=Kind.choices)
    delta = models.IntegerField()
    period_start = models.DateField()
    period_end = models.DateField()
    note = models.CharField(max_length=255, blank=True)
    reference_key = models.CharField(max_length=120, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-period_start", "-created_at")

    def __str__(self):
        return f"{self.user} - {self.category} ({self.delta})"

# Create your models here.
