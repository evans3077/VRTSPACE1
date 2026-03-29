from django.contrib import admin

from .models import Article, Service


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

# Register your models here.
