from collections import Counter

from .models import AuditChangeReport, AuditRun


SCORE_FIELDS = (
    ("technical", "technical_score"),
    ("on_page", "on_page_score"),
    ("content", "content_score"),
    ("aeo", "aeo_score"),
    ("internal_linking", "internal_linking_score"),
    ("performance", "performance_score"),
)


def find_previous_completed_audit(audit_run, *, project=None):
    if project and getattr(project, "audit_request_id", None):
        return (
            AuditRun.objects.filter(
                audit_request=project.audit_request,
                status=AuditRun.Status.COMPLETED,
            )
            .exclude(pk=audit_run.pk)
            .order_by("-created_at")
            .first()
        )

    if audit_run.audit_request_id:
        return (
            AuditRun.objects.filter(
                audit_request_id=audit_run.audit_request_id,
                status=AuditRun.Status.COMPLETED,
            )
            .exclude(pk=audit_run.pk)
            .order_by("-created_at")
            .first()
        )

    return (
        AuditRun.objects.filter(
            normalized_domain=audit_run.normalized_domain,
            status=AuditRun.Status.COMPLETED,
        )
        .exclude(pk=audit_run.pk)
        .order_by("-created_at")
        .first()
    )


def build_issue_fingerprint(issue):
    return (
        issue.category,
        issue.code,
        issue.message,
        issue.page.url if issue.page_id and issue.page else "",
    )


def build_change_report_summary(audit_run, *, previous_audit_run=None):
    current_issues = list(audit_run.issues.select_related("page"))
    previous_issues = (
        list(previous_audit_run.issues.select_related("page"))
        if previous_audit_run
        else []
    )

    current_fingerprints = {build_issue_fingerprint(issue): issue for issue in current_issues}
    previous_fingerprints = {build_issue_fingerprint(issue): issue for issue in previous_issues}

    new_issue_keys = set(current_fingerprints) - set(previous_fingerprints)
    resolved_issue_keys = set(previous_fingerprints) - set(current_fingerprints)

    new_issues = [current_fingerprints[key] for key in new_issue_keys]
    resolved_issues = [previous_fingerprints[key] for key in resolved_issue_keys]

    overall_delta = audit_run.overall_score - (previous_audit_run.overall_score if previous_audit_run else audit_run.overall_score)
    pages_delta = audit_run.pages_crawled - (previous_audit_run.pages_crawled if previous_audit_run else audit_run.pages_crawled)

    score_deltas = []
    for label, field_name in SCORE_FIELDS:
        current_score = getattr(audit_run, field_name, 0) or 0
        previous_score = getattr(previous_audit_run, field_name, current_score) or 0
        delta = current_score - previous_score
        if delta:
            score_deltas.append(
                {
                    "metric": label,
                    "current": current_score,
                    "previous": previous_score,
                    "delta": delta,
                }
            )

    score_deltas.sort(key=lambda item: abs(item["delta"]), reverse=True)

    if not previous_audit_run:
        headline = "Baseline audit captured. Future reruns will show movement and newly detected issues."
        alert_level = "info"
    elif overall_delta > 0:
        headline = f"Overall score improved by {overall_delta} points since the previous audit."
        alert_level = "good"
    elif overall_delta < 0:
        headline = f"Overall score dropped by {abs(overall_delta)} points since the previous audit."
        alert_level = "warning"
    else:
        headline = "Overall score held steady since the previous audit."
        alert_level = "neutral"

    return {
        "headline": headline,
        "alert_level": alert_level,
        "score_deltas": score_deltas[:6],
        "new_issue_categories": dict(Counter(issue.category for issue in new_issues)),
        "resolved_issue_categories": dict(Counter(issue.category for issue in resolved_issues)),
        "new_issue_examples": [issue.message for issue in new_issues[:3]],
        "resolved_issue_examples": [issue.message for issue in resolved_issues[:3]],
        "current_issue_total": len(current_issues),
        "previous_issue_total": len(previous_issues),
    }, overall_delta, pages_delta, len(new_issues), len(resolved_issues)


def create_audit_change_report(audit_run, *, project=None, previous_audit_run=None):
    previous_audit_run = previous_audit_run or find_previous_completed_audit(audit_run, project=project)
    summary, overall_delta, pages_delta, new_issue_count, resolved_issue_count = build_change_report_summary(
        audit_run,
        previous_audit_run=previous_audit_run,
    )
    report, _created = AuditChangeReport.objects.update_or_create(
        audit_run=audit_run,
        defaults={
            "project": project,
            "previous_audit_run": previous_audit_run,
            "overall_score_delta": overall_delta,
            "pages_crawled_delta": pages_delta,
            "new_issue_count": new_issue_count,
            "resolved_issue_count": resolved_issue_count,
            "summary": summary,
        },
    )
    return report
