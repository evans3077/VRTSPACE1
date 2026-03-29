import hashlib
import json
from urllib.parse import urlparse

from django.utils.text import slugify

from apps.leads.models import ClientProject

from .models import Article, ContentEditorialTask, GeneratedContent, Service
from .refinement import refine_brief, refine_payload


OUTPUT_TYPE_LABELS = {
    GeneratedContent.OutputType.SERVICE_PAGE: "service page",
    GeneratedContent.OutputType.LANDING_PAGE: "landing page",
    GeneratedContent.OutputType.ARTICLE: "article",
    GeneratedContent.OutputType.ANSWER_BLOCK: "answer block",
}

PAGE_TYPE_OUTPUT_MAP = {
    "service": GeneratedContent.OutputType.SERVICE_PAGE,
    "location": GeneratedContent.OutputType.LANDING_PAGE,
    "pricing": GeneratedContent.OutputType.LANDING_PAGE,
    "faq": GeneratedContent.OutputType.ANSWER_BLOCK,
    "comparison": GeneratedContent.OutputType.ARTICLE,
    "article": GeneratedContent.OutputType.ARTICLE,
    "feature": GeneratedContent.OutputType.SERVICE_PAGE,
    "use_case": GeneratedContent.OutputType.LANDING_PAGE,
    "inventory": GeneratedContent.OutputType.LANDING_PAGE,
    "case_study": GeneratedContent.OutputType.ARTICLE,
    "review": GeneratedContent.OutputType.ARTICLE,
    "finance": GeneratedContent.OutputType.LANDING_PAGE,
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


def get_latest_seo_context(project):
    if not project:
        return None, None
    seo_snapshot = project.seo_snapshots.order_by("-created_at").first()
    opportunity_snapshot = project.seo_opportunity_snapshots.order_by("-created_at").first()
    return seo_snapshot, opportunity_snapshot


def _output_type_for_page_type(page_type):
    return PAGE_TYPE_OUTPUT_MAP.get(page_type, GeneratedContent.OutputType.ARTICLE)


def _brief_title_options(*, page_type_label, primary_keyword, location, business_type):
    location_suffix = f" in {location}" if location else ""
    return [
        f"{primary_keyword.title()}{location_suffix}",
        f"{page_type_label} for {business_type}{location_suffix}",
        f"{primary_keyword.title()}: what buyers should know{location_suffix}",
    ]


def _brief_outline(*, primary_keyword, page_type_label, page_goal, competitor_evidence):
    competitor_line = ""
    if competitor_evidence:
        first_evidence = competitor_evidence[0]
        if isinstance(first_evidence, dict):
            evidence_label = first_evidence.get("title") or first_evidence.get("url")
        else:
            evidence_label = str(first_evidence).strip()
        if evidence_label:
            competitor_line = (
                f" Add the depth competitors show on pages like {evidence_label}."
            )
    return [
        {
            "heading": "Direct answer",
            "instruction": f"Answer the search intent behind {primary_keyword} immediately and connect it to {page_goal.lower()}.{competitor_line}",
        },
        {
            "heading": f"Why this {page_type_label.lower()} matters",
            "instruction": "Explain the business problem, the offer, and the fit for the target audience using specific commercial language.",
        },
        {
            "heading": "Proof and differentiation",
            "instruction": "Add trust signals, operational detail, process clarity, and outcome evidence instead of vague claims.",
        },
        {
            "heading": "FAQ and objections",
            "instruction": "Resolve common objections and add schema-friendly answers that support both SEO and AEO surfaces.",
        },
        {
            "heading": "Conversion path",
            "instruction": "Close with a direct CTA that moves the visitor into the next concrete action.",
        },
    ]


def _brief_faq_targets(primary_keyword, offer_summary, location):
    location_suffix = f" in {location}" if location else ""
    return [
        f"What should a page about {primary_keyword}{location_suffix} explain first?",
        f"How does {offer_summary.lower()} work in practice?",
        f"What should a buyer compare before choosing this option?",
    ]


def _build_internal_link_targets(project, seo_context_payload, page_map_item):
    links = []
    site_structure = seo_context_payload.get("site_structure", {})
    pages = site_structure.get("pages", [])
    for page in pages[:8]:
        url = page.get("url")
        title = page.get("title") or page.get("h1") or page.get("page_type", "Page").title()
        if not url:
            continue
        links.append(
            {
                "label": title,
                "url": url,
                "reason": f"Use this as a supporting internal link for {page_map_item.get('target_keyword', '').lower()} coverage.",
            }
        )
        if len(links) >= 4:
            break
    if project and project.website:
        links.insert(
            0,
            {
                "label": project.normalized_domain or project.website,
                "url": project.website,
                "reason": "Primary domain reference for cluster and navigation alignment.",
            },
        )
    return links[:5]


def build_seo_content_briefs(project):
    seo_snapshot, opportunity_snapshot = get_latest_seo_context(project)
    if not seo_snapshot or not opportunity_snapshot:
        return []

    seo_payload = seo_snapshot.output_json or {}
    opportunity_payload = opportunity_snapshot.output_json or {}
    context = seo_payload.get("context", {})
    keyword_queue = opportunity_payload.get("keyword_opportunities", [])
    page_map = opportunity_payload.get("page_map", [])
    keyword_by_type = {}
    for item in keyword_queue:
        keyword_by_type.setdefault(item.get("target_page_type"), item)

    briefs = []
    for item in page_map:
        if item.get("status") == "backlog":
            continue
        keyword_item = keyword_by_type.get(item.get("page_type"))
        primary_keyword = (keyword_item or {}).get("keyword") or item.get("target_keyword") or ""
        if not primary_keyword:
            continue
        page_type = item.get("page_type", "article")
        page_type_label = item.get("page_type_label", page_type.replace("_", " ").title())
        title_options = _brief_title_options(
            page_type_label=page_type_label,
            primary_keyword=primary_keyword,
            location=context.get("location", ""),
            business_type=context.get("business_type", ""),
        )
        competitor_evidence = []
        for evidence in item.get("competitor_evidence", [])[:3]:
            if isinstance(evidence, dict):
                competitor_evidence.append(evidence)
            elif isinstance(evidence, str) and evidence.strip():
                competitor_evidence.append({"url": evidence.strip(), "title": evidence.strip()})
        brief = {
            "brief_key": slugify(f"{page_type}-{primary_keyword}")[:80],
            "page_type": page_type,
            "page_type_label": page_type_label,
            "output_type": _output_type_for_page_type(page_type),
            "output_type_label": OUTPUT_TYPE_LABELS[_output_type_for_page_type(page_type)],
            "priority_score": item.get("priority_score", 0),
            "primary_keyword": primary_keyword,
            "secondary_keywords": (keyword_item or {}).get("support_terms", [])[:3],
            "search_intent": (keyword_item or {}).get("intent", page_type_label),
            "business_type": context.get("business_type", ""),
            "location": context.get("location", ""),
            "target_audience": context.get("target_audience", ""),
            "page_goal": context.get("target_goal", ""),
            "offer_summary": context.get("primary_service", "") or context.get("business_type", ""),
            "reason": item.get("reason", ""),
            "action": item.get("action", ""),
            "target_urls": item.get("target_urls", []),
            "title_options": title_options,
            "outline_sections": _brief_outline(
                primary_keyword=primary_keyword,
                page_type_label=page_type_label,
                page_goal=context.get("target_goal", ""),
                competitor_evidence=competitor_evidence,
            ),
            "faq_targets": _brief_faq_targets(
                primary_keyword,
                context.get("primary_service", "") or context.get("business_type", ""),
                context.get("location", ""),
            ),
            "internal_link_targets": _build_internal_link_targets(project, seo_payload, item),
            "competitor_evidence": competitor_evidence,
        }
        briefs.append(brief)
        if len(briefs) >= 8:
            break
    return briefs


def get_seo_content_brief(project, brief_key):
    for brief in build_seo_content_briefs(project):
        if brief["brief_key"] == brief_key:
            return brief
    return None


def _brief_hash(brief):
    return hashlib.sha256(json.dumps(brief, sort_keys=True).encode("utf-8")).hexdigest()


def sync_project_editorial_tasks(project):
    seo_snapshot, opportunity_snapshot = get_latest_seo_context(project)
    if not project or not seo_snapshot or not opportunity_snapshot:
        return []

    briefs = build_seo_content_briefs(project)
    active_keys = set()
    tasks = []

    for brief in briefs:
        active_keys.add(brief["brief_key"])
        refined_brief, brief_refinement = refine_brief(brief)
        task, created = ContentEditorialTask.objects.get_or_create(
            project=project,
            brief_key=brief["brief_key"],
            defaults={
                "source_seo_snapshot": seo_snapshot,
                "source_seo_opportunity_snapshot": opportunity_snapshot,
                "title": refined_brief["title_options"][0] if refined_brief.get("title_options") else refined_brief["primary_keyword"],
                "output_type": refined_brief["output_type"],
                "priority_score": refined_brief.get("priority_score", 0),
                "brief_hash": _brief_hash(brief),
                "brief_json": refined_brief,
                "metadata": {"brief_refinement": brief_refinement},
                "status": ContentEditorialTask.Status.QUEUED,
            },
        )
        if created:
            tasks.append(task)
            continue

        current_hash = _brief_hash(brief)
        changed = task.brief_hash != current_hash
        task.source_seo_snapshot = seo_snapshot
        task.source_seo_opportunity_snapshot = opportunity_snapshot
        task.title = refined_brief["title_options"][0] if refined_brief.get("title_options") else refined_brief["primary_keyword"]
        task.output_type = refined_brief["output_type"]
        task.priority_score = refined_brief.get("priority_score", 0)
        task.brief_hash = current_hash
        task.brief_json = refined_brief
        task.metadata = {
            **(task.metadata or {}),
            "brief_refinement": brief_refinement,
        }
        if changed:
            if task.status == ContentEditorialTask.Status.APPLIED:
                task.status = ContentEditorialTask.Status.STALE
            elif task.status != ContentEditorialTask.Status.ARCHIVED:
                task.status = ContentEditorialTask.Status.QUEUED
        task.save(
            update_fields=[
                "source_seo_snapshot",
                "source_seo_opportunity_snapshot",
                "title",
                "output_type",
                "priority_score",
                "brief_hash",
                "brief_json",
                "metadata",
                "status",
                "updated_at",
            ]
        )
        tasks.append(task)

    ContentEditorialTask.objects.filter(project=project).exclude(brief_key__in=active_keys).exclude(
        status=ContentEditorialTask.Status.ARCHIVED
    ).update(status=ContentEditorialTask.Status.STALE)

    return list(project.editorial_tasks.select_related("latest_generated_content").order_by("-priority_score", "-updated_at"))


def get_editorial_tasks(project):
    if not project:
        return []
    tasks = list(
        project.editorial_tasks.select_related("latest_generated_content")
        .exclude(status=ContentEditorialTask.Status.ARCHIVED)
        .order_by("-priority_score", "-updated_at")
    )
    if tasks:
        return tasks
    return sync_project_editorial_tasks(project)


def get_editorial_task(project, brief_key):
    if not project:
        return None
    task = (
        project.editorial_tasks.select_related("latest_generated_content")
        .filter(brief_key=brief_key)
        .first()
    )
    if task:
        return task
    sync_project_editorial_tasks(project)
    return (
        project.editorial_tasks.select_related("latest_generated_content")
        .filter(brief_key=brief_key)
        .first()
    )


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
    seo_brief = input_data.get("seo_brief") or {}
    brief_link_targets = seo_brief.get("internal_link_targets", [])
    if brief_link_targets:
        internal_links = brief_link_targets
    title_options = seo_brief.get("title_options") or [_build_heading({
        "location": input_data.get("location", ""),
        "output_type": output_type,
        "primary_keyword": primary_keyword,
        "target_audience": input_data["target_audience"],
        "business_type": input_data["business_type"],
    })]

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
        "seo_brief": seo_brief,
        "title_options": title_options[:3],
        "outline_sections": seo_brief.get("outline_sections", []),
        "faq_targets": seo_brief.get("faq_targets", []),
        "competitor_evidence": seo_brief.get("competitor_evidence", []),
        "category_gaps": category_gaps[:3],
        "improvement_points": improvement_points[:3],
        "suggested_internal_links": internal_links,
        "audit_context": audit_context,
    }


def _build_heading(context):
    title_options = context.get("title_options") or []
    if title_options:
        return title_options[0]
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
    if context.get("outline_sections"):
        return [
            {
                "heading": item.get("heading", "Section"),
                "body": item.get("instruction", ""),
            }
            for item in context["outline_sections"]
        ]
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
    return [
        {"heading": "Direct answer", "body": intro},
        {"heading": "Offer and fit", "body": offer},
        {"heading": "Credibility and gaps", "body": credibility},
        {"heading": "Structure guidance", "body": structure},
        {"heading": "Priority actions", "body": actions},
    ]


def _build_body(context):
    sections = _build_sections(context)
    heading = _build_heading(context)
    body_parts = [f"# {heading}", ""]

    for section in sections:
        body_parts.append(f"## {section['heading']}")
        body_parts.append(section["body"])
        body_parts.append("")

    body_parts.append("## FAQ")
    for faq in build_faq_items(context):
        body_parts.append(f"### {faq['question']}")
        body_parts.append(faq["answer"])
        body_parts.append("")
    return "\n".join(body_parts).strip()


def build_faq_items(context):
    faq_targets = context.get("faq_targets") or []
    if faq_targets:
        answers = [
            f"Start with the direct business problem, explain the offer clearly, and align the answer with {context['primary_keyword']}.",
            f"Explain the steps, proof, and expected result in a way that supports {context['page_goal'].lower()}.",
            "Use the latest audit and competitor benchmark insights to answer with more specificity than a generic marketing page.",
        ]
        return [
            {"question": question, "answer": answers[index % len(answers)]}
            for index, question in enumerate(faq_targets[:4])
        ]
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
        "answer_first_intro": (
            intro_line.startswith(context["business_type"])
            or context["primary_keyword"].lower() in intro_line.lower()
        ),
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
        "title_options": context.get("title_options", [])[:3],
        "meta_title": title[:60],
        "meta_description": _build_meta_description(context),
        "content": _build_body(context),
        "faq_items": build_faq_items(context),
        "keywords_used": context["target_keywords"][:3],
        "suggested_internal_links": context["suggested_internal_links"],
        "cta": build_cta(context),
        "brief": {
            "summary": context.get("seo_brief", {}).get("reason", ""),
            "action": context.get("seo_brief", {}).get("action", ""),
            "target_urls": context.get("seo_brief", {}).get("target_urls", []),
            "title_options": context.get("title_options", [])[:3],
            "outline_sections": context.get("outline_sections", []),
            "faq_targets": context.get("faq_targets", []),
            "internal_link_targets": context.get("suggested_internal_links", []),
            "competitor_evidence": context.get("competitor_evidence", []),
        },
    }
    payload["schema_json"] = build_schema_json(payload)
    payload["validation"] = validate_generated_output(payload, context=context)
    payload = refine_payload(
        context=context,
        payload=payload,
        schema_builder=build_schema_json,
        validator=validate_generated_output,
    )
    return context, payload


def create_generated_content(*, user, project, output_type, input_data):
    context, payload = generate_content_payload(
        project=project,
        output_type=output_type,
        input_data=input_data,
    )
    latest_audit = getattr(project, "latest_audit_run", None)
    source_seo_snapshot, source_seo_opportunity_snapshot = get_latest_seo_context(project)
    source_editorial_task = input_data.get("source_editorial_task")
    draft = GeneratedContent.objects.create(
        project=project,
        source_audit_run=latest_audit,
        source_seo_snapshot=source_seo_snapshot,
        source_seo_opportunity_snapshot=source_seo_opportunity_snapshot,
        source_editorial_task=source_editorial_task,
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
        brief_json=payload["brief"],
        prompt_context=context,
        output_json=payload,
        validation_json=payload["validation"],
    )
    if source_editorial_task:
        source_editorial_task.latest_generated_content = draft
        if source_editorial_task.status != ContentEditorialTask.Status.APPLIED:
            source_editorial_task.status = ContentEditorialTask.Status.DRAFTED
        source_editorial_task.save(update_fields=["latest_generated_content", "status", "updated_at"])
    return draft


def refresh_generated_content_validation(draft):
    validation = validate_generated_output(
        {
            "title": draft.title,
            "meta_description": draft.meta_description,
            "content": draft.body,
            "faq_items": draft.faq_items,
            "cta": draft.cta,
        },
        context=draft.prompt_context or {},
    )
    draft.validation_json = validation
    draft.output_json = {
        **(draft.output_json or {}),
        "title": draft.title,
        "meta_title": draft.meta_title,
        "meta_description": draft.meta_description,
        "content": draft.body,
        "faq_items": draft.faq_items,
        "keywords_used": draft.keywords_used,
        "suggested_internal_links": draft.suggested_internal_links,
        "cta": draft.cta,
        "brief": draft.brief_json,
        "schema_json": draft.schema_json,
        "validation": validation,
    }
    draft.save(update_fields=["validation_json", "output_json", "updated_at"])
    return draft


def _build_unique_slug(model_class, value, *, instance=None):
    base_slug = slugify(value)[:45] or "generated-content"
    slug = base_slug
    index = 2
    queryset = model_class.objects.all()
    if instance and instance.pk:
        queryset = queryset.exclude(pk=instance.pk)
    while queryset.filter(slug=slug).exists():
        slug = f"{base_slug[:40]}-{index}"
        index += 1
    return slug


def apply_generated_content(draft):
    if draft.output_type in {
        GeneratedContent.OutputType.SERVICE_PAGE,
        GeneratedContent.OutputType.LANDING_PAGE,
    }:
        service = draft.applied_service or Service()
        service.title = draft.title
        if not service.slug:
            service.slug = _build_unique_slug(Service, draft.title, instance=service)
        service.summary = draft.meta_description
        service.value_proposition = draft.cta[:255]
        service.body = draft.body
        service.meta_title = draft.meta_title
        service.meta_description = draft.meta_description
        service.schema_json = draft.schema_json
        service.save()
        draft.applied_service = service
    else:
        article = draft.applied_article or Article()
        article.title = draft.title
        if not article.slug:
            article.slug = _build_unique_slug(Article, draft.title, instance=article)
        article.excerpt = draft.meta_description
        article.content = draft.body
        article.meta_title = draft.meta_title
        article.meta_description = draft.meta_description
        article.schema_json = draft.schema_json
        article.status = Article.Status.DRAFT
        article.save()
        draft.applied_article = article

    draft.status = GeneratedContent.Status.APPLIED
    draft.save(update_fields=["applied_service", "applied_article", "status", "updated_at"])
    if draft.source_editorial_task_id:
        task = draft.source_editorial_task
        task.latest_generated_content = draft
        task.status = ContentEditorialTask.Status.APPLIED
        task.save(update_fields=["latest_generated_content", "status", "updated_at"])
    return draft
