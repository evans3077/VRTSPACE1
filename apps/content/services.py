from urllib.parse import urlparse

from apps.leads.models import ClientProject

from .models import GeneratedContent


OUTPUT_TYPE_LABELS = {
    GeneratedContent.OutputType.SERVICE_PAGE: "service page",
    GeneratedContent.OutputType.LANDING_PAGE: "landing page",
    GeneratedContent.OutputType.ARTICLE: "article",
    GeneratedContent.OutputType.ANSWER_BLOCK: "answer block",
}


def get_workspace_content_project(user):
    if not user or not getattr(user, "is_authenticated", False):
        return None
    return (
        ClientProject.objects.select_related("latest_audit_run", "audit_request")
        .filter(owner=user)
        .order_by("-updated_at")
        .first()
    )


def _normalized_domain(project):
    if project and project.normalized_domain:
        return project.normalized_domain
    if project and project.website:
        return urlparse(project.website).netloc
    return ""


def _score_context(audit_run):
    if not audit_run or not isinstance(audit_run.summary, dict):
        return {}
    summary = audit_run.summary
    return {
        "recommendations": summary.get("recommendations", [])[:3],
        "score_breakdown": summary.get("score_breakdown", {}),
        "product_modules": summary.get("product_modules", [])[:3],
    }


def build_generator_context(*, project, output_type, input_data):
    latest_audit = getattr(project, "latest_audit_run", None)
    keyword_list = input_data["target_keywords"]
    primary_keyword = keyword_list[0]
    domain = _normalized_domain(project)
    audit_context = _score_context(latest_audit)
    category_gaps = [
        item["label"]
        for item in audit_context.get("score_breakdown", {}).values()
        if item.get("score", 100) < 75
    ]
    improvement_points = [
        recommendation["title"]
        for recommendation in audit_context.get("recommendations", [])
    ]
    internal_links = [
        {"label": "Audit workspace", "url": "/workspace/"},
        {"label": "Plans", "url": "/#packages"},
    ]
    if project and project.website:
        internal_links.insert(
            0,
            {"label": domain or "Primary site", "url": project.website},
        )

    return {
        "project_name": project.name if project else "",
        "domain": domain,
        "output_type": output_type,
        "output_label": OUTPUT_TYPE_LABELS[output_type],
        "business_type": input_data["business_type"],
        "location": input_data.get("location", ""),
        "target_audience": input_data["target_audience"],
        "page_goal": input_data["page_goal"],
        "offer_summary": input_data["offer_summary"],
        "target_keywords": keyword_list,
        "primary_keyword": primary_keyword,
        "secondary_keywords": keyword_list[1:4],
        "search_intent": input_data.get("search_intent", ""),
        "category_gaps": category_gaps[:3],
        "improvement_points": improvement_points[:3],
        "suggested_internal_links": internal_links,
        "audit_context": audit_context,
    }


def _build_heading(context):
    location_suffix = f" in {context['location']}" if context["location"] else ""
    output_type = context["output_type"]
    if output_type == GeneratedContent.OutputType.ARTICLE:
        return f"{context['business_type']} {context['primary_keyword']}{location_suffix}: what to fix first"
    if output_type == GeneratedContent.OutputType.ANSWER_BLOCK:
        return f"What is the best way to improve {context['primary_keyword']}{location_suffix}?"
    return f"{context['primary_keyword'].title()}{location_suffix} for {context['target_audience']}"


def _build_meta_description(context):
    location_phrase = f" in {context['location']}" if context["location"] else ""
    return (
        f"Use this {context['output_label']} to explain {context['offer_summary']} to "
        f"{context['target_audience']}{location_phrase}, align with {context['primary_keyword']}, "
        "and move readers toward a clear next step."
    )[:160]


def _build_sections(context):
    location_phrase = f" in {context['location']}" if context["location"] else ""
    recommendation_lines = context["improvement_points"] or [
        "Clarify the offer and outcome in the first screen.",
        "Add direct answers and proof before deeper detail.",
    ]
    gap_lines = context["category_gaps"] or ["On-page", "Content", "AEO"]

    intro = (
        f"{context['business_type']} teams{location_phrase} need a {context['output_label']} that answers "
        f"{context['primary_keyword']} clearly, shows why the offer matters, and gives {context['target_audience']} "
        f"a direct path to {context['page_goal'].lower()}."
    )
    offer = (
        f"{context['offer_summary']} should be framed as the fastest route for {context['target_audience']} "
        f"to get the result they want without unnecessary friction."
    )
    credibility = (
        "Use audit-backed proof points to remove doubt: focus first on "
        + ", ".join(gap_lines[:3]).lower()
        + " improvements, then show the expected business impact."
    )
    structure = (
        "Keep the page answer-first, add scannable subheads, and place a CTA after the core explanation "
        "instead of waiting until the footer."
    )
    actions = "Priority issues from the latest workspace audit: " + "; ".join(recommendation_lines[:3]) + "."
    return [intro, offer, credibility, structure, actions]


def _build_body(context):
    sections = _build_sections(context)
    heading = _build_heading(context)
    body_parts = [f"# {heading}", ""]

    for index, section in enumerate(sections, start=1):
        body_parts.append(f"## Section {index}")
        body_parts.append(section)
        body_parts.append("")

    body_parts.append("## FAQ")
    for faq in build_faq_items(context):
        body_parts.append(f"### {faq['question']}")
        body_parts.append(faq["answer"])
        body_parts.append("")
    return "\n".join(body_parts).strip()


def build_faq_items(context):
    primary_keyword = context["primary_keyword"]
    audience = context["target_audience"]
    offer_summary = context["offer_summary"]
    return [
        {
            "question": f"What should a {primary_keyword} page explain first?",
            "answer": (
                f"It should explain the business problem, the offer, and why {audience} should trust the solution before asking them to convert."
            ),
        },
        {
            "question": "How should the CTA be framed?",
            "answer": (
                f"Frame the CTA around the next concrete step tied to {offer_summary.lower()}, not a vague contact request."
            ),
        },
        {
            "question": "How do audit findings improve this draft?",
            "answer": (
                "They show which gaps are suppressing visibility today, so the content can address those weaknesses directly instead of staying generic."
            ),
        },
    ]


def build_cta(context):
    return f"Open your workspace and turn {context['offer_summary'].lower()} into a live implementation plan."


def build_schema_json(content):
    faq_entities = [
        {
            "@type": "Question",
            "name": item["question"],
            "acceptedAnswer": {
                "@type": "Answer",
                "text": item["answer"],
            },
        }
        for item in content["faq_items"]
    ]
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": faq_entities,
    }


def validate_generated_output(content, *, context):
    body = content["content"]
    non_empty_lines = [line.strip() for line in body.splitlines() if line.strip()]
    intro_line = non_empty_lines[2] if len(non_empty_lines) > 2 else ""
    keyword_hits = [keyword for keyword in context["target_keywords"] if keyword.lower() in body.lower()]
    checks = {
        "has_title": bool(content["title"]),
        "has_meta_description": bool(content["meta_description"]),
        "has_faq_items": len(content["faq_items"]) >= 2,
        "has_cta": bool(content["cta"]),
        "keyword_coverage": len(keyword_hits),
        "keyword_target": len(context["target_keywords"]),
        "answer_first_intro": intro_line.startswith(context["business_type"]),
        "generic_risk": "low" if context["business_type"].lower() in body.lower() else "medium",
    }
    checks["passes"] = all(
        [
            checks["has_title"],
            checks["has_meta_description"],
            checks["has_faq_items"],
            checks["has_cta"],
            checks["keyword_coverage"] >= 1,
            checks["answer_first_intro"],
        ]
    )
    return checks


def generate_content_payload(*, project, output_type, input_data):
    context = build_generator_context(
        project=project,
        output_type=output_type,
        input_data=input_data,
    )
    title = _build_heading(context)
    payload = {
        "title": title,
        "meta_title": title[:60],
        "meta_description": _build_meta_description(context),
        "content": _build_body(context),
        "faq_items": build_faq_items(context),
        "keywords_used": context["target_keywords"][:3],
        "suggested_internal_links": context["suggested_internal_links"],
        "cta": build_cta(context),
    }
    payload["schema_json"] = build_schema_json(payload)
    payload["validation"] = validate_generated_output(payload, context=context)
    return context, payload


def create_generated_content(*, user, project, output_type, input_data):
    context, payload = generate_content_payload(
        project=project,
        output_type=output_type,
        input_data=input_data,
    )
    latest_audit = getattr(project, "latest_audit_run", None)
    return GeneratedContent.objects.create(
        project=project,
        source_audit_run=latest_audit,
        created_by=user,
        output_type=output_type,
        title=payload["title"],
        meta_title=payload["meta_title"],
        meta_description=payload["meta_description"],
        schema_json=payload["schema_json"],
        business_type=context["business_type"],
        location=context["location"],
        target_audience=context["target_audience"],
        page_goal=context["page_goal"],
        offer_summary=context["offer_summary"],
        search_intent=context["search_intent"],
        target_keywords=context["target_keywords"],
        body=payload["content"],
        cta=payload["cta"],
        faq_items=payload["faq_items"],
        suggested_internal_links=payload["suggested_internal_links"],
        keywords_used=payload["keywords_used"],
        prompt_context=context,
        output_json=payload,
        validation_json=payload["validation"],
    )
