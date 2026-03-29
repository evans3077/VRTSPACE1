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
        default="Make your brand the source AI search trusts.",
    )
    hero_subtitle = models.TextField(
        default=(
            "Build a high-performance SEO and AEO platform that ranks on Google, "
            "wins citations in AI answers, and turns authority into inbound leads."
        )
    )
    proprietary_method_name = models.CharField(max_length=120, default="VRT Authority Engine")
    primary_cta_label = models.CharField(max_length=80, default="Request a Free AEO Audit")
    secondary_cta_label = models.CharField(max_length=80, default="Talk to a Strategist")

    class Meta:
        verbose_name_plural = "site settings"

    def __str__(self):
        return self.brand_name

# Create your models here.
