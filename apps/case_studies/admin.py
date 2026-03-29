from django.contrib import admin

from .models import CaseStudy


@admin.register(CaseStudy)
class CaseStudyAdmin(admin.ModelAdmin):
    list_display = ("title", "client_name", "industry", "featured")
    list_filter = ("featured", "industry")
    prepopulated_fields = {"slug": ("title",)}

# Register your models here.
