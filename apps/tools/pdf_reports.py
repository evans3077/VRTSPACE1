"""Audit report PDF generation via Playwright HTML rendering.

Builds a styled HTML document and uses Playwright's Chromium to render it
to PDF, producing a polished stakeholder-ready report.
"""

import html
from datetime import date


# ─── Score helpers ──────────────────────────────────────────────────────────

def _score_color(score):
    if score is None:
        return "#94a3b8"
    if score >= 75:
        return "#22c55e"
    if score >= 50:
        return "#f59e0b"
    return "#ef4444"


def _score_label(score):
    if score is None:
        return "—"
    if score >= 75:
        return "Good"
    if score >= 50:
        return "Needs Work"
    return "Critical"


def _esc(value):
    return html.escape(str(value or ""))


# ─── CSS ────────────────────────────────────────────────────────────────────

_PDF_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
    --brand: #0ea5e9;
    --brand-dark: #0369a1;
    --bg-dark: #0f172a;
    --bg-mid: #1e293b;
    --text-light: #f8fafc;
    --text-muted: #94a3b8;
    --border: #e2e8f0;
    --green: #22c55e;
    --amber: #f59e0b;
    --red: #ef4444;
    --radius: 8px;
}

body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 10pt;
    line-height: 1.5;
    color: #1e293b;
    background: #ffffff;
}

/* ─── Cover page ──────────────────────────────────────────── */
.cover {
    min-height: 100vh;
    background: linear-gradient(160deg, #0f172a 0%, #1e3a5f 55%, #0c4a6e 100%);
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    padding: 60px 56px 48px;
    page-break-after: always;
    position: relative;
    overflow: hidden;
}
.cover::before {
    content: "";
    position: absolute;
    top: -120px; right: -120px;
    width: 480px; height: 480px;
    background: radial-gradient(circle, rgba(14,165,233,0.15) 0%, transparent 70%);
    border-radius: 50%;
}
.cover-brand {
    display: flex;
    align-items: center;
    gap: 12px;
}
.cover-brand-mark {
    width: 44px; height: 44px;
    background: var(--brand);
    border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    font-size: 22px; font-weight: 800; color: #fff;
}
.cover-brand-name {
    font-size: 16pt; font-weight: 700; color: #fff;
    letter-spacing: -0.02em;
}
.cover-body {
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: center;
    padding: 60px 0 40px;
}
.cover-report-type {
    font-size: 9pt; font-weight: 600; letter-spacing: 0.1em;
    text-transform: uppercase; color: var(--brand);
    margin-bottom: 16px;
}
.cover-domain {
    font-size: 34pt; font-weight: 800; color: #fff;
    letter-spacing: -0.03em; line-height: 1.1;
    margin-bottom: 12px; word-break: break-all;
}
.cover-subtitle {
    font-size: 13pt; color: #94a3b8; margin-bottom: 40px;
}
.cover-score-row {
    display: flex; gap: 24px; flex-wrap: wrap;
}
.cover-score-card {
    background: rgba(255,255,255,0.07);
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: var(--radius);
    padding: 18px 24px;
    min-width: 130px;
}
.cover-score-card-label {
    font-size: 8pt; font-weight: 600; letter-spacing: 0.06em;
    text-transform: uppercase; color: #64748b;
    margin-bottom: 6px;
}
.cover-score-card-value {
    font-size: 26pt; font-weight: 800; line-height: 1;
}
.cover-score-card-sub {
    font-size: 8pt; color: #64748b; margin-top: 4px;
}
.cover-footer {
    display: flex; justify-content: space-between;
    font-size: 8pt; color: #475569;
    border-top: 1px solid rgba(255,255,255,0.08);
    padding-top: 20px;
}

/* ─── Page sections ───────────────────────────────────────── */
.section {
    padding: 40px 56px;
    page-break-inside: avoid;
}
.section + .section {
    border-top: 1px solid var(--border);
}
.section-header {
    display: flex; align-items: center; gap: 12px;
    margin-bottom: 24px;
}
.section-icon {
    width: 36px; height: 36px;
    background: linear-gradient(135deg, #0ea5e9, #0284c7);
    border-radius: 8px;
    display: flex; align-items: center; justify-content: center;
    font-size: 16px;
}
.section-title {
    font-size: 15pt; font-weight: 700; color: #0f172a;
    letter-spacing: -0.02em;
}
.section-eyebrow {
    font-size: 8pt; font-weight: 600; letter-spacing: 0.08em;
    text-transform: uppercase; color: var(--brand-dark);
    margin-bottom: 4px;
}

/* ─── Score grid ──────────────────────────────────────────── */
.score-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 14px;
    margin-bottom: 8px;
}
.score-card {
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 18px 20px;
    background: #f8fafc;
    position: relative;
    overflow: hidden;
}
.score-card::before {
    content: "";
    position: absolute;
    top: 0; left: 0; right: 0; height: 3px;
    background: var(--card-color, #94a3b8);
}
.score-card-label {
    font-size: 8pt; font-weight: 600; letter-spacing: 0.05em;
    text-transform: uppercase; color: #64748b;
    margin-bottom: 10px;
}
.score-card-value {
    font-size: 28pt; font-weight: 800; line-height: 1;
    color: var(--card-color, #94a3b8);
}
.score-card-status {
    font-size: 8pt; font-weight: 600;
    color: var(--card-color, #94a3b8);
    margin-top: 4px;
}
.score-card-issues {
    font-size: 8pt; color: #94a3b8; margin-top: 2px;
}
.score-bar {
    height: 4px;
    background: #e2e8f0;
    border-radius: 2px;
    margin-top: 10px;
    overflow: hidden;
}
.score-bar-fill {
    height: 100%;
    border-radius: 2px;
    background: var(--card-color, #94a3b8);
}
.score-next-step {
    font-size: 8.5pt; color: #475569;
    margin-top: 8px; line-height: 1.4;
    border-top: 1px solid #e2e8f0;
    padding-top: 8px;
}

/* ─── Issue / recommendation cards ───────────────────────── */
.card-list { display: flex; flex-direction: column; gap: 12px; }

.item-card {
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 16px 20px;
    background: #fff;
    page-break-inside: avoid;
}
.item-card-head {
    display: flex; align-items: flex-start; gap: 12px;
    margin-bottom: 8px;
}
.item-num {
    flex-shrink: 0;
    width: 26px; height: 26px;
    background: var(--bg-dark);
    color: #fff;
    border-radius: 6px;
    display: flex; align-items: center; justify-content: center;
    font-size: 8pt; font-weight: 700;
}
.item-title {
    font-size: 10.5pt; font-weight: 700; color: #0f172a;
    flex: 1; line-height: 1.3;
}
.severity-badge {
    flex-shrink: 0;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 7.5pt; font-weight: 700; letter-spacing: 0.04em;
    text-transform: uppercase;
}
.severity-critical { background: #fee2e2; color: #991b1b; }
.severity-high     { background: #fff7ed; color: #9a3412; }
.severity-medium   { background: #fefce8; color: #854d0e; }
.severity-low      { background: #f0fdf4; color: #166534; }
.severity-info     { background: #eff6ff; color: #1e40af; }

.item-body {
    font-size: 9.5pt; color: #475569; line-height: 1.5;
    margin-bottom: 8px;
}
.item-fix-label {
    font-size: 8pt; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.05em; color: #64748b; margin-bottom: 4px;
}
.item-fix {
    font-size: 9.5pt; color: #334155; line-height: 1.4;
    background: #f8fafc;
    border-left: 3px solid var(--brand);
    padding: 8px 12px;
    border-radius: 0 var(--radius) var(--radius) 0;
}
.item-meta {
    display: flex; gap: 16px; margin-top: 8px;
    flex-wrap: wrap;
}
.item-meta-chip {
    font-size: 8pt; color: #64748b;
    background: #f1f5f9;
    padding: 2px 8px;
    border-radius: 4px;
}
.item-steps {
    margin-top: 8px;
    display: flex; flex-direction: column; gap: 4px;
}
.item-step {
    font-size: 9pt; color: #334155;
    display: flex; gap: 8px; align-items: flex-start;
}
.item-step::before {
    content: "→";
    color: var(--brand);
    flex-shrink: 0;
    margin-top: 1px;
}

/* ─── Metrics table ───────────────────────────────────────── */
.metrics-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 9.5pt;
}
.metrics-table th {
    text-align: left;
    font-size: 8pt; font-weight: 600; letter-spacing: 0.05em;
    text-transform: uppercase; color: #64748b;
    padding: 8px 12px;
    background: #f8fafc;
    border-bottom: 1px solid var(--border);
}
.metrics-table td {
    padding: 10px 12px;
    border-bottom: 1px solid #f1f5f9;
    vertical-align: top;
}
.metrics-table tr:last-child td { border-bottom: none; }
.metric-value { font-weight: 700; font-size: 10.5pt; }
.metric-bar-wrap { display: flex; align-items: center; gap: 8px; }
.metric-bar-outer {
    flex: 1; height: 6px;
    background: #e2e8f0; border-radius: 3px; overflow: hidden;
}
.metric-bar-inner {
    height: 100%; border-radius: 3px;
}

/* ─── Two-column layout ───────────────────────────────────── */
.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.two-col-3-1 { display: grid; grid-template-columns: 2fr 1fr; gap: 14px; }

/* ─── Summary stats row ───────────────────────────────────── */
.stat-row {
    display: flex; gap: 16px; flex-wrap: wrap;
    margin-bottom: 24px;
}
.stat-box {
    flex: 1; min-width: 120px;
    background: #f8fafc;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 14px 16px;
    text-align: center;
}
.stat-box-value {
    font-size: 20pt; font-weight: 800; color: #0f172a;
    line-height: 1;
}
.stat-box-label {
    font-size: 8pt; color: #64748b; font-weight: 500;
    margin-top: 4px;
}

/* ─── Page footer ─────────────────────────────────────────── */
.page-footer {
    position: fixed;
    bottom: 0; left: 0; right: 0;
    height: 36px;
    background: #f8fafc;
    border-top: 1px solid var(--border);
    display: flex; align-items: center;
    justify-content: space-between;
    padding: 0 56px;
    font-size: 7.5pt; color: #94a3b8;
}

/* ─── Print overrides ─────────────────────────────────────── */
@media print {
    .section { page-break-inside: auto; }
    .item-card { page-break-inside: avoid; }
    .score-grid { page-break-inside: avoid; }
}
@page {
    margin: 0 0 40px 0;
    size: A4;
}
"""


# ─── Audit report HTML builder ───────────────────────────────────────────────

def _build_audit_report_html(audit_run):
    summary = audit_run.summary or {}
    score_breakdown = summary.get("score_breakdown", {})
    recommendations = summary.get("featured_recommendations") or summary.get("recommendations", [])
    issue_summary = summary.get("issue_summary", {})
    pagespeed = summary.get("pagespeed", {})
    performance_metrics = summary.get("performance_metrics", [])
    context_analysis = summary.get("context_analysis", {})
    top_issues = summary.get("top_issues", [])
    quick_wins = summary.get("quick_wins", [])
    change_report = getattr(audit_run, "change_report", None)

    overall = audit_run.overall_score or 0
    domain = _esc(audit_run.normalized_domain or "—")
    generated = date.today().strftime("%B %d, %Y")
    pages = audit_run.pages_crawled or 0
    total_issues = issue_summary.get("total", 0)

    # Cover score cards
    cover_cards_html = f"""
    <div class="cover-score-card">
        <div class="cover-score-card-label">Overall Score</div>
        <div class="cover-score-card-value" style="color:{_score_color(overall)}">{overall}</div>
        <div class="cover-score-card-sub">{_score_label(overall)}</div>
    </div>
    <div class="cover-score-card">
        <div class="cover-score-card-label">Pages Crawled</div>
        <div class="cover-score-card-value" style="color:#e2e8f0">{pages}</div>
        <div class="cover-score-card-sub">Scanned this run</div>
    </div>
    <div class="cover-score-card">
        <div class="cover-score-card-label">Issues Found</div>
        <div class="cover-score-card-value" style="color:{'#ef4444' if total_issues > 10 else '#f59e0b' if total_issues > 3 else '#22c55e'}">{total_issues}</div>
        <div class="cover-score-card-sub">Across all categories</div>
    </div>
    """

    if change_report:
        cover_cards_html += f"""
        <div class="cover-score-card">
            <div class="cover-score-card-label">New Issues</div>
            <div class="cover-score-card-value" style="color:#ef4444">{change_report.new_issue_count}</div>
            <div class="cover-score-card-sub">Since last audit</div>
        </div>
        <div class="cover-score-card">
            <div class="cover-score-card-label">Resolved</div>
            <div class="cover-score-card-value" style="color:#22c55e">{change_report.resolved_issue_count}</div>
            <div class="cover-score-card-sub">Fixed since last run</div>
        </div>
        """

    # Score breakdown grid
    score_keys = ["technical", "on_page", "content", "aeo", "internal_linking", "performance"]
    score_cards = ""
    for key in score_keys:
        item = score_breakdown.get(key)
        if not item:
            continue
        s = item.get("score", 0) or 0
        col = _score_color(s)
        lbl = _esc(item.get("label", key.replace("_", " ").title()))
        status = _esc(item.get("status", "").replace("_", " ").title())
        issues_count = item.get("issues", 0) or 0
        next_step = _esc(item.get("next_step", ""))
        bar_width = min(s, 100)
        score_cards += f"""
        <div class="score-card" style="--card-color:{col}">
            <div class="score-card-label">{lbl}</div>
            <div class="score-card-value">{s}</div>
            <div class="score-card-status">{status}</div>
            <div class="score-card-issues">{issues_count} issue{'s' if issues_count != 1 else ''}</div>
            <div class="score-bar"><div class="score-bar-fill" style="width:{bar_width}%"></div></div>
            {f'<div class="score-next-step">{next_step}</div>' if next_step else ''}
        </div>
        """

    # Issues section
    issues_html = ""
    source_issues = top_issues or []
    for i, issue in enumerate(source_issues[:8], start=1):
        title = _esc(issue.get("problem") or issue.get("title", "Issue"))
        body = _esc(issue.get("summary") or issue.get("description", ""))
        fix = _esc(issue.get("fix") or issue.get("recommended_fix", ""))
        cat = _esc(issue.get("scope_label") or issue.get("category", ""))
        prio = (issue.get("priority_score") or 0)
        if prio >= 8:
            sev_cls, sev_lbl = "severity-critical", "Critical"
        elif prio >= 6:
            sev_cls, sev_lbl = "severity-high", "High"
        elif prio >= 4:
            sev_cls, sev_lbl = "severity-medium", "Medium"
        else:
            sev_cls, sev_lbl = "severity-low", "Low"

        steps_html = ""
        for step in (issue.get("action_steps") or [])[:3]:
            steps_html += f'<div class="item-step">{_esc(step)}</div>'

        issues_html += f"""
        <div class="item-card">
            <div class="item-card-head">
                <div class="item-num">{i}</div>
                <div class="item-title">{title}</div>
                <span class="severity-badge {sev_cls}">{sev_lbl}</span>
            </div>
            {f'<div class="item-body">{body}</div>' if body else ''}
            {f'<div class="item-fix-label">Fix</div><div class="item-fix">{fix}</div>' if fix else ''}
            {f'<div class="item-meta"><span class="item-meta-chip">{cat}</span></div>' if cat else ''}
            {f'<div class="item-steps">{steps_html}</div>' if steps_html else ''}
        </div>
        """

    # Quick wins section
    wins_html = ""
    for i, win in enumerate(quick_wins[:6], start=1):
        title = _esc(win.get("problem") or win.get("title", "Quick win"))
        body = _esc(win.get("summary") or win.get("description", ""))
        fix = _esc(win.get("fix") or win.get("recommended_fix", ""))
        cat = _esc(win.get("scope_label") or win.get("category", ""))
        wins_html += f"""
        <div class="item-card">
            <div class="item-card-head">
                <div class="item-num" style="background:#059669">{i}</div>
                <div class="item-title">{title}</div>
                <span class="severity-badge severity-low">Quick win</span>
            </div>
            {f'<div class="item-body">{body}</div>' if body else ''}
            {f'<div class="item-fix-label">Action</div><div class="item-fix">{fix}</div>' if fix else ''}
            {f'<div class="item-meta"><span class="item-meta-chip">{cat}</span></div>' if cat else ''}
        </div>
        """

    # Recommendations section
    recs_html = ""
    for i, rec in enumerate(recommendations[:8], start=1):
        title = _esc(rec.get("title", "Recommendation"))
        desc = _esc(rec.get("description", ""))
        fix = _esc(rec.get("recommended_fix", ""))
        cat = _esc(rec.get("category", ""))
        impact = _esc(rec.get("estimated_impact", ""))
        prio = rec.get("priority_score", 0) or 0
        steps_html = ""
        for step in (rec.get("technical_steps") or [])[:3]:
            steps_html += f'<div class="item-step">{_esc(step)}</div>'
        meta_html = ""
        if cat:
            meta_html += f'<span class="item-meta-chip">{cat}</span>'
        if prio:
            meta_html += f'<span class="item-meta-chip">Priority {prio}</span>'
        if impact:
            meta_html += f'<span class="item-meta-chip">Impact: {impact}</span>'
        recs_html += f"""
        <div class="item-card">
            <div class="item-card-head">
                <div class="item-num">{i}</div>
                <div class="item-title">{title}</div>
            </div>
            {f'<div class="item-body">{desc}</div>' if desc else ''}
            {f'<div class="item-fix-label">Recommended fix</div><div class="item-fix">{fix}</div>' if fix else ''}
            {f'<div class="item-meta">{meta_html}</div>' if meta_html else ''}
            {f'<div class="item-steps">{steps_html}</div>' if steps_html else ''}
        </div>
        """

    # Performance metrics table
    perf_html = ""
    if performance_metrics:
        rows = ""
        for m in performance_metrics:
            val = _esc(m.get("value", "—"))
            lbl = _esc(m.get("label", ""))
            target = _esc(m.get("target_label", ""))
            status = (m.get("status") or "ok").lower()
            col = "#22c55e" if status == "good" else "#f59e0b" if status == "needs_work" else "#ef4444"
            impact = _esc(m.get("impact", ""))
            pct = min(int((m.get("raw_score") or 0) * 100), 100) if m.get("raw_score") else 60
            rows += f"""
            <tr>
                <td><strong>{lbl}</strong><br><span style="font-size:8pt;color:#94a3b8">{impact}</span></td>
                <td><span class="metric-value" style="color:{col}">{val}</span></td>
                <td style="color:#64748b">{target}</td>
                <td style="width:120px">
                    <div class="metric-bar-wrap">
                        <div class="metric-bar-outer">
                            <div class="metric-bar-inner" style="width:{pct}%;background:{col}"></div>
                        </div>
                    </div>
                </td>
            </tr>
            """
        perf_html = f"""
        <div class="section">
            <div class="section-header">
                <div class="section-title">Performance Metrics</div>
            </div>
            <table class="metrics-table">
                <thead>
                    <tr>
                        <th>Metric</th>
                        <th>Value</th>
                        <th>Target</th>
                        <th>Visual</th>
                    </tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
        </div>
        """

    # Context analysis
    context_html = ""
    if context_analysis:
        market = _esc(context_analysis.get("market_context", ""))
        insights = context_analysis.get("insights", [])[:4]
        competitors = context_analysis.get("competitors", [])[:4]
        insight_items = "".join(f"<li>{_esc(ins)}</li>" for ins in insights)
        comp_rows = ""
        for comp in competitors:
            if comp.get("status") == "unavailable":
                comp_rows += f'<tr><td>{_esc(comp.get("url",""))}</td><td colspan="3" style="color:#94a3b8">Unavailable</td></tr>'
            else:
                comp_rows += f"""
                <tr>
                    <td>{_esc(comp.get("url",""))}</td>
                    <td>{comp.get("word_count",0):,}</td>
                    <td>{comp.get("schema_count",0)}</td>
                    <td>{comp.get("response_time_ms",0)}ms</td>
                </tr>
                """
        context_html = f"""
        <div class="section">
            <div class="section-header">
                <div class="section-title">Market &amp; Competitor Context</div>
            </div>
            {f'<p style="color:#475569;margin-bottom:16px">{market}</p>' if market else ''}
            {f'<ul style="color:#475569;padding-left:20px;margin-bottom:16px;line-height:1.8">{insight_items}</ul>' if insight_items else ''}
            {f'''<table class="metrics-table">
                <thead><tr><th>Competitor</th><th>Words</th><th>Schema</th><th>Response</th></tr></thead>
                <tbody>{comp_rows}</tbody>
            </table>''' if comp_rows else ''}
        </div>
        """

    # Change report banner
    change_html = ""
    if change_report:
        headline = _esc(change_report.summary.get("headline", ""))
        change_html = f"""
        <div style="margin: 0 56px; background: linear-gradient(135deg,#0f172a,#1e3a5f);
                    border-radius: var(--radius); padding: 20px 24px; color:#fff;
                    display:flex; gap:24px; align-items:center; flex-wrap:wrap;">
            <div style="flex:1">
                <div style="font-size:8pt;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:#38bdf8;margin-bottom:6px">Changes since last audit</div>
                <div style="font-size:11pt;font-weight:700">{headline}</div>
            </div>
            <div style="display:flex;gap:20px;">
                <div style="text-align:center">
                    <div style="font-size:22pt;font-weight:800;color:#ef4444">{change_report.new_issue_count}</div>
                    <div style="font-size:8pt;color:#94a3b8">New issues</div>
                </div>
                <div style="text-align:center">
                    <div style="font-size:22pt;font-weight:800;color:#22c55e">{change_report.resolved_issue_count}</div>
                    <div style="font-size:8pt;color:#94a3b8">Resolved</div>
                </div>
            </div>
        </div>
        """

    issues_section = ""
    if issues_html:
        issues_section = f"""
        <div class="section">
            <div class="section-header">
                <div>
                    <div class="section-eyebrow">What's holding you back</div>
                    <div class="section-title">Critical Issues</div>
                </div>
            </div>
            <div class="card-list">{issues_html}</div>
        </div>
        """

    wins_section = ""
    if wins_html:
        wins_section = f"""
        <div class="section">
            <div class="section-header">
                <div>
                    <div class="section-eyebrow">Fast wins</div>
                    <div class="section-title">Quick Wins</div>
                </div>
            </div>
            <div class="card-list">{wins_html}</div>
        </div>
        """

    recs_section = ""
    if recs_html:
        recs_section = f"""
        <div class="section">
            <div class="section-header">
                <div>
                    <div class="section-eyebrow">Strategic roadmap</div>
                    <div class="section-title">Priority Recommendations</div>
                </div>
            </div>
            <div class="card-list">{recs_html}</div>
        </div>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Audit Report — {domain}</title>
<style>{_PDF_CSS}</style>
</head>
<body>

<!-- Cover -->
<div class="cover">
    <div class="cover-brand">
        <div class="cover-brand-mark">V</div>
        <div class="cover-brand-name">VRT Space</div>
    </div>
    <div class="cover-body">
        <div class="cover-report-type">Audit Report</div>
        <div class="cover-domain">{domain}</div>
        <div class="cover-subtitle">AI-driven SEO &amp; AEO visibility analysis</div>
        <div class="cover-score-row">{cover_cards_html}</div>
    </div>
    <div class="cover-footer">
        <span>Generated {generated}</span>
        <span>Confidential — for client use only</span>
    </div>
</div>

{change_html}

<!-- Score Breakdown -->
{f'''
<div class="section">
    <div class="section-header">
        <div>
            <div class="section-eyebrow">Full diagnosis</div>
            <div class="section-title">Score Breakdown</div>
        </div>
    </div>
    <div class="score-grid">{score_cards}</div>
</div>
''' if score_cards else ''}

{issues_section}
{wins_section}
{perf_html}
{recs_section}
{context_html}

<!-- Footer -->
<div class="page-footer">
    <span>VRT Space — vrtspace.ai</span>
    <span>{domain} · {generated}</span>
</div>

</body>
</html>"""


# ─── SEO report HTML builder ─────────────────────────────────────────────────

def _build_seo_report_html(payload):
    project = payload.get("project", {})
    profile = payload.get("profile", {})
    benchmark_summary = payload.get("benchmark_summary", {})
    recommendations = payload.get("recommendations", [])
    execution_queue = payload.get("execution_queue", [])
    campaigns = payload.get("campaigns", [])
    backlink_summary = payload.get("backlink_summary", {})
    backlink_prospects = payload.get("backlink_prospects", [])
    competitor_trace = payload.get("competitor_trace", [])
    value_summary = payload.get("value_summary", {})

    domain = _esc(project.get("domain", "—"))
    proj_name = _esc(project.get("name", domain))
    generated = date.today().strftime("%B %d, %Y")
    biz_type = _esc(profile.get("business_type", ""))
    location = _esc(profile.get("location", ""))
    service = _esc(profile.get("primary_service", ""))
    goal = _esc(profile.get("target_goal", ""))

    comp_count = benchmark_summary.get("available_competitors", 0)
    exec_items = value_summary.get("execution_items", 0)
    prospect_count = backlink_summary.get("prospect_count", 0)
    avg_relevance = benchmark_summary.get("average_relevance", 0)

    # Competitor table
    comp_rows = ""
    for item in competitor_trace[:10]:
        comp_domain = _esc(item.get("domain", ""))
        decision = _esc(item.get("final_decision_label", ""))
        page_count = item.get("page_count", 0)
        fit_score = item.get("fit", {}).get("best_page_score", 0)
        reason = _esc((item.get("fit") or {}).get("reason", ""))
        queries = ", ".join(_esc(q) for q in (item.get("queries") or [])[:3])
        col = "#22c55e" if "include" in decision.lower() else "#ef4444" if "exclude" in decision.lower() else "#f59e0b"
        comp_rows += f"""
        <tr>
            <td><strong>{comp_domain}</strong>{f'<br><span style="font-size:8pt;color:#94a3b8">{queries}</span>' if queries else ''}</td>
            <td><span style="color:{col};font-weight:600">{decision}</span></td>
            <td>{page_count}</td>
            <td>{fit_score}</td>
            <td style="font-size:8.5pt;color:#475569">{reason}</td>
        </tr>
        """

    # Recommendations
    recs_html = ""
    for i, item in enumerate(recommendations[:8], start=1):
        title = _esc(item.get("title", "Recommendation"))
        why = _esc(item.get("why_it_matters", ""))
        fix = _esc(item.get("recommended_fix", ""))
        cat = _esc(item.get("category", ""))
        recs_html += f"""
        <div class="item-card">
            <div class="item-card-head">
                <div class="item-num">{i}</div>
                <div class="item-title">{title}</div>
                {f'<span class="item-meta-chip">{cat}</span>' if cat else ''}
            </div>
            {f'<div class="item-body">{why}</div>' if why else ''}
            {f'<div class="item-fix-label">Recommended fix</div><div class="item-fix">{fix}</div>' if fix else ''}
        </div>
        """

    # Execution queue
    exec_html = ""
    for i, item in enumerate(execution_queue[:8], start=1):
        title = _esc(item.get("title", "Execution item"))
        deliverable = _esc(item.get("deliverable", ""))
        urls = ", ".join(_esc(u) for u in (item.get("target_urls") or [])[:3])
        steps_html = ""
        for step in (item.get("action_steps") or [])[:3]:
            steps_html += f'<div class="item-step">{_esc(step)}</div>'
        exec_html += f"""
        <div class="item-card">
            <div class="item-card-head">
                <div class="item-num">{i}</div>
                <div class="item-title">{title}</div>
                {f'<span class="severity-badge severity-info">{deliverable[:40]}</span>' if deliverable else ''}
            </div>
            {f'<div class="item-meta"><span class="item-meta-chip">Apply to: {urls}</span></div>' if urls else ''}
            {f'<div class="item-steps">{steps_html}</div>' if steps_html else ''}
        </div>
        """

    # Campaigns
    campaign_rows = ""
    for c in campaigns[:8]:
        ctitle = _esc(c.get("title", ""))
        status = _esc(c.get("status", ""))
        keyword = _esc(c.get("target_keyword", ""))
        prospects = c.get("backlink_prospect_count", 0)
        acquired = c.get("acquired_backlink_count", 0)
        draft = _esc(c.get("draft_title") or "Not created")
        col = "#22c55e" if "active" in status.lower() else "#f59e0b"
        campaign_rows += f"""
        <tr>
            <td><strong>{ctitle}</strong>{f'<br><span style="font-size:8pt;color:#94a3b8">{keyword}</span>' if keyword else ''}</td>
            <td><span style="color:{col};font-weight:600">{status}</span></td>
            <td style="font-size:8.5pt;color:#475569">{draft}</td>
            <td style="text-align:center">{prospects}</td>
            <td style="text-align:center;color:#22c55e;font-weight:600">{acquired}</td>
        </tr>
        """

    # Backlink prospects
    bp_rows = ""
    for p in backlink_prospects[:8]:
        bp_domain = _esc(p.get("domain", ""))
        ptype = _esc(p.get("prospect_type", ""))
        score = p.get("total_score", 0)
        asset = _esc(p.get("target_asset_title", ""))
        col = "#22c55e" if score >= 7 else "#f59e0b" if score >= 4 else "#94a3b8"
        bp_rows += f"""
        <tr>
            <td><strong>{bp_domain}</strong></td>
            <td style="color:#475569">{ptype}</td>
            <td><span style="color:{col};font-weight:700">{score}</span></td>
            <td style="font-size:8.5pt;color:#475569">{asset}</td>
        </tr>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SEO Report — {proj_name}</title>
<style>{_PDF_CSS}</style>
</head>
<body>

<!-- Cover -->
<div class="cover">
    <div class="cover-brand">
        <div class="cover-brand-mark">V</div>
        <div class="cover-brand-name">VRT Space</div>
    </div>
    <div class="cover-body">
        <div class="cover-report-type">SEO Strategy Report</div>
        <div class="cover-domain">{proj_name}</div>
        <div class="cover-subtitle">{domain}{f' · {location}' if location else ''}{f' · {biz_type}' if biz_type else ''}</div>
        <div class="cover-score-row">
            <div class="cover-score-card">
                <div class="cover-score-card-label">Competitors</div>
                <div class="cover-score-card-value" style="color:#e2e8f0">{comp_count}</div>
                <div class="cover-score-card-sub">Benchmarked</div>
            </div>
            <div class="cover-score-card">
                <div class="cover-score-card-label">Execution Items</div>
                <div class="cover-score-card-value" style="color:#e2e8f0">{exec_items}</div>
                <div class="cover-score-card-sub">Action ready</div>
            </div>
            <div class="cover-score-card">
                <div class="cover-score-card-label">Backlink Prospects</div>
                <div class="cover-score-card-value" style="color:#e2e8f0">{prospect_count}</div>
                <div class="cover-score-card-sub">Discovered</div>
            </div>
            <div class="cover-score-card">
                <div class="cover-score-card-label">Avg Relevance</div>
                <div class="cover-score-card-value" style="color:#e2e8f0">{avg_relevance}</div>
                <div class="cover-score-card-sub">Discovery precision</div>
            </div>
        </div>
    </div>
    <div class="cover-footer">
        <span>Generated {generated}</span>
        <span>{f'Service: {service}' if service else ''}{f' · Goal: {goal}' if goal else ''}</span>
    </div>
</div>

<!-- Competitor Benchmark -->
{f'''
<div class="section">
    <div class="section-header">
        <div>
            <div class="section-eyebrow">Benchmark analysis</div>
            <div class="section-title">Competitor Decision Trace</div>
        </div>
    </div>
    <table class="metrics-table">
        <thead>
            <tr>
                <th>Competitor</th>
                <th>Decision</th>
                <th>Pages</th>
                <th>Score</th>
                <th>Reason</th>
            </tr>
        </thead>
        <tbody>{comp_rows}</tbody>
    </table>
</div>
''' if comp_rows else ''}

<!-- Recommendations -->
{f'''
<div class="section">
    <div class="section-header">
        <div>
            <div class="section-eyebrow">Strategic playbook</div>
            <div class="section-title">Priority Recommendations</div>
        </div>
    </div>
    <div class="card-list">{recs_html}</div>
</div>
''' if recs_html else ''}

<!-- Execution Queue -->
{f'''
<div class="section">
    <div class="section-header">
        <div>
            <div class="section-eyebrow">What to do next</div>
            <div class="section-title">Execution Queue</div>
        </div>
    </div>
    <div class="card-list">{exec_html}</div>
</div>
''' if exec_html else ''}

<!-- Campaigns -->
{f'''
<div class="section">
    <div class="section-header">
        <div>
            <div class="section-eyebrow">Content pipeline</div>
            <div class="section-title">Campaign Tracker</div>
        </div>
    </div>
    <table class="metrics-table">
        <thead>
            <tr>
                <th>Campaign</th>
                <th>Status</th>
                <th>Draft</th>
                <th>Prospects</th>
                <th>Links</th>
            </tr>
        </thead>
        <tbody>{campaign_rows}</tbody>
    </table>
</div>
''' if campaign_rows else ''}

<!-- Backlink Prospects -->
{f'''
<div class="section">
    <div class="section-header">
        <div>
            <div class="section-eyebrow">Link acquisition</div>
            <div class="section-title">Top Backlink Prospects</div>
        </div>
    </div>
    <div class="stat-row" style="margin-bottom:16px">
        <div class="stat-box">
            <div class="stat-box-value">{backlink_summary.get("linkable_asset_count",0)}</div>
            <div class="stat-box-label">Linkable assets</div>
        </div>
        <div class="stat-box">
            <div class="stat-box-value">{prospect_count}</div>
            <div class="stat-box-label">Prospects found</div>
        </div>
        <div class="stat-box">
            <div class="stat-box-value">{backlink_summary.get("average_total_score",0)}</div>
            <div class="stat-box-label">Avg prospect score</div>
        </div>
    </div>
    <table class="metrics-table">
        <thead>
            <tr><th>Domain</th><th>Type</th><th>Score</th><th>Target asset</th></tr>
        </thead>
        <tbody>{bp_rows}</tbody>
    </table>
</div>
''' if bp_rows else ''}

<!-- Footer -->
<div class="page-footer">
    <span>VRT Space — vrtspace.ai</span>
    <span>{domain} · {generated}</span>
</div>

</body>
</html>"""


# ─── Playwright renderer ─────────────────────────────────────────────────────

def _html_to_pdf_bytes(html_content):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        page = browser.new_page()
        page.set_content(html_content, wait_until="networkidle")
        pdf_bytes = page.pdf(
            format="A4",
            print_background=True,
            margin={"top": "0", "right": "0", "bottom": "40px", "left": "0"},
        )
        browser.close()
    return pdf_bytes


# ─── Public API ──────────────────────────────────────────────────────────────

def build_audit_report_pdf(audit_run):
    html_content = _build_audit_report_html(audit_run)
    return _html_to_pdf_bytes(html_content)
