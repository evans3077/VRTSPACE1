"""Append missing CSS utilities to site.css"""
import os

css_path = os.path.join(os.path.dirname(__file__), "..", "public", "static", "css", "site.css")

additions = r"""

/* ============================================================
   SCORE PILLS — used across audit, SEO, AEO, workspace views
   ============================================================ */

.score-pill {
    display: inline-flex;
    align-items: center;
    padding: 0.28rem 0.65rem;
    border-radius: 999px;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    white-space: nowrap;
}

.score-pill.score-high,
.score-pill.score-strong {
    background: rgba(22, 163, 74, 0.12);
    color: #15803d;
    border: 1px solid rgba(22, 163, 74, 0.2);
}

.score-pill.score-med,
.score-pill.score-medium,
.score-pill.score-stable {
    background: rgba(234, 179, 8, 0.12);
    color: #a16207;
    border: 1px solid rgba(234, 179, 8, 0.2);
}

.score-pill.score-low,
.score-pill.score-weak,
.score-pill.score-critical {
    background: rgba(220, 38, 38, 0.1);
    color: #b91c1c;
    border: 1px solid rgba(220, 38, 38, 0.18);
}

/* ============================================================
   MOBILE NAVIGATION — hamburger + overlay drawer
   ============================================================ */

.nav-hamburger {
    display: none;
    flex-direction: column;
    gap: 5px;
    cursor: pointer;
    padding: 0.5rem;
    border: none;
    background: none;
    border-radius: 8px;
}

.nav-hamburger span {
    display: block;
    width: 22px;
    height: 2px;
    background: var(--ink);
    border-radius: 2px;
    transition: transform 0.25s ease, opacity 0.25s ease;
}

.nav-mobile-drawer {
    display: none;
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 200;
    background: rgba(255, 253, 248, 0.98);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    padding: 1.5rem;
    flex-direction: column;
    gap: 0.75rem;
    overflow-y: auto;
}

.nav-mobile-drawer.is-open {
    display: flex;
}

.nav-mobile-close {
    align-self: flex-end;
    background: rgba(15, 23, 42, 0.06);
    border: none;
    font-size: 1.2rem;
    cursor: pointer;
    padding: 0.6rem 0.9rem;
    color: var(--ink);
    border-radius: 12px;
    font-weight: 700;
}

.nav-mobile-brand {
    font-weight: 800;
    letter-spacing: 0.08em;
    font-size: 1rem;
    padding: 0.5rem 0;
}

.nav-mobile-links {
    display: flex;
    flex-direction: column;
    gap: 0.45rem;
    margin-top: 0.5rem;
}

.nav-mobile-links a {
    padding: 0.9rem 1.1rem;
    border-radius: 14px;
    font-weight: 700;
    font-size: 1rem;
    background: rgba(15, 23, 42, 0.04);
    display: block;
    color: var(--ink);
}

.nav-mobile-links a:hover {
    background: rgba(15, 23, 42, 0.09);
}

.nav-mobile-actions {
    display: flex;
    flex-direction: column;
    gap: 0.65rem;
    margin-top: 1rem;
}

.nav-mobile-actions .button {
    width: 100%;
    justify-content: center;
}

@media (max-width: 860px) {
    .nav-hamburger {
        display: flex;
    }

    .site-header .nav-links,
    .site-header .workspace-menu,
    .site-header .workspace-project-switch,
    .site-header .nav-cta,
    .site-header .nav-auth-link,
    .site-header .nav-account-link {
        display: none;
    }

    .nav-actions {
        gap: 0.5rem;
        justify-content: flex-end;
    }

    .nav-shell {
        padding: 0.75rem 0;
    }
}

/* ============================================================
   IN-PAGE JUMP NAVIGATION (long workspace pages)
   ============================================================ */

.page-jump-nav {
    position: sticky;
    top: 62px;
    z-index: 30;
    background: rgba(255, 253, 248, 0.94);
    border-bottom: 1px solid rgba(15, 23, 42, 0.07);
    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
    padding: 0.6rem 0;
    margin-bottom: 1.5rem;
}

.page-jump-links {
    display: flex;
    gap: 0.45rem;
    overflow-x: auto;
    scrollbar-width: none;
    -ms-overflow-style: none;
    padding: 0.1rem 0;
}

.page-jump-links::-webkit-scrollbar { display: none; }

.page-jump-link {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    padding: 0.45rem 0.85rem;
    border-radius: 999px;
    font-size: 0.75rem;
    font-weight: 700;
    white-space: nowrap;
    color: rgba(15, 23, 42, 0.65);
    background: rgba(15, 23, 42, 0.05);
    transition: background 0.15s ease, color 0.15s ease, transform 0.15s ease;
    text-decoration: none;
}

.page-jump-link:hover {
    background: rgba(15, 23, 42, 0.1);
    color: var(--ink);
    transform: translateY(-1px);
}

.page-jump-link.is-active {
    background: var(--signal);
    color: white;
    box-shadow: 0 8px 20px rgba(249, 115, 22, 0.25);
}

/* ============================================================
   CROSS-MODULE COMMAND CARD (workspace overview)
   ============================================================ */

.command-card {
    background: linear-gradient(135deg, rgba(19, 34, 56, 0.97) 0%, rgba(23, 43, 69, 0.98) 100%);
    border-radius: 28px;
    padding: 2rem;
    color: white;
    position: relative;
    overflow: hidden;
}

.command-card::before {
    content: "";
    position: absolute;
    top: -60px;
    right: -60px;
    width: 220px;
    height: 220px;
    background: radial-gradient(circle, rgba(249, 115, 22, 0.22) 0%, transparent 70%);
    pointer-events: none;
}

.command-card .eyebrow {
    color: rgba(255, 255, 255, 0.5);
}

.command-module-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 1rem;
    margin-top: 1.5rem;
}

.command-module-tile {
    padding: 1rem 1.1rem;
    border-radius: 18px;
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.1);
    transition: background 0.2s ease;
    text-decoration: none;
    color: inherit;
}

.command-module-tile:hover { background: rgba(255, 255, 255, 0.11); }

.command-module-label {
    font-size: 0.65rem;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: rgba(255, 255, 255, 0.45);
    margin-bottom: 0.4rem;
}

.command-module-value {
    font-size: 1.5rem;
    font-weight: 800;
    color: white;
    line-height: 1;
}

.command-module-status {
    font-size: 0.75rem;
    color: rgba(255, 255, 255, 0.6);
    margin-top: 0.3rem;
}

.command-priority-list {
    display: grid;
    gap: 0.6rem;
    margin-top: 1.5rem;
}

.command-priority-item {
    display: flex;
    align-items: flex-start;
    gap: 0.75rem;
    padding: 0.85rem 1rem;
    border-radius: 14px;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.08);
}

.command-priority-num {
    width: 24px;
    height: 24px;
    border-radius: 999px;
    background: var(--signal);
    color: white;
    font-size: 0.68rem;
    font-weight: 800;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}

.command-priority-text {
    font-size: 0.85rem;
    color: rgba(255, 255, 255, 0.82);
    line-height: 1.5;
}

/* ============================================================
   EVIDENCE CARD
   ============================================================ */

.evidence-card {
    padding: 0.9rem 1rem;
    border-radius: 14px;
    background: rgba(14, 165, 233, 0.06);
    border: 1px solid rgba(14, 165, 233, 0.12);
    margin-top: 0.6rem;
}

.evidence-card-label {
    font-size: 0.65rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: rgba(15, 23, 42, 0.5);
    margin-bottom: 0.3rem;
}

.evidence-card-text {
    font-size: 0.85rem;
    color: #0f172a;
    line-height: 1.55;
}

/* ============================================================
   PROGRESS BAR
   ============================================================ */

.progress-bar-shell {
    height: 5px;
    border-radius: 999px;
    background: rgba(15, 23, 42, 0.08);
    overflow: hidden;
    margin-top: 0.5rem;
}

.progress-bar-fill {
    height: 100%;
    border-radius: 999px;
    background: linear-gradient(90deg, var(--signal), #fb923c);
    transition: width 0.9s ease;
}

.progress-bar-fill-green { background: linear-gradient(90deg, #16a34a, #4ade80); }
.progress-bar-fill-blue  { background: linear-gradient(90deg, #0ea5e9, #38bdf8); }

/* ============================================================
   METRIC HERO STRIP
   ============================================================ */

.metric-hero-strip {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
    gap: 1rem;
    padding: 1.3rem 1.5rem;
    border-radius: 22px;
    background: linear-gradient(135deg, rgba(249, 115, 22, 0.06), rgba(14, 165, 233, 0.05));
    border: 1px solid rgba(15, 23, 42, 0.06);
    margin-bottom: 1.5rem;
}

.metric-hero-item { display: grid; gap: 0.2rem; }

.metric-hero-value {
    font-size: clamp(1.5rem, 2.5vw, 2rem);
    font-weight: 800;
    line-height: 1;
    color: var(--ink);
}

.metric-hero-label {
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: rgba(15, 23, 42, 0.52);
}

/* ============================================================
   STATUS DOTS
   ============================================================ */

.status-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 999px;
    margin-right: 0.35rem;
    flex-shrink: 0;
}

.status-dot-green { background: #16a34a; }
.status-dot-amber { background: #ca8a04; }
.status-dot-red   { background: #dc2626; }
.status-dot-blue  {
    background: #0ea5e9;
    box-shadow: 0 0 0 0 rgba(14, 165, 233, 0.6);
    animation: seo-pulse 1.6s ease-out infinite;
}

/* ============================================================
   MODULE SECTION BADGES
   ============================================================ */

.module-section-head {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 1.25rem 0 0.5rem;
    margin-bottom: 0.25rem;
}

.module-section-badge {
    display: inline-flex;
    align-items: center;
    padding: 0.32rem 0.85rem;
    border-radius: 999px;
    font-size: 0.68rem;
    font-weight: 800;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    white-space: nowrap;
}

.module-section-badge-seo     { background: rgba(15, 23, 42, 0.08); color: #0f172a; }
.module-section-badge-aeo     { background: rgba(234, 88, 12, 0.1); color: #c2410c; }
.module-section-badge-content { background: rgba(22, 163, 74, 0.1); color: #15803d; }
.module-section-badge-audit   { background: rgba(249, 115, 22, 0.1); color: #c2410c; }

/* ============================================================
   HOMEPAGE AUDIT FORM — progressive disclosure
   ============================================================ */

.audit-form-advanced {
    display: grid;
    gap: 0.85rem;
    overflow: hidden;
    max-height: 0;
    opacity: 0;
    pointer-events: none;
    transition: max-height 0.45s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.3s ease;
}

.audit-form-advanced.is-open {
    max-height: 1200px;
    opacity: 1;
    pointer-events: auto;
}

.audit-form-expand-btn {
    display: flex;
    align-items: center;
    gap: 0.45rem;
    background: none;
    border: none;
    font: inherit;
    font-size: 0.85rem;
    font-weight: 700;
    color: var(--signal);
    cursor: pointer;
    padding: 0.4rem 0;
}

@media (max-width: 980px) {
    .command-module-grid { grid-template-columns: repeat(2, 1fr); }
    .metric-hero-strip   { grid-template-columns: repeat(2, 1fr); }
    .page-jump-nav       { top: 54px; }
    .upsell-grid         { grid-template-columns: 1fr; }
}
"""

with open(css_path, "a", encoding="utf-8") as f:
    f.write(additions)

print(f"Appended CSS to: {os.path.abspath(css_path)}")
