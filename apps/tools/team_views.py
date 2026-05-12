"""
P3 — Team management views.

Owners can:
    - View team list per project
    - Invite members (OWNER/MEMBER/CLIENT) — seat limit enforced
    - Revoke members
    - See a client share URL they can copy
"""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View

from apps.leads.membership import (
    PLAN_SEAT_LIMITS,
    SeatLimitExceeded,
    count_active_seats,
    get_client_share_membership,
    get_project_role,
    get_seat_limit_for_user,
    invite_member,
    resolve_invite_for_user,
    revoke_membership,
)
from apps.leads.models import (
    ROLE_CLIENT,
    ROLE_MEMBER,
    ROLE_OWNER,
    ClientProject,
    WorkspaceMembership,
)


def _get_active_project(user, request):
    """Return the user's currently-active project (owned)."""
    project_id = request.session.get("active_project_id")
    qs = ClientProject.objects.filter(owner=user)
    if project_id:
        project = qs.filter(pk=project_id).first()
        if project:
            return project
    return qs.first()


class WorkspaceTeamView(LoginRequiredMixin, View):
    template_name = "tools/workspace_team.html"

    def get(self, request, *args, **kwargs):
        project = _get_active_project(request.user, request)
        if not project:
            messages.info(request, "Create a project before inviting collaborators.")
            return redirect("tools:workspace-onboarding")

        memberships = list(
            WorkspaceMembership.objects.filter(project=project)
            .select_related("user", "invited_by")
            .order_by("role", "-created_at")
        )
        seat_limit = get_seat_limit_for_user(request.user)
        seats_used = count_active_seats(request.user)
        client_link_token = next(
            (
                m.magic_token
                for m in memberships
                if m.role == ROLE_CLIENT and m.magic_active
            ),
            "",
        )
        client_share_url = (
            request.build_absolute_uri(
                reverse("tools:client-shared-project", kwargs={"token": client_link_token})
            )
            if client_link_token
            else ""
        )

        return render(
            request,
            self.template_name,
            {
                "project": project,
                "memberships": memberships,
                "seat_limit": seat_limit,
                "seats_used": seats_used,
                "seats_remaining": max(seat_limit - seats_used, 0),
                "plan_seat_limits": PLAN_SEAT_LIMITS,
                "client_share_url": client_share_url,
                "workspace_nav_current": "team",
                "page_title": f"{project.name} — Team & Sharing | VRT SPACE AGENCY",
                "meta_description": "Manage workspace seats and client share links.",
                "meta_robots": "noindex, nofollow",
                "canonical_url": request.build_absolute_uri(request.path),
                "shell_theme": "shell-light",
            },
        )

    def post(self, request, *args, **kwargs):
        project = _get_active_project(request.user, request)
        if not project:
            messages.error(request, "No active project to invite to.")
            return redirect("tools:workspace-team")

        role = request.POST.get("role", "").strip().lower()
        email = request.POST.get("email", "").strip().lower()
        if role not in (ROLE_OWNER, ROLE_MEMBER, ROLE_CLIENT):
            messages.error(request, "Choose a valid role.")
            return redirect("tools:workspace-team")
        if role != ROLE_CLIENT and not email:
            messages.error(request, "Provide an email to invite a teammate.")
            return redirect("tools:workspace-team")

        try:
            membership = invite_member(
                project=project,
                inviter=request.user,
                email=email or f"client+{project.pk}@vrtspace.local",
                role=role,
            )
        except SeatLimitExceeded as exc:
            messages.error(request, str(exc))
            return redirect("tools:workspace-team")
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect("tools:workspace-team")

        if role == ROLE_CLIENT:
            share_url = request.build_absolute_uri(
                reverse(
                    "tools:client-shared-project",
                    kwargs={"token": membership.magic_token},
                )
            )
            messages.success(
                request,
                f"Client share link ready. Copy and send: {share_url}",
            )
        else:
            accept_url = request.build_absolute_uri(
                reverse(
                    "tools:workspace-invite-accept",
                    kwargs={"token": membership.magic_token},
                )
            )
            messages.success(
                request,
                f"Invite created for {email}. They can accept at: {accept_url}",
            )
        return redirect("tools:workspace-team")


class RevokeMemberView(LoginRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        membership = get_object_or_404(
            WorkspaceMembership.objects.select_related("project"),
            pk=pk,
        )
        # Only the project owner can revoke.
        if get_project_role(request.user, membership.project) != ROLE_OWNER:
            raise Http404
        revoke_membership(membership)
        messages.success(request, "Access revoked.")
        return redirect("tools:workspace-team")


class AcceptInviteView(LoginRequiredMixin, View):
    """Logged-in user clicks the email link, gets attached to the project."""

    def get(self, request, token, *args, **kwargs):
        membership = resolve_invite_for_user(user=request.user, token=token)
        if not membership:
            messages.error(request, "Invite link is invalid or expired.")
            return redirect("tools:workspace-dashboard")
        messages.success(
            request,
            f"You're now a {membership.get_role_display().lower()} on {membership.project.name}.",
        )
        request.session["active_project_id"] = membership.project_id
        return redirect("tools:workspace-dashboard")


class ClientSharedProjectView(View):
    """Read-only project view for a CLIENT magic-link recipient.

    No authentication required — the magic token IS the credential.
    """

    template_name = "tools/client_shared_project.html"

    def get(self, request, token, *args, **kwargs):
        membership = get_client_share_membership(token)
        if not membership:
            raise Http404("Share link is invalid or expired.")
        project = membership.project
        latest_audit = getattr(project, "latest_audit_run", None)
        summary = (latest_audit.summary if latest_audit else {}) or {}
        return render(
            request,
            self.template_name,
            {
                "project": project,
                "latest_audit": latest_audit,
                "summary": summary,
                "recommendations": (summary.get("featured_recommendations") or summary.get("recommendations", []))[:6],
                "page_title": f"{project.name} — Read-only Workspace",
                "meta_description": "Read-only project view shared by your VRT SPACE workspace owner.",
                "meta_robots": "noindex, nofollow",
                "canonical_url": request.build_absolute_uri(request.path),
                "shell_theme": "shell-light",
                "is_client_share": True,
            },
        )
