"""
P3 — Multi-user agency collaboration.

Three roles (per grill decision Q18):
    OWNER: full control, billing, can invite + remove anyone.
    MEMBER: full workspace access for the project, cannot manage billing.
    CLIENT: read-only access. Accessed via magic link, no signup required.

Seat limits are read from the plan catalog (free=1, starter=3, growth=10,
authority=25).  The hard ceiling is enforced at invite time.

Lifecycle:
    1. Owner submits an email + role -> WorkspaceMembership row in PENDING.
    2. For OWNER/MEMBER invites -> email contains a signup/login magic link.
       When the invitee logs in / signs up with that email, the membership
       resolves to their user account.
    3. For CLIENT invites -> the magic_token grants read-only access to the
       project dashboard via /share/clients/<token>/. No user record is
       created; the share is revocable.
"""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from .models import (
    ROLE_CLIENT,
    ROLE_MEMBER,
    ROLE_OWNER,
    WorkspaceMembership,
)


# Seat caps per plan slug (per grill decision Q19).
PLAN_SEAT_LIMITS = {
    "free": 1,
    "starter": 3,
    "growth": 10,
    "authority": 25,
}


class SeatLimitExceeded(Exception):
    """Raised when the owner has hit their plan's seat cap."""


def get_seat_limit_for_user(user) -> int:
    """Return the maximum number of seats this owner is allowed to use."""
    from .billing import get_workspace_subscription

    sub = get_workspace_subscription(user)
    plan_slug = sub.plan.slug if (sub and sub.plan) else "free"
    return PLAN_SEAT_LIMITS.get(plan_slug, 1)


def count_active_seats(owner) -> int:
    """Count active OWNER + MEMBER memberships across the user's projects.
    CLIENT memberships are free (don't count against seats). The owner
    themselves counts as 1 (implicit).
    """
    return (
        WorkspaceMembership.objects.filter(
            project__owner=owner,
            role__in=(WorkspaceMembership.Role.OWNER, WorkspaceMembership.Role.MEMBER),
            status=WorkspaceMembership.Status.ACTIVE,
        ).count()
        + 1
    )


def get_project_role(user, project):
    """Return the role string for this user on this project, or None."""
    if not user or not getattr(user, "is_authenticated", False) or not project:
        return None
    if project.owner_id == user.id:
        return ROLE_OWNER
    membership = WorkspaceMembership.objects.filter(
        project=project,
        user=user,
        status=WorkspaceMembership.Status.ACTIVE,
    ).first()
    return membership.role if membership else None


def user_can_access_project(user, project) -> bool:
    return get_project_role(user, project) is not None


def user_can_manage_project(user, project) -> bool:
    """Owner + Member can both edit; Client cannot."""
    role = get_project_role(user, project)
    return role in (ROLE_OWNER, ROLE_MEMBER)


def user_can_manage_billing(user, project) -> bool:
    return get_project_role(user, project) == ROLE_OWNER


def invite_member(
    *,
    project,
    inviter,
    email: str,
    role: str,
    expires_in_days: int = 30,
) -> WorkspaceMembership:
    """Create (or refresh) a membership invite.

    For OWNER/MEMBER invites we check the seat limit; CLIENT invites are
    seat-free.
    """
    email = (email or "").strip().lower()
    if role not in (ROLE_OWNER, ROLE_MEMBER, ROLE_CLIENT):
        raise ValueError(f"Unknown role: {role}")

    if role != ROLE_CLIENT:
        limit = get_seat_limit_for_user(inviter)
        if count_active_seats(inviter) >= limit:
            raise SeatLimitExceeded(
                f"Your plan allows {limit} seat(s). Upgrade to invite more team members."
            )

    membership, _created = WorkspaceMembership.objects.update_or_create(
        project=project,
        invited_email=email,
        defaults={
            "role": role,
            "status": WorkspaceMembership.Status.PENDING,
            "invited_by": inviter,
            "magic_expires_at": timezone.now() + timedelta(days=expires_in_days),
        },
    )
    return membership


def resolve_invite_for_user(*, user, token: str):
    """Match an invite token to a logged-in user and activate it."""
    membership = WorkspaceMembership.objects.filter(magic_token=token).first()
    if not membership or not membership.magic_active:
        return None
    if not user or not getattr(user, "is_authenticated", False):
        return None
    membership.user = user
    membership.status = WorkspaceMembership.Status.ACTIVE
    membership.accepted_at = timezone.now()
    membership.save(update_fields=["user", "status", "accepted_at", "updated_at"])
    return membership


def revoke_membership(membership: WorkspaceMembership) -> None:
    membership.status = WorkspaceMembership.Status.REVOKED
    membership.save(update_fields=["status", "updated_at"])


def get_client_share_membership(token: str):
    """Return an ACTIVE/PENDING client membership for the given magic token."""
    membership = (
        WorkspaceMembership.objects.select_related("project", "project__owner")
        .filter(magic_token=token, role=ROLE_CLIENT)
        .first()
    )
    if not membership or not membership.magic_active:
        return None
    return membership


# ─── Plan / Seat Helpers ────────────────────────────────────────────────────

def get_seat_limit_for_user(user) -> int:
    """Return the maximum number of seats this owner is allowed to use."""
    from .billing import get_workspace_subscription  # local import to avoid cycles

    sub = get_workspace_subscription(user)
    plan_slug = sub.plan.slug if (sub and sub.plan) else "free"
    return PLAN_SEAT_LIMITS.get(plan_slug, 1)


def count_active_seats(owner) -> int:
    """Count active OWNER + MEMBER memberships across the user's projects.
    CLIENT memberships are free (don't count against seats).
    """
    return WorkspaceMembership.objects.filter(
        project__owner=owner,
        role__in=(WorkspaceMembership.Role.OWNER, WorkspaceMembership.Role.MEMBER),
        status=WorkspaceMembership.Status.ACTIVE,
    ).count() + 1  # +1 for the owner themselves (implicit)


# ─── Access Helpers ─────────────────────────────────────────────────────────

def get_project_role(user, project) -> str | None:
    """Return the role string for this user on this project, or None."""
    if not user or not getattr(user, "is_authenticated", False) or not project:
        return None
    if project.owner_id == user.id:
        return ROLE_OWNER
    membership = WorkspaceMembership.objects.filter(
        project=project,
        user=user,
        status=WorkspaceMembership.Status.ACTIVE,
    ).first()
    return membership.role if membership else None


def user_can_access_project(user, project) -> bool:
    return get_project_role(user, project) is not None


def user_can_manage_project(user, project) -> bool:
    """Owner + Member can both edit; Client cannot."""
    role = get_project_role(user, project)
    return role in (ROLE_OWNER, ROLE_MEMBER)


def user_can_manage_billing(user, project) -> bool:
    return get_project_role(user, project) == ROLE_OWNER


# ─── Invite Lifecycle ───────────────────────────────────────────────────────

class SeatLimitExceeded(Exception):
    """Raised when the owner has hit their plan's seat cap."""


def invite_member(
    *,
    project,
    inviter,
    email: str,
    role: str,
    expires_in_days: int = 30,
) -> WorkspaceMembership:
    """Create (or refresh) a membership invite.

    For OWNER/MEMBER invites we check the seat limit; CLIENT invites are
    seat-free.
    """
    email = (email or "").strip().lower()
    if role not in (ROLE_OWNER, ROLE_MEMBER, ROLE_CLIENT):
        raise ValueError(f"Unknown role: {role}")

    if role != ROLE_CLIENT:
        limit = get_seat_limit_for_user(inviter)
        if count_active_seats(inviter) >= limit:
            raise SeatLimitExceeded(
                f"Your plan allows {limit} seat(s). Upgrade to invite more team members."
            )

    membership, _created = WorkspaceMembership.objects.update_or_create(
        project=project,
        invited_email=email,
        defaults={
            "role": role,
            "status": WorkspaceMembership.Status.PENDING,
            "invited_by": inviter,
            "magic_expires_at": timezone.now() + timedelta(days=expires_in_days),
        },
    )
    return membership


def resolve_invite_for_user(*, user, token: str) -> WorkspaceMembership | None:
    """Match an invite token to a logged-in user and activate it."""
    membership = WorkspaceMembership.objects.filter(magic_token=token).first()
    if not membership or not membership.magic_active:
        return None
    if not user or not getattr(user, "is_authenticated", False):
        return None
    membership.user = user
    membership.status = WorkspaceMembership.Status.ACTIVE
    membership.accepted_at = timezone.now()
    membership.save(
        update_fields=["user", "status", "accepted_at", "updated_at"]
    )
    return membership


def revoke_membership(membership: WorkspaceMembership) -> None:
    membership.status = WorkspaceMembership.Status.REVOKED
    membership.save(update_fields=["status", "updated_at"])


def get_client_share_membership(token: str) -> WorkspaceMembership | None:
    """Return an ACTIVE/PENDING client membership for the given magic token."""
    membership = (
        WorkspaceMembership.objects.select_related("project", "project__owner")
        .filter(magic_token=token, role=ROLE_CLIENT)
        .first()
    )
    if not membership or not membership.magic_active:
        return None
    return membership
