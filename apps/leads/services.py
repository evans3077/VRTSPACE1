from django.db import connection
from django.utils import timezone

from apps.core.runtime import ensure_runtime_database

from .models import AuditRequest, Lead


def _ensure_model_table(model):
    table_name = model._meta.db_table

    with connection.cursor() as cursor:
        existing_tables = set(connection.introspection.table_names(cursor))

    if table_name in existing_tables:
        return

    with connection.schema_editor() as schema_editor:
        schema_editor.create_model(model)


def score_lead(*, company, website, message, interest_area):
    score = 10
    if company:
        score += 15
    if website:
        score += 25
    if message and len(message.strip()) >= 80:
        score += 20
    if interest_area in {Lead.InterestArea.AEO, Lead.InterestArea.SEO}:
        score += 20
    return min(score, 100)


def score_audit_request(*, website, monthly_leads_goal, notes):
    score = 30 if website else 0
    if monthly_leads_goal >= 50:
        score += 30
    elif monthly_leads_goal >= 20:
        score += 20
    if notes and len(notes.strip()) >= 60:
        score += 20
    return min(score, 100)


def create_lead_from_form(form, source_page):
    ensure_runtime_database(required_tables=("leads_lead",))
    _ensure_model_table(Lead)
    lead = form.save(commit=False)
    lead.source_page = source_page
    lead.score = score_lead(
        company=lead.company,
        website=lead.website,
        message=lead.message,
        interest_area=lead.interest_area,
    )
    if lead.score >= 70:
        lead.qualified_at = timezone.now()
    lead.save()
    return lead


def create_audit_request_from_form(form):
    ensure_runtime_database(required_tables=("leads_auditrequest",))
    _ensure_model_table(AuditRequest)
    audit_request = form.save(commit=False)
    audit_request.score = score_audit_request(
        website=audit_request.website,
        monthly_leads_goal=audit_request.monthly_leads_goal,
        notes=audit_request.notes,
    )
    if audit_request.score >= 75:
        audit_request.status = AuditRequest.Status.QUALIFIED
    audit_request.save()
    return audit_request
