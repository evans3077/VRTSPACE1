from django.core.cache import cache
from django.core.exceptions import ValidationError

import requests

from .intake_options import LOCATION_SCOPE_CHOICES, LOCATION_SCOPE_LABELS


COUNTRY_CACHE_KEY = "leads:country-catalog:v1"
COUNTRY_CACHE_TIMEOUT = 60 * 60 * 24 * 30
LOCATION_VALIDATION_CACHE_PREFIX = "leads:location-validation:v1"

COUNTRY_ADMIN_LABEL_OVERRIDES = {
    "AU": "State / territory",
    "CA": "Province",
    "GB": "County / region",
    "IE": "County",
    "IN": "State",
    "KE": "County",
    "NG": "State",
    "PH": "Province",
    "US": "State",
    "ZA": "Province",
}

COUNTRY_FALLBACKS = [
    {"code": "AU", "name": "Australia"},
    {"code": "CA", "name": "Canada"},
    {"code": "DE", "name": "Germany"},
    {"code": "FR", "name": "France"},
    {"code": "GB", "name": "United Kingdom"},
    {"code": "IN", "name": "India"},
    {"code": "KE", "name": "Kenya"},
    {"code": "NG", "name": "Nigeria"},
    {"code": "RW", "name": "Rwanda"},
    {"code": "TZ", "name": "Tanzania"},
    {"code": "UG", "name": "Uganda"},
    {"code": "US", "name": "United States"},
    {"code": "ZA", "name": "South Africa"},
]


def get_country_catalog():
    cached = cache.get(COUNTRY_CACHE_KEY)
    if cached:
        return cached
    try:
        response = requests.get(
            "https://restcountries.com/v3.1/all",
            params={"fields": "name,cca2,region,subregion"},
            timeout=8,
        )
        response.raise_for_status()
        payload = response.json()
        countries = []
        for item in payload:
            code = str(item.get("cca2") or "").strip().upper()
            name = str(((item.get("name") or {}).get("common")) or "").strip()
            if not code or not name:
                continue
            countries.append(
                {
                    "code": code,
                    "name": name,
                    "region": str(item.get("region") or "").strip(),
                    "subregion": str(item.get("subregion") or "").strip(),
                }
            )
        countries.sort(key=lambda item: item["name"])
        if countries:
            cache.set(COUNTRY_CACHE_KEY, countries, COUNTRY_CACHE_TIMEOUT)
            return countries
    except requests.RequestException:
        pass
    return COUNTRY_FALLBACKS


def get_country_choices():
    return [("", "Select country")] + [
        (item["code"], item["name"])
        for item in get_country_catalog()
    ]


def get_country_ui_metadata():
    metadata = {}
    for item in get_country_catalog():
        code = item["code"]
        metadata[code] = {
            "name": item["name"],
            "region": item.get("region", ""),
            "subregion": item.get("subregion", ""),
            "admin_label": COUNTRY_ADMIN_LABEL_OVERRIDES.get(code, "Region / province"),
        }
    return metadata


def get_country_name(code):
    code = str(code or "").strip().upper()
    for item in get_country_catalog():
        if item["code"] == code:
            return item["name"]
    return ""


def _scope_address_keys(scope):
    return {
        "city_town": ("city", "town", "village", "municipality", "hamlet", "locality"),
        "county": ("county",),
        "state": ("state", "state_district"),
        "province": ("province", "state", "state_district"),
        "region": ("region", "state", "province", "state_district"),
    }.get(scope, ("city", "town", "village"))


def _validation_cache_key(country_code, scope, area):
    normalized = f"{str(country_code or '').upper()}:{str(scope or '').lower()}:{str(area or '').strip().lower()}"
    return f"{LOCATION_VALIDATION_CACHE_PREFIX}:{normalized}"


def validate_location_selection(country_code, scope, area):
    country_code = str(country_code or "").strip().upper()
    scope = str(scope or "").strip()
    area = " ".join(str(area or "").split()).strip()

    if not country_code:
        raise ValidationError("Select a country for this market.")
    if not scope:
        raise ValidationError("Select the market level you want to target.")
    if scope not in {value for value, _label in LOCATION_SCOPE_CHOICES}:
        raise ValidationError("Select a valid market level.")
    if not area:
        raise ValidationError(f"Enter the {LOCATION_SCOPE_LABELS.get(scope, 'location')} name.")

    cached = cache.get(_validation_cache_key(country_code, scope, area))
    if cached:
        return cached

    country_name = get_country_name(country_code)
    if not country_name:
        raise ValidationError("Select a valid country.")

    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "q": f"{area}, {country_name}",
                "format": "jsonv2",
                "addressdetails": 1,
                "limit": 5,
                "countrycodes": country_code.lower(),
            },
            headers={"User-Agent": "VRTSPACE/1.0"},
            timeout=10,
        )
        response.raise_for_status()
        results = response.json()
    except requests.RequestException as exc:
        raise ValidationError(
            "Location validation is temporarily unavailable. Try again in a moment or use Worldwide for global services."
        ) from exc

    expected_keys = _scope_address_keys(scope)
    for result in results:
        address = result.get("address") or {}
        result_country = str(address.get("country_code") or "").upper()
        if result_country != country_code:
            continue
        normalized_area = ""
        for key in expected_keys:
            value = str(address.get(key) or "").strip()
            if value:
                normalized_area = value
                break
        if not normalized_area:
            continue
        payload = {
            "display": f"{normalized_area}, {country_name}",
            "country_code": country_code,
            "country_name": country_name,
            "scope": scope,
            "scope_label": LOCATION_SCOPE_LABELS.get(scope, scope.replace("_", " ").title()),
            "area": normalized_area,
        }
        cache.set(_validation_cache_key(country_code, scope, area), payload, COUNTRY_CACHE_TIMEOUT)
        return payload

    raise ValidationError(
        f"'{area}' was not validated as a {LOCATION_SCOPE_LABELS.get(scope, 'location').lower()} in {country_name}."
    )
