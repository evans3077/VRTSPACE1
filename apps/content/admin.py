from django.contrib import admin

from .models import Article, ContentEditorialTask, GeneratedContent, Service


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("title", "featured", "order")
    list_filter = ("featured",)
    prepopulated_fields = {"slug": ("title",)}


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "is_pillar", "published_at")
    list_filter = ("status", "is_pillar")
    prepopulated_fields = {"slug": ("title",)}


@admin.register(GeneratedContent)
class GeneratedContentAdmin(admin.ModelAdmin):
    list_display = ("title", "output_type", "status", "project", "applied_target", "created_at")
    list_filter = ("output_type", "status")
    search_fields = ("title", "business_type", "target_audience", "project__name")
    readonly_fields = ("prompt_context", "output_json", "validation_json", "schema_json")

    @admin.display(description="Applied Target")
    def applied_target(self, obj):
        return obj.applied_service or obj.applied_article or "-"


@admin.register(ContentEditorialTask)
class ContentEditorialTaskAdmin(admin.ModelAdmin):
    list_display = ("title", "project", "status", "output_type", "priority_score", "updated_at")
    list_filter = ("status", "output_type")
    search_fields = ("title", "project__name", "brief_key")
    readonly_fields = ("brief_json", "metadata")

# Register your models here.
