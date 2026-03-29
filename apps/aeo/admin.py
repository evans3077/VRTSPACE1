from django.contrib import admin

from .models import VisibilitySnapshot


@admin.register(VisibilitySnapshot)
class VisibilitySnapshotAdmin(admin.ModelAdmin):
    list_display = ("engine", "answer_present", "citation_frequency", "created_at")
    list_filter = ("engine", "answer_present")

# Register your models here.
