from .services import get_workspace_projects, resolve_workspace_project


def workspace_projects(request):
    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False) or getattr(user, "is_staff", False):
        return {"workspace_projects": [], "active_workspace_project": None}

    return {
        "workspace_projects": get_workspace_projects(user),
        "active_workspace_project": resolve_workspace_project(request=request, user=user),
    }
