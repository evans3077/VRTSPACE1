from django.contrib import admin

from .models import (
    BacklinkProspect,
    BacklinkSnapshot,
    FAQ,
    SEOCampaign,
    SEOCompetitor,
    SEOCompetitorSnapshot,
    SEOContextSnapshot,
    SEOOpportunitySnapshot,
    SEOProjectProfile,
    SEOSiteStructureSnapshot,
)


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ("question", "service", "article", "case_study", "order")


@admin.register(SEOProjectProfile)
class SEOProjectProfileAdmin(admin.ModelAdmin):
    list_display = ("project", "business_type", "location", "target_goal", "updated_at")
    search_fields = ("project__name", "project__normalized_domain", "location", "target_goal")


@admin.register(SEOContextSnapshot)
class SEOContextSnapshotAdmin(admin.ModelAdmin):
    list_display = ("project", "source_audit_run", "created_at")
    search_fields = ("project__name", "project__normalized_domain")


@admin.register(SEOOpportunitySnapshot)
class SEOOpportunitySnapshotAdmin(admin.ModelAdmin):
    list_display = ("project", "source_audit_run", "created_at")
    search_fields = ("project__name", "project__normalized_domain")


@admin.register(SEOCompetitor)
class SEOCompetitorAdmin(admin.ModelAdmin):
    list_display = ("project", "normalized_domain", "source", "is_active", "updated_at")
    search_fields = ("project__name", "normalized_domain", "homepage_url")
    list_filter = ("source", "is_active")


@admin.register(SEOCampaign)
class SEOCampaignAdmin(admin.ModelAdmin):
    list_display = ("title", "project", "status", "owner", "priority_score", "due_date", "updated_at")
    search_fields = ("title", "project__name", "target_keyword")
    list_filter = ("status", "page_type")


@admin.register(SEOCompetitorSnapshot)
class SEOCompetitorSnapshotAdmin(admin.ModelAdmin):
    list_display = ("competitor", "source_audit_run", "created_at")
    search_fields = ("competitor__normalized_domain", "competitor__project__name")


@admin.register(SEOSiteStructureSnapshot)
class SEOSiteStructureSnapshotAdmin(admin.ModelAdmin):
    list_display = ("project", "source_audit_run", "created_at")
    search_fields = ("project__name", "project__normalized_domain")


@admin.register(BacklinkSnapshot)
class BacklinkSnapshotAdmin(admin.ModelAdmin):
    list_display = ("project", "source_audit_run", "created_at")
    search_fields = ("project__name", "project__normalized_domain")
    readonly_fields = ("output_json",)


@admin.register(BacklinkProspect)
class BacklinkProspectAdmin(admin.ModelAdmin):
    list_display = ("domain", "project", "prospect_type", "status", "total_score", "target_asset_title", "updated_at")
    search_fields = ("domain", "title", "project__name", "target_asset_title", "prospect_url")
    list_filter = ("prospect_type", "status")
    readonly_fields = ("outreach_packet", "metadata")
