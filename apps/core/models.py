from django.db import models


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SEOFieldsMixin(models.Model):
    meta_title = models.CharField(max_length=255, blank=True)
    meta_description = models.TextField(blank=True)
    schema_json = models.JSONField(default=dict, blank=True)

    class Meta:
        abstract = True


class SiteSettings(TimestampedModel):
    brand_name = models.CharField(max_length=120, default="VRT SPACE AGENCY")
    hero_title = models.CharField(
        max_length=255,
        default="Turn your website into a measurable growth system.",
    )
    hero_subtitle = models.TextField(
        default=(
            "Run the audit, open a workspace, track what is broken, and choose when "
            "to unlock deeper monitoring, automation, and content systems."
        )
    )
    proprietary_method_name = models.CharField(max_length=120, default="VRT Authority Engine")
    primary_cta_label = models.CharField(max_length=80, default="Run Free Audit")
    secondary_cta_label = models.CharField(max_length=80, default="Create Workspace")

    class Meta:
        verbose_name_plural = "site settings"

    def __str__(self):
        return self.brand_name

# Create your models here.
