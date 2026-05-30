from .billing import get_billing_state
from .services import get_workspace_project_summaries, get_workspace_projects, resolve_workspace_project


def workspace_projects(request):
    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False) or getattr(user, "is_staff", False):
        return {
            "workspace_projects": [],
            "workspace_project_summaries": [],
            "active_workspace_project": None,
            "workspace_billing_state": {},
            "workspace_nav_current": "",
        }

    path = request.path or ""
    nav_current = ""
    if path.startswith("/workspace/seo/"):
        nav_current = "seo"
    elif path.startswith("/workspace/prompts/"):
        nav_current = "prompts"
    elif path.startswith("/workspace/share-of-voice/"):
        nav_current = "sov"
    elif path.startswith("/workspace/aeo/"):
        nav_current = "aeo"
    elif path.startswith("/workspace/content/") or path.startswith("/workspace/cms/"):
        nav_current = "content"
    elif path.startswith("/workspace/agency/"):
        nav_current = "agency"
    elif path.startswith("/workspace/team/"):
        nav_current = "team"
    elif path.startswith("/workspace/"):
        nav_current = "workspace"
    elif path.startswith("/account/"):
        nav_current = "billing"
    elif path.startswith("/tools/audits/"):
        nav_current = "audits"
    elif path.startswith("/affiliates/"):
        nav_current = "affiliate"

    is_workspace = nav_current != ""

    return {
        "workspace_projects": get_workspace_projects(user),
        "workspace_project_summaries": get_workspace_project_summaries(user),
        "active_workspace_project": resolve_workspace_project(request=request, user=user),
        "workspace_billing_state": get_billing_state(user),
        "workspace_nav_current": nav_current,
        "is_workspace_shell": is_workspace,
    }
