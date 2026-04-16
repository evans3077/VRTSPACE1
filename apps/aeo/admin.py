from django.contrib import admin

from .models import AEOAudit, AIRecommendation, VisibilitySnapshot


@admin.register(VisibilitySnapshot)
class VisibilitySnapshotAdmin(admin.ModelAdmin):
    list_display = ("engine", "answer_present", "citation_frequency", "created_at")
    list_filter = ("engine", "answer_present")


@admin.register(AEOAudit)
class AEOAuditAdmin(admin.ModelAdmin):
    list_display = (
        "project",
        "target_keyword",
        "visibility_score",
        "entity_score",
        "structure_score",
        "completeness_score",
        "created_at",
    )
    search_fields = ("project__name", "project__normalized_domain", "target_keyword")


@admin.register(AIRecommendation)
class AIRecommendationAdmin(admin.ModelAdmin):
    list_display = ("aeo_audit", "category", "priority_score", "issue")
    search_fields = ("issue", "category", "aeo_audit__project__name")
