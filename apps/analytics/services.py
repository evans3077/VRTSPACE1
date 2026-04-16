from collections import Counter
from datetime import timedelta

from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.leads.models import AuditRequest, ClientProject, Lead


def _series_map(queryset, date_field):
    rows = (
        queryset.annotate(bucket=TruncDate(date_field))
        .values("bucket")
        .annotate(total=Count("id"))
        .order_by("bucket")
    )
    return {row["bucket"]: row["total"] for row in rows if row["bucket"]}


def _daily_activity(days=7):
    today = timezone.localdate()
    start_date = today - timedelta(days=days - 1)

    leads = Lead.objects.filter(created_at__date__gte=start_date)
    audits = AuditRequest.objects.filter(created_at__date__gte=start_date)

    lead_map = _series_map(leads, "created_at")
    audit_map = _series_map(audits, "created_at")

    series = []
    for offset in range(days):
        day = start_date + timedelta(days=offset)
        series.append(
            {
                "label": day.strftime("%b %d"),
                "date": day,
                "leads": lead_map.get(day, 0),
                "audits": audit_map.get(day, 0),
            }
        )
    return series


def _weekly_activity(weeks=8):
    today = timezone.localdate()
    start_date = today - timedelta(days=(weeks * 7) - 1)

    series = []
    for offset in range(weeks):
        week_start = start_date + timedelta(days=offset * 7)
        week_end = min(week_start + timedelta(days=6), today)
        leads = Lead.objects.filter(created_at__date__gte=week_start, created_at__date__lte=week_end).count()
        audits = AuditRequest.objects.filter(created_at__date__gte=week_start, created_at__date__lte=week_end).count()
        series.append(
            {
                "label": f"{week_start.strftime('%b %d')} - {week_end.strftime('%b %d')}",
                "leads": leads,
                "audits": audits,
            }
        )
    return series


def _top_geo_breakdown():
    country_counts = Counter()
    region_counts = Counter()

    for item in Lead.objects.values_list("submission_context", flat=True):
        context = item or {}
        if context.get("country"):
            country_counts[context["country"]] += 1
        if context.get("region"):
            region_counts[context["region"]] += 1

    for item in AuditRequest.objects.values_list("submission_context", flat=True):
        context = item or {}
        if context.get("country"):
            country_counts[context["country"]] += 1
        if context.get("region"):
            region_counts[context["region"]] += 1

    return {
        "countries": [
            {"label": label, "count": count}
            for label, count in country_counts.most_common(8)
        ],
        "regions": [
            {"label": label, "count": count}
            for label, count in region_counts.most_common(8)
        ],
    }


def _interest_area_mix():
    label_map = dict(Lead.InterestArea.choices)
    rows = (
        Lead.objects.values("interest_area")
        .annotate(total=Count("id"))
        .order_by("-total", "interest_area")
    )
    return [
        {
            "key": row["interest_area"],
            "label": label_map.get(row["interest_area"], row["interest_area"]),
            "count": row["total"],
        }
        for row in rows
    ]


def build_admin_dashboard_snapshot():
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())

    leads_qs = Lead.objects.all()
    audits_qs = AuditRequest.objects.all()
    projects_qs = ClientProject.objects.all()

    recent_leads = list(
        leads_qs.order_by("-created_at")[:10]
    )
    recent_audits = list(
        audits_qs.order_by("-created_at")[:10]
    )

    return {
        "kpis": {
            "leads_today": leads_qs.filter(created_at__gte=today_start).count(),
            "leads_week": leads_qs.filter(created_at__gte=week_start).count(),
            "audits_today": audits_qs.filter(created_at__gte=today_start).count(),
            "audits_week": audits_qs.filter(created_at__gte=week_start).count(),
            "qualified_audits": audits_qs.filter(status=AuditRequest.Status.QUALIFIED).count(),
            "active_projects": projects_qs.exclude(stage=ClientProject.Stage.ARCHIVED).count(),
        },
        "daily_activity": _daily_activity(),
        "weekly_activity": _weekly_activity(),
        "interest_mix": _interest_area_mix(),
        "geo_breakdown": _top_geo_breakdown(),
        "stage_mix": [
            {"label": label, "count": projects_qs.filter(stage=key).count()}
            for key, label in ClientProject.Stage.choices
        ],
        "recent_leads": recent_leads,
        "recent_audits": recent_audits,
    }
