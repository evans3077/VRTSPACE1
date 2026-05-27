from django.conf import settings
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


class SEOProjectProfile(TimestampedModel):
    project = models.OneToOneField(
        "leads.ClientProject",
        on_delete=models.CASCADE,
        related_name="seo_profile",
    )
    business_type = models.CharField(max_length=120)
    location = models.CharField(max_length=160)
    target_goal = models.CharField(max_length=160)
    primary_service = models.CharField(max_length=160, blank=True)
    target_audience = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("project__name",)

    def __str__(self):
        return f"{self.project} SEO profile"


class SEOCompetitor(TimestampedModel):
    class Source(models.TextChoices):
        AUDIT = "audit", "Audit"
        PROFILE = "profile", "Profile"
        SERP = "serp", "SERP Discovery"

    project = models.ForeignKey(
        "leads.ClientProject",
        on_delete=models.CASCADE,
        related_name="seo_competitors",
    )
    homepage_url = models.URLField()
    normalized_domain = models.CharField(max_length=255, blank=True)
    label = models.CharField(max_length=160, blank=True)
    source = models.CharField(max_length=24, choices=Source.choices, default=Source.PROFILE)
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("project__name", "homepage_url")
        constraints = [
            models.UniqueConstraint(
                fields=("project", "homepage_url"),
                name="unique_project_seo_competitor",
            )
        ]

    def __str__(self):
        return self.label or self.normalized_domain or self.homepage_url


class SEOSiteStructureSnapshot(TimestampedModel):
    project = models.ForeignKey(
        "leads.ClientProject",
        on_delete=models.CASCADE,
        related_name="seo_site_structure_snapshots",
    )
    source_audit_run = models.ForeignKey(
        "tools.AuditRun",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="seo_site_structure_snapshots",
    )
    output_json = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"SEO site structure for {self.project}"


class SEOCompetitorSnapshot(TimestampedModel):
    competitor = models.ForeignKey(
        SEOCompetitor,
        on_delete=models.CASCADE,
        related_name="snapshots",
    )
    source_audit_run = models.ForeignKey(
        "tools.AuditRun",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="seo_competitor_snapshots",
    )
    output_json = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"SEO competitor snapshot for {self.competitor}"


class SEOContextSnapshot(TimestampedModel):
    project = models.ForeignKey(
        "leads.ClientProject",
        on_delete=models.CASCADE,
        related_name="seo_snapshots",
    )
    profile = models.ForeignKey(
        SEOProjectProfile,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="snapshots",
    )
    source_audit_run = models.ForeignKey(
        "tools.AuditRun",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="seo_snapshots",
    )
    output_json = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"SEO context snapshot for {self.project}"


class SEOOpportunitySnapshot(TimestampedModel):
    project = models.ForeignKey(
        "leads.ClientProject",
        on_delete=models.CASCADE,
        related_name="seo_opportunity_snapshots",
    )
    profile = models.ForeignKey(
        SEOProjectProfile,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="opportunity_snapshots",
    )
    source_audit_run = models.ForeignKey(
        "tools.AuditRun",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="seo_opportunity_snapshots",
    )
    source_context_snapshot = models.ForeignKey(
        SEOContextSnapshot,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="opportunity_snapshots",
    )
    output_json = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"SEO opportunity snapshot for {self.project}"


class SEOCampaign(TimestampedModel):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        IN_PROGRESS = "in_progress", "In Progress"
        BLOCKED = "blocked", "Blocked"
        COMPLETED = "completed", "Completed"
        ARCHIVED = "archived", "Archived"

    class ValidationStatus(models.TextChoices):
        PENDING = "pending", "Pending Validation"
        VALIDATED = "validated", "Validated"

    project = models.ForeignKey(
        "leads.ClientProject",
        on_delete=models.CASCADE,
        related_name="seo_campaigns",
    )
    source_context_snapshot = models.ForeignKey(
        SEOContextSnapshot,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="campaigns",
    )
    source_opportunity_snapshot = models.ForeignKey(
        SEOOpportunitySnapshot,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="campaigns",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="seo_campaigns",
    )
    campaign_key = models.CharField(max_length=140)
    title = models.CharField(max_length=255)
    page_type = models.CharField(max_length=80, blank=True)
    target_keyword = models.CharField(max_length=255, blank=True)
    related_keywords = models.JSONField(default=list, blank=True)
    related_page_urls = models.JSONField(default=list, blank=True)
    success_criteria = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED)
    validation_status = models.CharField(
        max_length=20,
        choices=ValidationStatus.choices,
        default=ValidationStatus.PENDING,
    )
    priority_score = models.PositiveSmallIntegerField(default=0)
    due_date = models.DateField(null=True, blank=True)
    latest_validation_audit_run = models.ForeignKey(
        "tools.AuditRun",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="validated_seo_campaigns",
    )
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("status", "-priority_score", "-updated_at")
        constraints = [
            models.UniqueConstraint(
                fields=("project", "campaign_key"),
                name="unique_seo_campaign_per_project_key",
            )
        ]

    def __str__(self):
        return f"{self.project} - {self.title}"


class SEOCampaignEditItem(TimestampedModel):
    """
    A single page-level change target within an SEO campaign.
    Persists the edit_targets array so execution can be tracked item-by-item.
    """

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        IN_PROGRESS = "in_progress", "In Progress"
        COMPLETED = "completed", "Completed"
        SKIPPED = "skipped", "Skipped"

    campaign = models.ForeignKey(
        SEOCampaign,
        on_delete=models.CASCADE,
        related_name="edit_items",
    )
    page_url = models.CharField(max_length=2000, blank=True)
    page_title = models.CharField(max_length=255, blank=True)
    page_type = models.CharField(max_length=80, blank=True)
    change_scope = models.CharField(max_length=40, blank=True)  # new_page | existing_page
    # Specific changes as a list of strings (title, H1, meta, schema, FAQ, etc.)
    changes = models.JSONField(default=list)
    # What "done" looks like for this particular edit target
    success_criteria = models.JSONField(default=list)
    # Competitor examples that justify this change
    evidence = models.JSONField(default=dict)
    ordering_index = models.PositiveSmallIntegerField(default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("ordering_index", "status")

    def __str__(self):
        return f"{self.campaign.title} — {self.page_url or 'new page'}"

    @property
    def is_new_page(self):
        return self.change_scope == "new_page"


class BacklinkSnapshot(TimestampedModel):
    project = models.ForeignKey(
        "leads.ClientProject",
        on_delete=models.CASCADE,
        related_name="backlink_snapshots",
    )
    profile = models.ForeignKey(
        SEOProjectProfile,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="backlink_snapshots",
    )
    source_audit_run = models.ForeignKey(
        "tools.AuditRun",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="backlink_snapshots",
    )
    source_context_snapshot = models.ForeignKey(
        SEOContextSnapshot,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="backlink_snapshots",
    )
    source_opportunity_snapshot = models.ForeignKey(
        SEOOpportunitySnapshot,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="backlink_snapshots",
    )
    output_json = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"Backlink snapshot for {self.project}"


class BacklinkProspect(TimestampedModel):
    class ProspectType(models.TextChoices):
        RESOURCE = "resource", "Resource Page"
        DIRECTORY = "directory", "Directory / Citation"
        ASSOCIATION = "association", "Association"
        BLOG = "blog", "Blog / Publication"
        MEDIA = "media", "Media / Press"
        PARTNER = "partner", "Partner"

    class Status(models.TextChoices):
        SUGGESTED = "suggested", "Suggested"
        SHORTLISTED = "shortlisted", "Shortlisted"
        OUTREACHED = "outreached", "Outreached"
        REPLIED = "replied", "Replied"
        ACQUIRED = "acquired", "Acquired"
        REJECTED = "rejected", "Rejected"

    project = models.ForeignKey(
        "leads.ClientProject",
        on_delete=models.CASCADE,
        related_name="backlink_prospects",
    )
    snapshot = models.ForeignKey(
        BacklinkSnapshot,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="prospects",
    )
    seo_campaign = models.ForeignKey(
        "seo.SEOCampaign",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="backlink_prospects",
    )
    domain = models.CharField(max_length=255)
    homepage_url = models.URLField(blank=True)
    prospect_url = models.URLField()
    title = models.CharField(max_length=255, blank=True)
    prospect_type = models.CharField(max_length=24, choices=ProspectType.choices, default=ProspectType.RESOURCE)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.SUGGESTED)
    relevance_score = models.PositiveSmallIntegerField(default=0)
    authority_fit_score = models.PositiveSmallIntegerField(default=0)
    local_fit_score = models.PositiveSmallIntegerField(default=0)
    outreach_likelihood_score = models.PositiveSmallIntegerField(default=0)
    total_score = models.PositiveSmallIntegerField(default=0)
    target_asset_title = models.CharField(max_length=255, blank=True)
    target_asset_type = models.CharField(max_length=120, blank=True)
    target_asset_url = models.URLField(blank=True)
    suggested_anchor_text = models.CharField(max_length=255, blank=True)
    outreach_packet = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-total_score", "-updated_at")
        constraints = [
            models.UniqueConstraint(
                fields=("project", "prospect_url", "target_asset_url"),
                name="unique_backlink_prospect_per_target",
            )
        ]

    def __str__(self):
        return f"{self.domain} -> {self.target_asset_title or self.target_asset_url or self.prospect_url}"


class SEOShareLink(TimestampedModel):
    project = models.ForeignKey(
        "leads.ClientProject",
        on_delete=models.CASCADE,
        related_name="seo_share_links",
    )
    profile = models.ForeignKey(
        SEOProjectProfile,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="share_links",
    )
    source_context_snapshot = models.ForeignKey(
        SEOContextSnapshot,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="share_links",
    )
    source_opportunity_snapshot = models.ForeignKey(
        SEOOpportunitySnapshot,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="share_links",
    )
    source_backlink_snapshot = models.ForeignKey(
        BacklinkSnapshot,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="share_links",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="seo_share_links",
    )
    token = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    access_count = models.PositiveIntegerField(default=0)
    last_accessed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"SEO share link for {self.project}"
