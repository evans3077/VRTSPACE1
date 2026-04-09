from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def seed_workspace_plans(apps, schema_editor):
    WorkspacePlan = apps.get_model("leads", "WorkspacePlan")
    plans = [
        {
            "slug": "starter",
            "name": "Starter",
            "price_label": "~$200",
            "description": "Entry plan for grouped recommendations and a limited workspace history.",
            "sort_order": 10,
            "monthly_audits_limit": 5,
            "history_limit": 5,
            "premium_recommendation_limit": 6,
            "recurring_audits_enabled": False,
            "export_reports_enabled": False,
        },
        {
            "slug": "growth",
            "name": "Growth",
            "price_label": "~$500",
            "description": "Team plan for more audits, broader history, and recurring monitoring.",
            "sort_order": 20,
            "monthly_audits_limit": 20,
            "history_limit": 20,
            "premium_recommendation_limit": 12,
            "recurring_audits_enabled": True,
            "export_reports_enabled": True,
        },
        {
            "slug": "authority",
            "name": "Authority",
            "price_label": "$1000+",
            "description": "Advanced visibility plan with deeper history, exports, and recurring audits.",
            "sort_order": 30,
            "monthly_audits_limit": 100,
            "history_limit": None,
            "premium_recommendation_limit": None,
            "recurring_audits_enabled": True,
            "export_reports_enabled": True,
        },
        {
            "slug": "enterprise",
            "name": "Enterprise",
            "price_label": "Custom",
            "description": "Reserved for custom environments and direct scope review.",
            "sort_order": 40,
            "monthly_audits_limit": None,
            "history_limit": None,
            "premium_recommendation_limit": None,
            "recurring_audits_enabled": True,
            "export_reports_enabled": True,
        },
    ]
    for plan in plans:
        WorkspacePlan.objects.update_or_create(slug=plan["slug"], defaults=plan)


class Migration(migrations.Migration):

    dependencies = [
        ("leads", "0004_clientproject_owner"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="WorkspacePlan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("slug", models.SlugField(unique=True)),
                ("name", models.CharField(max_length=80)),
                ("price_label", models.CharField(blank=True, max_length=80)),
                ("stripe_price_id", models.CharField(blank=True, max_length=120)),
                ("description", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("sort_order", models.PositiveSmallIntegerField(default=0)),
                ("monthly_audits_limit", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("history_limit", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("premium_recommendation_limit", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("recurring_audits_enabled", models.BooleanField(default=False)),
                ("export_reports_enabled", models.BooleanField(default=False)),
                ("metadata", models.JSONField(blank=True, default=dict)),
            ],
            options={"ordering": ("sort_order", "name")},
        ),
        migrations.CreateModel(
            name="WorkspaceSubscription",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("status", models.CharField(choices=[("inactive", "Inactive"), ("trialing", "Trialing"), ("active", "Active"), ("past_due", "Past Due"), ("canceled", "Canceled"), ("unpaid", "Unpaid")], default="inactive", max_length=24)),
                ("stripe_customer_id", models.CharField(blank=True, max_length=120)),
                ("stripe_subscription_id", models.CharField(blank=True, max_length=120)),
                ("stripe_checkout_session_id", models.CharField(blank=True, max_length=120)),
                ("current_period_end", models.DateTimeField(blank=True, null=True)),
                ("cancel_at_period_end", models.BooleanField(default=False)),
                ("last_webhook_event_id", models.CharField(blank=True, max_length=120)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("plan", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="subscriptions", to="leads.workspaceplan")),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="workspace_subscription", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-updated_at",)},
        ),
        migrations.CreateModel(
            name="UsageRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("metric", models.CharField(choices=[("audit_run", "Audit Run"), ("export", "Export")], max_length=32)),
                ("period_start", models.DateField()),
                ("period_end", models.DateField()),
                ("quantity", models.PositiveIntegerField(default=0)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("plan", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="usage_records", to="leads.workspaceplan")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="usage_records", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-period_start", "-updated_at")},
        ),
        migrations.AddConstraint(
            model_name="usagerecord",
            constraint=models.UniqueConstraint(fields=("user", "metric", "period_start", "period_end"), name="unique_usage_record_per_period"),
        ),
        migrations.RunPython(seed_workspace_plans, migrations.RunPython.noop),
    ]
