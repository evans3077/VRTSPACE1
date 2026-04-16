# Antigravity Phase 1: VRTSPACE Evolution Plan

This document serves as the master blueprint for the Antigravity overhaul of VRTSPACE. The goal is to transform the platform into a world-class, high-performance SEO/AEO/Content Audit engine with a premium UI/UX.

## 1. Project Analysis Summary
VRTSPACE is a sophisticated Django-based platform designed for modern search optimization. 

## 2. Platform Routes & Status (Visual & Performance Tracker)

| Route | Function | UI Status | Performance |
| :--- | :--- | :--- | :--- |
| `/` | Agency Homepage | [x] Improved | [x] Photon location live |
| `/tools/workspace-dashboard/` | Client Dashboard | [x] Improved | [x] Location autocomplete live |
| `/seo/workspace-seo/` | SEO Intelligence Hub | [/] In Progress | [x] Engine upgraded |
| `/aeo/workspace-aeo/` | AI Visibility (AEO) | [ ] Pending | [/] Pipeline wired |
| `/content/workspace-content/` | Content Optimizer | [ ] Pending | [ ] Pending |
| `/tools/account-dashboard/` | User Account/Billing | [x] Standard | [x] Sync |
| `/analytics/ops/` | Admin Operations | [x] Standard | [x] Sync |

## 3. The Core Problems
1. **UI Lag & Aesthetics**: Significant contrast issues and performance bottlenecks in the frontend templates.
2. **Search Precision**: SerpApi results are not yet optimized for the "best" competitive intelligence.
3. **Feature Gaps**: AEO and Content Optimization modules are pending.

## 3. Strategic Roadmap

### Phase A: UI/UX Premium Overhaul — [x] COMPLETE
- [x] Location autocomplete using free Photon/OSM API (no credit cost)
- [x] Widened to cities, towns, counties, states, regions
- [x] All form inputs readable, dark-mode contrast fixed

### Phase B: Search Algorithm Optimization — [x] COMPLETE
- [x] Replaced hardcoded `FOREIGN_GEO_HINTS` with dynamic `_parse_canonical_location()` + `_is_foreign_location()` working globally for any location
- [x] SerpApi now receives `gl` (country code) and `hl` (language) params derived from the selected canonical location — restricts SERP results to the right geography
- [x] City-level location scoring: `+6` for city match, `+3` region, `+2` country (vs old flat `+3` for any token)
- [x] Foreign geo-conflict penalty raised from `-8` to `-10`
- [x] City-only query variants added (`"{service} in {city}"`) for tighter local discovery
- [x] `intelligence.py` pipeline wired into `jobs.py` — triggers automatically after every completed audit
- [x] Intelligence results (AEO overview, related questions, local pack) stored in `profile.metadata["intelligence"]`

### Phase B: Search Algorithm Optimization (The Intelligence Engine)
- **SerpApi Multi-Engine Strategy**: Transition from single `google` engine to a hybrid approach (supporting `google_maps`, `google_local`, and `google_scholar` where appropriate).
- **Extended Result Extraction**: Modify `discovery.py` to capture `answer_box`, `featured_snippet`, and `related_questions` to build the foundational AEO data set.
- **Dynamic Filtering**: Refine `BLOCKED_COMPETITOR_DOMAINS` and `NON_COMPETITOR_RESULT_HINTS` to be context-aware based on the business type (e.g., allow certain directory sites for local services).
- **Weighted Scoring**: Enhance `discovery_score` to prioritize "Direct Competitors" over "Market Surfaces" to fulfill the user's need for "best results".

### Phase C: AEO (Answer Engine Optimization) — [x] COMPLETE
- [ ] Surface `intelligence.metadata["intelligence"]` data in AEO workspace UI
- [ ] SGE / AI Overview tracking and citability scoring
- [ ] Related Questions display and gap analysis
- [ ] Google Knowledge Graph presence check

### Phase D: Content Optimization Engine — [x] COMPLETE
- [x] Gap analysis against top-ranking competitors
- [x] Keyword clustering from Related Questions + SERP data

### Phase E: Monetization & Growth — [/] ACTIVE
- [ ] Billing cycle integration with credit quotas
- [ ] Lead capture conversion optimisation

### Phase F: Global Mobile Responsiveness Overhaul — [x] COMPLETE
- [x] Implement robust `@media` queries in `site.css` and `vrt-space-core.css`.
- [x] Refactor `.hero-grid`, `.contact-grid`, `.method-grid` and other rigid structures to single-column flex/grids on screens `< 1024px` and `< 768px`.
- [x] Create adaptive table wrappers for horizontal scrolling on data-heavy dashboards (Audit Results & SEO Intelligence Hub).
- [x] Audit typography and padding scales for mobile viewport legibility.

## 4. Immediate Next Steps
- [ ] Audit `apps/seo/services.py` for SerpApi call efficiency.
- [ ] Refactor `apps/seo/views.py` to modularize template rendering.
- [ ] Establish a global CSS framework in `public/static/css/vrt-space-core.css`.

---
*Created by Antigravity AI - 2026-04-09*
