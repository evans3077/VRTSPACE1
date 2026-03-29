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
