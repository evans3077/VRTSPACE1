from .billing import get_billing_state
from .services import get_workspace_projects, resolve_workspace_project


def workspace_projects(request):
    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False) or getattr(user, "is_staff", False):
        return {
            "workspace_projects": [],
            "active_workspace_project": None,
            "workspace_billing_state": {},
            "workspace_nav_current": "",
        }

    path = request.path or ""
    nav_current = ""
    if path.startswith("/workspace/seo/"):
        nav_current = "seo"
    elif path.startswith("/workspace/aeo/"):
        nav_current = "aeo"
    elif path.startswith("/workspace/content/"):
        nav_current = "content"
    elif path.startswith("/workspace/"):
        nav_current = "workspace"
    elif path.startswith("/tools/audits/"):
        nav_current = "audits"

    return {
        "workspace_projects": get_workspace_projects(user),
        "active_workspace_project": resolve_workspace_project(request=request, user=user),
        "workspace_billing_state": get_billing_state(user),
        "workspace_nav_current": nav_current,
    }
