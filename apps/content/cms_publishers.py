"""
P4 — Push GeneratedContent to a connected CMS as a DRAFT.

Currently implements WordPress via the REST API + Application Passwords.
Drafts only (per grill decision Q20) — never publishes directly. Users
finish the post in their CMS.
"""

from __future__ import annotations

import base64
import logging

import requests
from django.utils import timezone

from .models import (
    CMSCredential,
    CMSPushLog,
    ContentEditorialTask,
    GeneratedContent,
)

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 30


class CMSPushError(Exception):
    """Raised when a push cannot proceed (missing data / config)."""


def _pick_credential(project, platform: str | None = None) -> CMSCredential | None:
    qs = CMSCredential.objects.filter(project=project, is_active=True)
    if platform:
        qs = qs.filter(platform=platform)
    return qs.order_by("-updated_at").first()


def _resolve_content_for_task(task: ContentEditorialTask) -> GeneratedContent | None:
    if task.latest_generated_content_id:
        return task.latest_generated_content
    return (
        GeneratedContent.objects.filter(project=task.project)
        .order_by("-created_at")
        .first()
    )


def _build_wordpress_post_body(task: ContentEditorialTask, content: GeneratedContent) -> dict:
    """Map a GeneratedContent record onto WordPress REST API fields."""
    title = task.title or content.title or "Draft post"
    body = content.body or ""
    excerpt = (getattr(content, "meta_description", "") or content.offer_summary or "")[:160]
    return {
        "title": title,
        "status": "draft",  # always draft (Q20 decision)
        "content": body,
        "excerpt": excerpt,
    }


def push_to_wordpress(
    *,
    task: ContentEditorialTask,
    credential: CMSCredential | None = None,
    triggered_by=None,
) -> CMSPushLog:
    """Attempt to create a draft WordPress post from a ContentEditorialTask.

    Returns the CMSPushLog row (always created — success or failed).
    """
    credential = credential or _pick_credential(task.project, platform=CMSCredential.Platform.WORDPRESS)
    if not credential:
        raise CMSPushError("No WordPress credential configured for this project.")
    if not credential.site_url or not credential.username or not credential.app_password:
        raise CMSPushError("WordPress credential is incomplete (need site URL + username + app password).")

    content = _resolve_content_for_task(task)
    if not content:
        raise CMSPushError("No generated content available to push for this task.")

    payload = _build_wordpress_post_body(task, content)
    endpoint = credential.site_url.rstrip("/") + "/wp-json/wp/v2/posts"
    basic = base64.b64encode(
        f"{credential.username}:{credential.app_password}".encode("utf-8")
    ).decode("ascii")
    headers = {
        "Authorization": f"Basic {basic}",
        "Content-Type": "application/json",
    }

    log_kwargs = {
        "task": task,
        "credential": credential,
        "triggered_by": triggered_by,
    }

    try:
        response = requests.post(endpoint, json=payload, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        logger.warning("WordPress push failed: %s", exc)
        return CMSPushLog.objects.create(
            status=CMSPushLog.Status.FAILED,
            response_summary=f"Network error: {exc}",
            **log_kwargs,
        )

    if response.status_code in (200, 201):
        try:
            data = response.json()
        except ValueError:
            data = {}
        post_id = str(data.get("id") or "")
        post_url = data.get("link") or ""
        credential.last_used_at = timezone.now()
        credential.save(update_fields=["last_used_at", "updated_at"])
        return CMSPushLog.objects.create(
            status=CMSPushLog.Status.SUCCESS,
            remote_post_id=post_id,
            remote_post_url=post_url,
            response_summary=f"Created draft post #{post_id}",
            **log_kwargs,
        )

    # Failed — capture short body for diagnostics
    body_excerpt = (response.text or "")[:600]
    return CMSPushLog.objects.create(
        status=CMSPushLog.Status.FAILED,
        response_summary=f"HTTP {response.status_code}: {body_excerpt}",
        **log_kwargs,
    )
