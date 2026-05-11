"""Read-side helpers for the referral cookie.

The cookie is written by the /r/<slug>/ redirect view, not here, because
writing happens at one specific URL whereas reading happens at every
signup. Splitting concerns keeps the middleware footprint small and
side-effect free.
"""
from __future__ import annotations

from django.conf import settings


def get_referral_slug_from_request(request) -> str:
    """Return the referral slug stamped on this visitor, or empty string.

    Order of precedence:
      1. ?ref=<slug> query param (allows manual override / link sharing).
      2. The persisted cookie set by the /r/<slug>/ redirect.
    """
    ref = (request.GET.get("ref") or "").strip().lower()
    if ref:
        return ref[:64]
    cookie_name = getattr(settings, "AFFILIATE_COOKIE_NAME", "vrt_ref")
    return (request.COOKIES.get(cookie_name) or "").strip().lower()[:64]
