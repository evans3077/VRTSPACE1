from django.contrib import admin
from django.utils.safestring import mark_safe

from .admin_utils import format_score_pill, get_service_recommendations, get_score_color
from .models import AuditIssue, AuditPage, AuditRun, ToolDefinition


@admin.register(ToolDefinition)
class ToolDefinitionAdmin(admin.ModelAdmin):
    list_display = ("name", "endpoint_path", "is_public")
    list_filter = ("is_public",)
    prepopulated_fields = {"slug": ("name",)}


class AuditPageInline(admin.TabularInline):
    model = AuditPage
    extra = 0
    fields = (
        "url",
        "status_code",
        "title",
        "word_count",
        "internal_link_count",
        "schema_count",
        "response_time_ms",
    )
    readonly_fields = fields
    can_delete = False


class AuditIssueInline(admin.StackedInline):
    model = AuditIssue
    extra = 0
    fields = ("code", "category", "severity", "message", "recommendation")
    readonly_fields = fields
    can_delete = False


@admin.register(AuditRun)
class AuditRunAdmin(admin.ModelAdmin):
    list_display = (
        "normalized_domain",
        "tool_type",
        "status",
        "overall_score_pill",
        "pages_crawled",
        "created_at",
    )
    list_filter = ("status", "tool_type")
    search_fields = ("normalized_domain", "start_url")
    readonly_fields = (
        "pretty_summary",
        "service_recommendations_html",
        "overall_score_pill",
        "technical_score_pill",
        "on_page_score_pill",
        "content_score_pill",
        "aeo_score_pill",
        "internal_linking_score_pill",
        "performance_score_pill",
        "pages_crawled",
        "error_message",
        "completed_at",
    )
    
    fieldsets = (
        ("Context", {"fields": ("audit_request", "start_url", "normalized_domain", "tool_type", "status", "completed_at")}),
        ("Concierge Advice", {"fields": ("service_recommendations_html", "pretty_summary")}),
        ("Scores", {"fields": (
            "overall_score_pill", 
            "technical_score_pill", 
            "on_page_score_pill", 
            "content_score_pill", 
            "aeo_score_pill", 
            "internal_linking_score_pill", 
            "performance_score_pill"
        )}),
        ("Errors", {"fields": ("error_message",), "classes": ("collapse",)}),
    )
    
    inlines = [AuditPageInline, AuditIssueInline]

    @admin.display(description="Result Summary")
    def pretty_summary(self, obj):
        if not obj.summary:
            return "No summary data available."
        
        # Build a small dashboard table
        html = '<table style="width: 100%; border-collapse: collapse; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; font-family: sans-serif;">'
        html += '<tr style="background: #eef2f6;"><th style="padding: 10px; text-align: left; border-bottom: 1px solid #cbd5e1;">Metric</th><th style="padding: 10px; text-align: left; border-bottom: 1px solid #cbd5e1;">Value</th></tr>'
        
        # Overall
        html += f'<tr><td style="padding: 8px; border-bottom: 1px solid #f1f5f9;"><b>Overall Score</b></td><td style="padding: 8px; border-bottom: 1px solid #f1f5f9;">{format_score_pill(obj.overall_score)}</td></tr>'
        
        # Pagespeed if exists
        pagespeed = obj.summary.get("pagespeed")
        if pagespeed:
            metrics = pagespeed.get("metrics", {})
            html += f'<tr><td style="padding: 8px; border-bottom: 1px solid #f1f5f9; background: #fffbeb;"><b>PageSpeed Strategy</b></td><td style="padding: 8px; border-bottom: 1px solid #f1f5f9; background: #fffbeb;">{pagespeed.get("strategy")}</td></tr>'
            for key, val in metrics.items():
                label = key.replace("_", " ").title()
                html += f'<tr><td style="padding: 8px; border-bottom: 1px solid #f1f5f9;">{label}</td><td style="padding: 8px; border-bottom: 1px solid #f1f5f9;">{val}</td></tr>'
        
        # Top Issues List
        top_issues = obj.summary.get("top_issues", [])
        if top_issues:
            html += '<tr><td colspan="2" style="padding: 12px; background: #f1f5f9; font-weight: bold;">Priority Action Items</td></tr>'
            for issue in top_issues:
                html += f'<tr><td style="padding: 8px; border-bottom: 1px solid #f1f5f9;">{issue["message"]}</td><td style="padding: 8px; border-bottom: 1px solid #f1f5f9; color: #64748b; font-size: 0.9em;">{issue["recommendation"]}</td></tr>'
                
        html += "</table>"
        return mark_safe(html)

    @admin.display(description="Agency Upsells & Advice")
    def service_recommendations_html(self, obj):
        recs = get_service_recommendations(obj)
        if not recs:
            return mark_safe('<div style="color: #059669; font-weight: bold;">✅ Site is in excellent condition. No urgent service needed.</div>')
        
        html = '<div style="display: grid; gap: 10px;">'
        for r in recs:
            html += f"""
            <div style="padding: 12px; border: 1px solid #e2e8f0; border-left: 5px solid {r['color']}; border-radius: 6px; background: #ffffff;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                    <span style="font-weight: 800; color: #1e293b;">Category: {r['category']}</span>
                    <span style="background: {r['color']}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.8em;">Score: {r['score']}</span>
                </div>
                <div style="color: #2563eb; font-weight: bold; margin-bottom: 4px;">Recommended Service: {r['service']}</div>
                <div style="font-size: 0.9em; color: #475569; line-height: 1.4;"><b>Impact:</b> {r['impact']}</div>
            </div>
            """
        html += '</div>'
        return mark_safe(html)

    # Score Pill Helpers
    @admin.display(description="Overall")
    def overall_score_pill(self, obj): return format_score_pill(obj.overall_score)
    
    @admin.display(description="Technical")
    def technical_score_pill(self, obj): return format_score_pill(obj.technical_score)
    
    @admin.display(description="On-page")
    def on_page_score_pill(self, obj): return format_score_pill(obj.on_page_score)
    
    @admin.display(description="Content")
    def content_score_pill(self, obj): return format_score_pill(obj.content_score)
    
    @admin.display(description="AEO")
    def aeo_score_pill(self, obj): return format_score_pill(obj.aeo_score)
    
    @admin.display(description="Internal Linking")
    def internal_linking_score_pill(self, obj): return format_score_pill(obj.internal_linking_score)
    
    @admin.display(description="Performance")
    def performance_score_pill(self, obj): return format_score_pill(obj.performance_score)
