from django.contrib import admin

from .models import (
    FAQ,
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


@admin.register(SEOCompetitorSnapshot)
class SEOCompetitorSnapshotAdmin(admin.ModelAdmin):
    list_display = ("competitor", "source_audit_run", "created_at")
    search_fields = ("competitor__normalized_domain", "competitor__project__name")


@admin.register(SEOSiteStructureSnapshot)
class SEOSiteStructureSnapshotAdmin(admin.ModelAdmin):
    list_display = ("project", "source_audit_run", "created_at")
    search_fields = ("project__name", "project__normalized_domain")
