import json
from copy import deepcopy
from urllib import error, request

from django.conf import settings


def _default_metadata(kind):
    provider = settings.CONTENT_REFINEMENT_PROVIDER or "deterministic"
    model = settings.CONTENT_REFINEMENT_MODEL or ""
    enabled = bool(
        settings.CONTENT_REFINEMENT_ENABLED
        and provider == "ollama"
        and model
    )
    return {
        "kind": kind,
        "provider": provider,
        "model": model,
        "enabled": enabled,
        "applied": False,
        "sections_refined": [],
        "fallback_reason": "",
    }


def _dedupe_strings(values, *, limit=None):
    cleaned = []
    seen = set()
    for value in values or []:
        if not isinstance(value, str):
            continue
        item = value.strip()
        if not item:
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(item)
        if limit and len(cleaned) >= limit:
            break
    return cleaned


def _normalize_outline(items):
    outline = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        heading = str(item.get("heading", "")).strip()
        instruction = str(item.get("instruction", "")).strip()
        if not heading or not instruction:
            continue
        outline.append(
            {
                "heading": heading[:140],
                "instruction": instruction[:600],
            }
        )
        if len(outline) >= 6:
            break
    return outline


def _normalize_faq_items(items):
    normalized = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        question = str(item.get("question", "")).strip()
        answer = str(item.get("answer", "")).strip()
        if not question or not answer:
            continue
        normalized.append(
            {
                "question": question[:220],
                "answer": answer[:900],
            }
        )
        if len(normalized) >= 6:
            break
    return normalized


def _normalize_payload_response(candidate):
    if not isinstance(candidate, dict):
        return {}
    normalized = {}
    if isinstance(candidate.get("title"), str) and candidate["title"].strip():
        normalized["title"] = candidate["title"].strip()[:255]
    title_options = _dedupe_strings(candidate.get("title_options"), limit=4)
    if title_options:
        normalized["title_options"] = title_options
    if isinstance(candidate.get("meta_title"), str) and candidate["meta_title"].strip():
        normalized["meta_title"] = candidate["meta_title"].strip()[:60]
    if isinstance(candidate.get("meta_description"), str) and candidate["meta_description"].strip():
        normalized["meta_description"] = candidate["meta_description"].strip()[:160]
    if isinstance(candidate.get("content"), str) and candidate["content"].strip():
        normalized["content"] = candidate["content"].strip()
    faq_items = _normalize_faq_items(candidate.get("faq_items"))
    if faq_items:
        normalized["faq_items"] = faq_items
    if isinstance(candidate.get("cta"), str) and candidate["cta"].strip():
        normalized["cta"] = candidate["cta"].strip()[:255]
    keywords_used = _dedupe_strings(candidate.get("keywords_used"), limit=5)
    if keywords_used:
        normalized["keywords_used"] = keywords_used
    if isinstance(candidate.get("brief"), dict):
        brief = {}
        title_options = _dedupe_strings(candidate["brief"].get("title_options"), limit=4)
        if title_options:
            brief["title_options"] = title_options
        outline = _normalize_outline(candidate["brief"].get("outline_sections"))
        if outline:
            brief["outline_sections"] = outline
        faq_targets = _dedupe_strings(candidate["brief"].get("faq_targets"), limit=5)
        if faq_targets:
            brief["faq_targets"] = faq_targets
        if isinstance(candidate["brief"].get("summary"), str) and candidate["brief"]["summary"].strip():
            brief["summary"] = candidate["brief"]["summary"].strip()[:400]
        if isinstance(candidate["brief"].get("action"), str) and candidate["brief"]["action"].strip():
            brief["action"] = candidate["brief"]["action"].strip()[:400]
        if brief:
            normalized["brief"] = brief
    return normalized


def _normalize_brief_response(candidate):
    if not isinstance(candidate, dict):
        return {}
    normalized = {}
    title_options = _dedupe_strings(candidate.get("title_options"), limit=4)
    if title_options:
        normalized["title_options"] = title_options
    outline = _normalize_outline(candidate.get("outline_sections"))
    if outline:
        normalized["outline_sections"] = outline
    faq_targets = _dedupe_strings(candidate.get("faq_targets"), limit=5)
    if faq_targets:
        normalized["faq_targets"] = faq_targets
    if isinstance(candidate.get("reason"), str) and candidate["reason"].strip():
        normalized["reason"] = candidate["reason"].strip()[:400]
    if isinstance(candidate.get("action"), str) and candidate["action"].strip():
        normalized["action"] = candidate["action"].strip()[:400]
    return normalized


def _call_ollama(prompt):
    payload = json.dumps(
        {
            "model": settings.CONTENT_REFINEMENT_MODEL,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        }
    ).encode("utf-8")
    endpoint = settings.OLLAMA_BASE_URL.rstrip("/") + "/api/generate"
    req = request.Request(
        endpoint,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=settings.CONTENT_REFINEMENT_TIMEOUT) as response:
        body = response.read().decode("utf-8")
    parsed = json.loads(body)
    response_text = parsed.get("response", "")
    if not response_text:
        return None
    return json.loads(response_text)


def _run_provider_prompt(prompt):
    provider = settings.CONTENT_REFINEMENT_PROVIDER or "deterministic"
    if provider != "ollama" or not settings.CONTENT_REFINEMENT_ENABLED:
        return None
    try:
        return _call_ollama(prompt)
    except (error.URLError, TimeoutError, json.JSONDecodeError, OSError, ValueError):
        return None


def _merge_refined_brief(brief, candidate):
    refined = deepcopy(brief)
    sections = []
    for field, value in candidate.items():
        refined[field] = value
        sections.append(field)
    return refined, sections


def refine_brief(brief):
    metadata = _default_metadata("brief")
    if not metadata["enabled"]:
        metadata["fallback_reason"] = "provider_disabled"
        return deepcopy(brief), metadata

    prompt = (
        "You are refining a deterministic SEO editorial brief.\n"
        "Return valid JSON only.\n"
        "Do not invent URLs or competitor domains.\n"
        "Improve clarity and specificity for titles, outline sections, FAQ targets, reason, and action.\n"
        "Keep the business, location, and primary keyword grounded in the provided brief.\n"
        "JSON contract:\n"
        "{"
        "\"title_options\": [\"...\"], "
        "\"outline_sections\": [{\"heading\": \"...\", \"instruction\": \"...\"}], "
        "\"faq_targets\": [\"...\"], "
        "\"reason\": \"...\", "
        "\"action\": \"...\""
        "}\n"
        "Deterministic brief:\n"
        f"{json.dumps(brief, indent=2, sort_keys=True)}"
    )
    candidate = _normalize_brief_response(_run_provider_prompt(prompt))
    if not candidate:
        metadata["fallback_reason"] = "provider_unavailable_or_invalid"
        return deepcopy(brief), metadata

    refined, sections = _merge_refined_brief(brief, candidate)
    metadata["applied"] = bool(sections)
    metadata["sections_refined"] = sections
    if not metadata["applied"]:
        metadata["fallback_reason"] = "no_usable_changes"
    return refined, metadata


def refine_payload(*, context, payload, schema_builder, validator):
    metadata = _default_metadata("payload")
    base_payload = deepcopy(payload)
    base_payload["refinement"] = metadata

    if not metadata["enabled"]:
        metadata["fallback_reason"] = "provider_disabled"
        return base_payload

    prompt = (
        "You are refining a deterministic SEO and AEO content payload.\n"
        "Return valid JSON only.\n"
        "Do not invent internal-link URLs, competitor domains, or unsupported claims.\n"
        "Preserve answer-first structure and keyword grounding.\n"
        "Allowed JSON fields:\n"
        "{"
        "\"title\": \"...\", "
        "\"title_options\": [\"...\"], "
        "\"meta_title\": \"...\", "
        "\"meta_description\": \"...\", "
        "\"content\": \"...\", "
        "\"faq_items\": [{\"question\": \"...\", \"answer\": \"...\"}], "
        "\"cta\": \"...\", "
        "\"keywords_used\": [\"...\"], "
        "\"brief\": {"
        "\"summary\": \"...\", "
        "\"action\": \"...\", "
        "\"title_options\": [\"...\"], "
        "\"outline_sections\": [{\"heading\": \"...\", \"instruction\": \"...\"}], "
        "\"faq_targets\": [\"...\"]"
        "}"
        "}\n"
        "Generator context:\n"
        f"{json.dumps(context, indent=2, sort_keys=True)}\n"
        "Deterministic payload:\n"
        f"{json.dumps(payload, indent=2, sort_keys=True)}"
    )
    candidate = _normalize_payload_response(_run_provider_prompt(prompt))
    if not candidate:
        metadata["fallback_reason"] = "provider_unavailable_or_invalid"
        return base_payload

    merged = deepcopy(payload)
    sections = []
    for field in ("title", "title_options", "meta_title", "meta_description", "content", "faq_items", "cta"):
        if field in candidate:
            merged[field] = candidate[field]
            sections.append(field)

    if "keywords_used" in candidate:
        allowed_keywords = {keyword.lower(): keyword for keyword in context.get("target_keywords", [])}
        filtered_keywords = []
        for keyword in candidate["keywords_used"]:
            match = allowed_keywords.get(keyword.lower())
            if match and match not in filtered_keywords:
                filtered_keywords.append(match)
        if filtered_keywords:
            merged["keywords_used"] = filtered_keywords[:5]
            sections.append("keywords_used")

    if "brief" in candidate:
        brief = deepcopy(merged.get("brief", {}))
        for field, value in candidate["brief"].items():
            brief[field] = value
        merged["brief"] = brief
        sections.append("brief")

    merged["schema_json"] = schema_builder(merged)
    merged["validation"] = validator(merged, context=context)
    if not merged["validation"].get("passes"):
        metadata["fallback_reason"] = "validation_failed"
        return base_payload

    metadata["applied"] = bool(sections)
    metadata["sections_refined"] = sections
    if not metadata["applied"]:
        metadata["fallback_reason"] = "no_usable_changes"
        return base_payload

    merged["refinement"] = metadata
    if isinstance(merged.get("brief"), dict):
        merged["brief"]["refinement"] = {
            "provider": metadata["provider"],
            "model": metadata["model"],
            "applied": metadata["applied"],
            "sections_refined": sections,
        }
    return merged
