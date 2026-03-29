from urllib.parse import urlencode

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.crypto import get_random_string


GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


class GoogleOAuthError(Exception):
    pass


def is_google_oauth_enabled():
    return settings.GOOGLE_OAUTH_ENABLED


def create_google_oauth_state():
    return get_random_string(40)


def build_google_authorize_url(*, redirect_uri, state):
    params = {
        "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "prompt": "select_account",
    }
    return f"{GOOGLE_AUTHORIZE_URL}?{urlencode(params)}"


def exchange_google_code_for_userinfo(*, code, redirect_uri):
    token_response = requests.post(
        GOOGLE_TOKEN_URL,
        data={
            "code": code,
            "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
        timeout=15,
    )
    if token_response.status_code != 200:
        raise GoogleOAuthError("Google token exchange failed.")

    access_token = (token_response.json() or {}).get("access_token")
    if not access_token:
        raise GoogleOAuthError("Google did not return an access token.")

    profile_response = requests.get(
        GOOGLE_USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15,
    )
    if profile_response.status_code != 200:
        raise GoogleOAuthError("Google user profile lookup failed.")

    profile = profile_response.json() or {}
    if not profile.get("email"):
        raise GoogleOAuthError("Google account did not return an email address.")
    return profile


def get_or_create_user_from_google_profile(profile):
    email = profile["email"].strip().lower()
    user_model = get_user_model()
    user = (
        user_model.objects.filter(email__iexact=email).first()
        or user_model.objects.filter(username__iexact=email).first()
    )
    if user:
        updated_fields = []
        if user.email != email:
            user.email = email
            updated_fields.append("email")
        if not user.first_name and profile.get("given_name"):
            user.first_name = profile["given_name"][:150]
            updated_fields.append("first_name")
        if not user.last_name and profile.get("family_name"):
            user.last_name = profile["family_name"][:150]
            updated_fields.append("last_name")
        if updated_fields:
            user.save(update_fields=updated_fields)
        return user

    user = user_model.objects.create_user(
        username=email,
        email=email,
        first_name=(profile.get("given_name") or "")[:150],
        last_name=(profile.get("family_name") or "")[:150],
    )
    user.set_unusable_password()
    user.save(update_fields=["password"])
    return user
