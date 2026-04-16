---
name: vrt-space-workspace-retention
description: Workspace, credits, reruns, and retention-loop guidance for the VRT SPACE revamp. Use when editing workspace dashboards, audit history, project switching, credit messaging, progress tracking, upgrade prompts, rerun flows, or any authenticated product screen that should strengthen repeated usage over time.
---

# VRT Space Workspace Retention

Use this skill when authenticated product work should make users return, rerun, and upgrade naturally.

## Workflow

1. Read `references/workspace-loop.md` for the intended retention behavior.
2. Read `references/current-workspace-reality.md` before changing views or templates.
3. Keep the workspace focused on project execution first, with billing and account management as supporting surfaces.

## Primary Hotspots

- `templates/tools/workspace_dashboard.html`
- `templates/includes/workspace_nav.html`
- `templates/tools/audit_result.html`
- `apps/tools/views.py`
- `apps/tools/billing_views.py`
- `apps/leads/billing.py`
- `apps/tools/automation.py`

## Retention Rules

- Treat the workspace as a growth log, not a file cabinet.
- Make reruns easy, visible, and tied to improvement.
- Show what changed since the previous run whenever possible.
- Keep credits framed as access to progress and deeper insight.
- Make upgrade prompts appear after visible value, not before it.
- Keep the next recommended action obvious from every major workspace state.

## Product Requirements

- One active project context at a time
- Visible latest state across Audit, SEO, and AEO
- Clear history and before/after movement
- Credit balance with simple explanations
- Natural path from first audit to repeat usage
- Locked states that explain the next unlock in operational terms

## Review Checklist

- Does the workspace tell the user what to do next?
- Is progress over time more visible than raw feature inventory?
- Do credits and limits feel understandable?
- Does a rerun feel like a meaningful validation step?
- Are account and billing concerns separated from day-to-day project work?

## References

- `references/workspace-loop.md`: retention model from the revamp prompt pack
- `references/current-workspace-reality.md`: current implementation strengths and gaps
- `../../../prompts/new/Vrt Space Agency Codex Skills Pack.MD`
- `../../../prompts/new/Vrt Space Agency Codex Master Instructions.md`
- `../../../plan.md`
