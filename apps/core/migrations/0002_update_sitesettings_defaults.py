from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="sitesettings",
            name="hero_title",
            field=models.CharField(
                default="Turn your website into a measurable growth system.",
                max_length=255,
            ),
        ),
        migrations.AlterField(
            model_name="sitesettings",
            name="hero_subtitle",
            field=models.TextField(
                default=(
                    "Run the audit, open a workspace, track what is broken, and choose when "
                    "to unlock deeper monitoring, automation, and content systems."
                ),
            ),
        ),
        migrations.AlterField(
            model_name="sitesettings",
            name="primary_cta_label",
            field=models.CharField(default="Run Free Audit", max_length=80),
        ),
        migrations.AlterField(
            model_name="sitesettings",
            name="secondary_cta_label",
            field=models.CharField(default="Create Workspace", max_length=80),
        ),
    ]
