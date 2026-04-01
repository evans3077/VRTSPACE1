from urllib.parse import urlparse

from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import AuditRequest, ClientProject, Lead

ACTIVE_WORKSPACE_PROJECT_SESSION_KEY = "active_workspace_project_id"


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


def score_audit_request(*, website, monthly_leads_goal, notes, business_type="", location="", target_goal="", primary_service=""):
    score = 30 if website else 0
    if monthly_leads_goal >= 50:
        score += 30
    elif monthly_leads_goal >= 20:
        score += 20
    if business_type:
        score += 10
    if location:
        score += 10
    if target_goal:
        score += 10
    if primary_service:
        score += 10
    if notes and len(notes.strip()) >= 60:
        score += 20
    return min(score, 100)


def extract_submission_context(request, *, source_page=""):
    if request is None:
        return {}

    meta = request.META
    context = {
        "source_page": source_page or "",
        "referrer": meta.get("HTTP_REFERER", "")[:255],
        "host": meta.get("HTTP_HOST", "")[:120],
        "country": meta.get("HTTP_CF_IPCOUNTRY", "")[:8],
        "region": (
            meta.get("HTTP_CF_REGION")
            or meta.get("HTTP_X_REGION")
            or meta.get("HTTP_X_APPENGINE_REGION")
            or ""
        )[:120],
        "city": (
            meta.get("HTTP_CF_IPCITY")
            or meta.get("HTTP_X_CITY")
            or ""
        )[:120],
    }
    return {key: value for key, value in context.items() if value}


def create_lead_from_form(form, source_page, *, request=None):
    lead = form.save(commit=False)
    lead.source_page = source_page
    lead.submission_context = extract_submission_context(request, source_page=source_page)
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


def create_audit_request_from_form(form, *, request=None):
    audit_request = form.save(commit=False)
    audit_request.submission_context = extract_submission_context(request)
    audit_request.score = score_audit_request(
        website=audit_request.website,
        monthly_leads_goal=audit_request.monthly_leads_goal,
        notes=audit_request.notes,
        business_type=audit_request.business_type,
        location=audit_request.location,
        target_goal=audit_request.target_goal,
        primary_service=audit_request.primary_service,
    )
    if audit_request.score >= 75:
        audit_request.status = AuditRequest.Status.QUALIFIED
    audit_request.save()
    return audit_request


def get_workspace_project_queryset(user):
    if not user or not getattr(user, "is_authenticated", False):
        return ClientProject.objects.none()
    return (
        ClientProject.objects.select_related("latest_audit_run", "audit_request")
        .filter(owner=user)
        .order_by("name", "created_at")
    )


def get_workspace_projects(user):
    return list(get_workspace_project_queryset(user))


def resolve_workspace_project(request=None, user=None, *, project_id=None, fallback=True):
    user = user or getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return None

    queryset = get_workspace_project_queryset(user)
    if project_id is None and request is not None:
        project_id = request.GET.get("project") or request.POST.get("project")
    if project_id is None and request is not None:
        project_id = request.session.get(ACTIVE_WORKSPACE_PROJECT_SESSION_KEY)

    project = None
    if project_id:
        project = queryset.filter(pk=project_id).first()
    if project is None and fallback:
        project = queryset.order_by("-updated_at", "-created_at").first()

    if request is not None:
        if project is not None:
            request.session[ACTIVE_WORKSPACE_PROJECT_SESSION_KEY] = project.pk
        else:
            request.session.pop(ACTIVE_WORKSPACE_PROJECT_SESSION_KEY, None)
    return project


def set_active_workspace_project(request, project):
    if project is None:
        request.session.pop(ACTIVE_WORKSPACE_PROJECT_SESSION_KEY, None)
        return
    request.session[ACTIVE_WORKSPACE_PROJECT_SESSION_KEY] = project.pk


def sync_client_project_from_audit_run(audit_run):
    audit_request = audit_run.audit_request
    normalized_domain = audit_run.normalized_domain or urlparse(audit_run.start_url).netloc.lower()
    website = audit_run.start_url or (audit_request.website if audit_request else "")
    email = audit_request.email if audit_request else ""
    name = (audit_request.company_name if audit_request and audit_request.company_name else normalized_domain or website)
    business_type = audit_request.business_type if audit_request else ""
    location = audit_request.location if audit_request else ""
    target_goal = audit_request.target_goal if audit_request else ""
    primary_service = audit_request.primary_service if audit_request else ""

    if audit_request:
        project, _created = ClientProject.objects.get_or_create(
            audit_request=audit_request,
            defaults={
                "name": name,
                "website": website,
                "normalized_domain": normalized_domain,
                "contact_email": email,
                "business_type": business_type,
                "location": location,
                "target_goal": target_goal,
                "primary_service": primary_service,
            },
        )
    else:
        project = ClientProject.objects.filter(
            normalized_domain=normalized_domain,
            contact_email=email,
        ).first()
        if not project:
            project = ClientProject.objects.create(
                name=name,
                website=website,
                normalized_domain=normalized_domain,
                contact_email=email,
                business_type=business_type,
                location=location,
                target_goal=target_goal,
                primary_service=primary_service,
            )

    project.name = name or project.name
    project.website = website or project.website
    project.normalized_domain = normalized_domain
    project.contact_email = email or project.contact_email
    if business_type:
        project.business_type = business_type
    if location:
        project.location = location
    if target_goal:
        project.target_goal = target_goal
    if primary_service:
        project.primary_service = primary_service
    project.latest_audit_run = audit_run
    project.latest_score = audit_run.overall_score or 0
    if email:
        user = get_user_model().objects.filter(email__iexact=email).first()
        if user:
            project.owner = user
    if audit_request and audit_request.status == AuditRequest.Status.QUALIFIED:
        project.stage = ClientProject.Stage.PROPOSAL
    project.save()
    return project
