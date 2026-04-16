from io import BytesIO
from textwrap import wrap


SECTION_DIVIDER = "-" * 76


def _escape_pdf_text(value):
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
    )


def _build_report_lines(audit_run):
    summary = audit_run.summary or {}
    score_breakdown = summary.get("score_breakdown", {})
    recommendations = summary.get("featured_recommendations") or summary.get("recommendations", [])
    issue_summary = summary.get("issue_summary", {})
    pagespeed = summary.get("pagespeed", {})
    performance_metrics = summary.get("performance_metrics", [])
    product_modules = summary.get("product_modules", [])
    context_analysis = summary.get("context_analysis", {})
    change_report = getattr(audit_run, "change_report", None)

    lines = [
        "VRT SPACE AGENCY",
        "Stakeholder Audit Report",
        SECTION_DIVIDER,
        f"Domain: {audit_run.normalized_domain}",
        f"Status: {audit_run.get_status_display()}",
        f"Overall score: {audit_run.overall_score}",
        f"Pages crawled: {audit_run.pages_crawled}",
        f"Completed at: {audit_run.completed_at or 'Pending'}",
        "",
        "Executive summary",
        SECTION_DIVIDER,
        f"This report summarizes the saved audit state for {audit_run.normalized_domain}.",
    ]

    if recommendations:
        top_categories = ", ".join(
            sorted(
                {
                    recommendation.get("category", "General")
                    for recommendation in recommendations[:4]
                    if recommendation.get("category")
                }
            )
        )
        if top_categories:
            lines.append(f"Primary pressure areas: {top_categories}.")

    if change_report:
        lines.extend(
            [
                change_report.summary.get("headline", ""),
                f"New issues: {change_report.new_issue_count}",
                f"Resolved issues: {change_report.resolved_issue_count}",
                "",
            ]
        )
    else:
        lines.append("")

    lines.extend(["", "Score breakdown", SECTION_DIVIDER])

    for key in ("technical", "on_page", "content", "aeo", "internal_linking", "performance"):
        item = score_breakdown.get(key)
        if not item:
            continue
        lines.append(
            f"- {item.get('label', key.title())}: {item.get('score', 0)} | "
            f"Status: {item.get('status', 'n/a')} | Issues: {item.get('issues', 0)}"
        )
        next_step = item.get("next_step")
        if next_step:
            lines.append(f"  Next step: {next_step}")

    if pagespeed or performance_metrics:
        lines.extend(
            [
                "",
                "PageSpeed summary",
                SECTION_DIVIDER,
            ]
        )
        if pagespeed:
            lines.extend(
                [
                    f"- Source: {pagespeed.get('source', 'Unknown')}",
                    f"- Strategy: {pagespeed.get('strategy', 'Unknown')}",
                ]
            )
        for metric in performance_metrics:
            lines.append(
                f"- {metric.get('label')}: {metric.get('value')} | Target: {metric.get('target_label')} | Status: {metric.get('status', 'n/a')}"
            )
            lines.append(f"  Why it matters: {metric.get('impact')}")
        if pagespeed:
            for metric, value in (pagespeed.get("metrics") or {}).items():
                if metric in {item.get("key") for item in performance_metrics}:
                    continue
                label = metric.replace("_", " ").title()
                lines.append(f"- {label}: {value}")

    if context_analysis:
        lines.extend(["", "Market and competitor context", SECTION_DIVIDER])
        market_context = context_analysis.get("market_context")
        if market_context:
            lines.append(f"- Market context: {market_context}")
        for insight in context_analysis.get("insights", [])[:5]:
            lines.append(f"- Insight: {insight}")
        for competitor in context_analysis.get("competitors", [])[:3]:
            if competitor.get("status") == "unavailable":
                lines.append(f"- Competitor {competitor.get('url')}: unavailable during benchmark pass")
            else:
                lines.append(
                    f"- Competitor {competitor.get('url')}: {competitor.get('word_count', 0)} words, "
                    f"{competitor.get('schema_count', 0)} schema blocks, {competitor.get('response_time_ms', 0)}ms"
                )

    lines.extend(
        [
            "",
            "Issue summary",
            SECTION_DIVIDER,
            f"- Total issues: {issue_summary.get('total', 0)}",
        ]
    )
    for category, count in sorted((issue_summary.get("by_category") or {}).items()):
        lines.append(f"- {category.replace('_', ' ').title()}: {count}")

    lines.extend(["", "Priority recommendations and solutions", SECTION_DIVIDER])
    for index, recommendation in enumerate(recommendations[:8], start=1):
        lines.append(
            f"{index}. {recommendation.get('title', 'Recommendation')} "
            f"({recommendation.get('category', 'General')}, priority {recommendation.get('priority_score', 0)})"
        )
        description = recommendation.get("description")
        if description:
            lines.append(f"   {description}")
        fix = recommendation.get("recommended_fix")
        if fix:
            lines.append(f"   Strategic fix: {fix}")
        if recommendation.get("page_examples"):
            lines.append(
                f"   Where found: {recommendation.get('affected_pages_count', len(recommendation.get('page_examples', [])))} pages including "
                + ", ".join(recommendation.get("page_examples", [])[:3])
            )
        elif recommendation.get("page_url"):
            lines.append(f"   Where found: {recommendation.get('page_url')}")
        impact = recommendation.get("estimated_impact")
        if impact:
            lines.append(f"   Expected result: {impact}")
        technical_steps = recommendation.get("technical_steps") or []
        for step in technical_steps[:2]:
            lines.append(f"   Action step: {step}")
        lines.append("")

    if product_modules:
        lines.extend(["", "Recommended product modules", SECTION_DIVIDER])
        for module in product_modules[:5]:
            lines.append(f"- {module.get('title', 'Module')} ({module.get('plan', 'Plan')}): {module.get('reason', '')}")
            if module.get("impact"):
                lines.append(f"  Outcome: {module.get('impact')}")

    lines.extend(
        [
            "",
            SECTION_DIVIDER,
            "Generated by VRT SPACE AGENCY",
            "This report is based on the stored audit result and can be shared with internal teams or stakeholders.",
        ]
    )
    return lines


def _paginate_lines(lines, *, width=92, lines_per_page=44):
    wrapped_lines = []
    for line in lines:
        if not line:
            wrapped_lines.append("")
            continue
        wrapped_lines.extend(wrap(line, width=width) or [""])

    pages = []
    for start in range(0, len(wrapped_lines), lines_per_page):
        pages.append(wrapped_lines[start:start + lines_per_page])
    return pages or [[]]


def _build_pdf_bytes(page_lines):
    buffer = BytesIO()
    offsets = []

    def write(value):
        if isinstance(value, str):
            value = value.encode("latin-1", errors="replace")
        buffer.write(value)

    write("%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")

    page_count = len(page_lines)
    font_object_id = 3 + (page_count * 2)

    def write_object(object_id, content):
        offsets.append(buffer.tell())
        write(f"{object_id} 0 obj\n")
        write(content)
        write("\nendobj\n")

    kids_refs = " ".join(f"{2 + (index * 2)} 0 R" for index in range(page_count))
    write_object(1, f"<< /Type /Pages /Count {page_count} /Kids [{kids_refs}] >>")

    content_object_ids = []
    for index, lines in enumerate(page_lines):
        page_object_id = 2 + (index * 2)
        content_object_id = page_object_id + 1
        content_object_ids.append(content_object_id)
        write_object(
            page_object_id,
            (
                f"<< /Type /Page /Parent 1 0 R /MediaBox [0 0 612 792] "
                f"/Resources << /Font << /F1 {font_object_id} 0 R >> >> "
                f"/Contents {content_object_id} 0 R >>"
            ),
        )

    for content_object_id, lines in zip(content_object_ids, page_lines):
        text_commands = ["BT", "/F1 11 Tf", "50 760 Td", "14 TL"]
        for line in lines:
            text_commands.append(f"({_escape_pdf_text(line)}) Tj")
            text_commands.append("T*")
        text_commands.append("ET")
        stream = "\n".join(text_commands)
        write_object(
            content_object_id,
            f"<< /Length {len(stream.encode('latin-1', errors='replace'))} >>\nstream\n{stream}\nendstream",
        )

    write_object(font_object_id, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    catalog_object_id = font_object_id + 1
    write_object(catalog_object_id, "<< /Type /Catalog /Pages 1 0 R >>")

    xref_start = buffer.tell()
    write(f"xref\n0 {catalog_object_id + 1}\n")
    write("0000000000 65535 f \n")
    for offset in offsets:
        write(f"{offset:010d} 00000 n \n")

    write(
        f"trailer\n<< /Size {catalog_object_id + 1} /Root {catalog_object_id} 0 R >>\n"
        f"startxref\n{xref_start}\n%%EOF"
    )
    return buffer.getvalue()


def build_audit_report_pdf(audit_run):
    lines = _build_report_lines(audit_run)
    pages = _paginate_lines(lines)
    return _build_pdf_bytes(pages)
