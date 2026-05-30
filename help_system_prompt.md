# VRT SPACE — Help & Navigation System: Prompt Pack

A set of copy-paste prompts for your AI coding agent to build an embedded help system
that makes VRT SPACE feel **simple**, even though it does a lot.

The strategy is a **3-layer help system**. Each layer removes one specific kind of confusion:

| Layer | Kills the question… | Artifacts |
|---|---|---|
| **1. Orientation** | *"What even is this product / why should I care?"* | "How VRT Works" page · plain-language concept primers |
| **2. In-context** | *"What is THIS screen / number doing?"* | module intro banners · jargon info-popovers · helpful empty states · first-run tour |
| **3. Self-serve** | *"How do I do X?"* | Help Center hub · getting-started checklist · glossary · floating help launcher |

> **Golden rule for every prompt below:** explain in plain language first, jargon second.
> The product is intimidating because of words like *AEO, AVS, Share of Voice, citations, prompts*.
> Every one of those must be defined the moment a user meets it.

---

## 0 · MASTER CONTEXT (prepend this to every prompt below)

```
You are building help & onboarding UI for VRT SPACE, an AI-first SEO / AEO platform
(Django + server-rendered templates). Goal: make a feature-rich product FEEL simple.

PRODUCT IN ONE LINE
VRT SPACE audits a website, tracks where AI tools (ChatGPT, Perplexity, Gemini, Google AI
Overviews, Bing Copilot) mention or ignore the brand, and tells the user exactly what to
fix. The core loop is: AUDIT → SEE GAPS → FIX → RERUN.

THE MODULES (workspace sidebar, in order)
- Overview        — project mission-control dashboard
- AI Visibility   — where AI engines cite you vs competitors (the flagship)
- Prompts         — the AI questions/topics you track
- Share of Voice  — your slice of AI answers vs competitors
- SEO Audit       — technical + on-page health
- Content         — content planning / optimization / publishing
- (Workspace mgmt: All Clients, Team, Billing & Credits, Publishing, Settings, Affiliate)

VOICE & TONE
- Plain, calm, confident. Second person ("you"). Short sentences.
- Define every acronym on first use. Never assume the user knows SEO/AEO.
- No hype, no emoji in body copy. One idea per sentence.
- Always tie a feature back to a benefit ("...so you know which pages to fix first").

DESIGN SYSTEM — USE TOKENS, DO NOT INVENT VALUES
- Tokens live in colors_and_type.css as --vrt-* custom properties. Use them for ALL
  color, type, spacing, radius, shadow, motion. Examples:
  brand=var(--vrt-color-brand) (#0284c7), ink=var(--vrt-color-ink),
  paper=var(--vrt-color-paper), radius=var(--vrt-radius-lg), shadow=var(--vrt-shadow-md).
- Type: --vrt-font-sans = Space Grotesk; --vrt-font-mono = JetBrains Mono (eyebrows/labels/numbers).
- Helper classes exist: .vrt-h1..h4, .vrt-lead, .vrt-body, .vrt-small, .vrt-caption,
  .vrt-eyebrow, .vrt-mono, .vrt-num. Reuse them.
- Icons: FontAwesome solid (<i class="fa-solid fa-...">), matching the existing sidebar.
- Light shell (white/paper surfaces). Restrained shadows, no gradient text, no glow.

CONVENTIONS
- Server-rendered Django templates in /templates/<app>/. Reusable bits go in
  /templates/includes/. The workspace sidebar is includes/workspace_nav.html.
- Match the markup style already in the codebase (BEM-ish .ws-* classes, {% url %} tags).
- Accessibility: real headings, aria-labels, focus-visible states (.vrt-focusable),
  keyboard-dismissable overlays, 44px min hit targets.
```

---

## LAYER 1 — ORIENTATION

### Prompt 1.1 · "How VRT Works" page (the 60-second mental model)

```
[PASTE MASTER CONTEXT]

Build a standalone "How VRT Works" page at /templates/core/how_it_works.html
(extends base.html). Its only job: in under 60 seconds of reading, a brand-new user
understands what VRT does and what they'll do with it. This is the single page we link
from onboarding, the help launcher, and empty states.

Structure, top to bottom:
1. Hero: eyebrow "HOW IT WORKS", h1 "Be the source behind the answer.", one-sentence lead.
2. The loop, as 4 numbered steps shown as a horizontal flow (stack on mobile):
   1) Audit your site  2) See where AI ignores you  3) Fix the gaps  4) Rerun & track.
   Each step: FontAwesome icon, 3-word title, one plain sentence, the module it maps to.
3. "What the words mean" — a 4-card row defining, in one sentence each:
   AI Visibility, Answer Engine Optimization (AEO), Share of Voice, Prompts.
   Each card links to the matching module and to the glossary entry.
4. "Where to start" — three persona cards (Agency / In-house SEO / SaaS team), each with a
   single recommended first action and a button into the app.
5. Closing CTA band: "Run your first audit" primary button + "Open a sample workspace" secondary.

Constraints: use --vrt-* tokens and .vrt-* helper classes only. Max content width
var(--vrt-container-max). No stock imagery — use simple tokenized icon tiles. Fully responsive.
Acceptance: a non-SEO person can read it in <60s and correctly say what VRT does and what to click next.
```

### Prompt 1.2 · Plain-language concept primers (reusable explainer partial)

```
[PASTE MASTER CONTEXT]

Create a reusable Django include /templates/includes/concept_primer.html that renders a
compact "concept primer" card from context vars (term, acronym, plain_definition,
why_it_matters, learn_more_url). It's used inline at the top of complex modules.

Design: left accent rail in var(--vrt-color-brand), small mono eyebrow with the acronym,
bold plain-English term, one-sentence definition, a muted "Why it matters" line, and a
text "Learn more →" link. Dismissible (remembers dismissal per user via a data attribute +
localStorage key passed in). Compact — never taller than ~140px.

Then provide ready-to-use context for these five concepts, each written in plain language
a small-business owner would understand (no SEO jargon inside the definition):
AI Visibility · AEO · AI Visibility Score (AVS) · Share of Voice · Prompts/Topics.

Acceptance: drop {% include 'includes/concept_primer.html' with term=... %} at the top of
any module and it explains that module's core idea before the user sees a single chart.
```

---

## LAYER 2 — IN-CONTEXT HELP

### Prompt 2.1 · Module intro banners + helpful empty states

```
[PASTE MASTER CONTEXT]

For EACH workspace module (Overview, AI Visibility, Prompts, Share of Voice, SEO Audit,
Content) add two things, built as reusable includes so they stay consistent:

A) /templates/includes/module_header.html — a slim header strip: module name, a one-line
   plain-language description of what this screen is for, and a single primary action
   (e.g. "Run audit", "Add prompt"). Optional "?" button opening the help launcher (Prompt 3.3)
   filtered to this module.

B) /templates/includes/empty_state.html — a friendly empty state (used when there's no data
   yet) with: a calm icon tile, a headline that names the ONE next action, a sentence of
   reassurance, a primary button, and a "See sample data" secondary link so the screen is
   never a scary blank table.

Write the actual copy for all 6 modules' headers and empty states. Tone = calm and directive:
tell the user the single next thing to do. Use --vrt-* tokens, FontAwesome icons, responsive.
Acceptance: no module ever opens as a blank/unexplained screen.
```

### Prompt 2.2 · Jargon info-popovers (the "?" next to every metric)

```
[PASTE MASTER CONTEXT]

Build a lightweight, dependency-free info-popover component so any metric, score, or column
header can carry a "?" that explains it on hover/click. This is the #1 lever for reducing
perceived complexity — every unfamiliar number gets a plain-language explanation in place.

Deliver:
- /templates/includes/info_tip.html — renders <button class="vrt-infotip" aria-label=...>
  with a fa-circle-question icon; content supplied via attributes (title + body, optional
  "How it's calculated" line + learn-more link).
- A small JS module (vanilla, no deps) that positions the popover, handles hover + click +
  keyboard focus, closes on Esc/outside-click, and is screen-reader friendly (aria-describedby).
- Tokenized styles: paper background, var(--vrt-shadow-lg), var(--vrt-radius-md), max-width ~280px,
  body in .vrt-small, title in mono eyebrow.

Then provide finished copy for the key terms users hit first: AI Visibility Score, Share of
Voice, Citation, Prompt, Recommendation strength, Topic cluster, Core Web Vitals (LCP/CLS/INP),
Technical health score. One plain sentence each + an optional "How it's calculated" line.
Acceptance: every jargon term on a dashboard has a "?" that explains it without leaving the page.
```

### Prompt 2.3 · First-run guided tour (overlay coach marks)

```
[PASTE MASTER CONTEXT]

Build a first-run guided tour for the AI Visibility dashboard (the flagship, and the most
intimidating screen). Vanilla JS, no libraries.

Behavior: on a user's first visit to the AI Visibility module, show a sequence of 4 coach-mark
steps that spotlight + explain, in order: (1) the AI Visibility Score card, (2) the competitor
share-of-voice chart, (3) the topic/prompt cards, (4) the "top opportunities / next actions" list.
Each step: a tooltip card anchored to the target with a one-sentence plain explanation, a
progress dot row (1/4), Back/Next, and a Skip. Dim the rest of the page with a scrim that has a
cut-out around the highlighted element. Persists "seen" in localStorage; never auto-shows again.
Re-triggerable from the help launcher ("Replay tour").

Styling via --vrt-* tokens; tooltip uses paper bg, --vrt-shadow-xl, brand-colored Next button.
Fully keyboard navigable (Tab/Esc/Enter), respects prefers-reduced-motion.
Acceptance: a first-time user understands the four things on the AI Visibility screen without reading docs.
```

---

## LAYER 3 — SELF-SERVE HELP

### Prompt 3.1 · Getting-started activation checklist

```
[PASTE MASTER CONTEXT]

Build a persistent "Getting started" checklist that drives activation and shrinks the product
to 4 obvious steps. Two surfaces, one source of truth:

A) A compact checklist card on the Overview dashboard.
B) An expanded version inside the help launcher.

Steps (each: title, one-line why, deep-link, auto-complete condition the backend can set):
  [ ] Add your website (create project)
  [ ] Run your first AI Visibility audit
  [ ] Review your score + top 3 opportunities
  [ ] Fix one issue and rerun

Design: progress ring or "2 of 4 done" mono label, checked items with strikethrough + success
tint, current step emphasized with brand accent, completed-all state collapses to a small
dismissible "You're set up ✓" pill. Use --vrt-* tokens. Build as /templates/includes/
getting_started.html driven by a context list so the backend marks steps done.
Acceptance: a new user always sees exactly what to do next, capped at 4 steps.
```

### Prompt 3.2 · Glossary page

```
[PASTE MASTER CONTEXT]

Build a glossary page at /templates/core/glossary.html (extends base.html). It's the canonical
plain-language dictionary for every VRT/SEO/AEO term, linked from primers, info-tips, and the
help launcher.

Layout: sticky alphabetical / category filter rail on the left (Categories: AI Visibility,
SEO, Content, Performance, Account), searchable filter input at top (client-side filter, no
backend), and a clean definition list. Each entry: term + acronym chip, a 1–2 sentence plain
definition, an optional "In VRT, you'll find this in [Module →]" link, and a "Related terms" row.
Anchor IDs on each term so info-tips can deep-link (e.g. /glossary#avs).

Seed it with at least these, fully written in plain language: AEO, AI Visibility, AI Visibility
Score (AVS), Citation, Share of Voice, Prompt, Topic cluster, Recommendation strength,
Core Web Vitals (LCP/CLS/INP), Technical health, Crawlability, Indexation, Schema/Structured
data, Internal linking, Workspace, Project, Credits, Rerun.
Use --vrt-* tokens, .vrt-* type helpers, mono for term chips. Responsive; rail collapses on mobile.
Acceptance: every acronym in the product resolves to a one-line plain-English answer here.
```

### Prompt 3.3 · Help Center hub + article template

```
[PASTE MASTER CONTEXT]

Build a Help Center at /templates/core/help_center.html (extends base.html) plus a reusable
article template /templates/core/help_article.html.

Help Center hub:
- Big search box at top (client-side filter over article titles/tags for now; leave a hook
  for server search later).
- Category grid matching the user's mental model: "Getting started", "AI Visibility & AEO",
  "SEO & Technical", "Content & Publishing", "Workspaces & Team", "Billing & Credits".
  Each category card: icon, name, article count, top 3 article links.
- A "Popular / Start here" row linking: How VRT Works, Run your first audit, Understand your
  AI Visibility Score, Read your Share of Voice.

Article template: breadcrumb (Help / Category / Article), h1, est. read time, a right-hand
"On this page" anchor nav for long articles, clean prose styling using .vrt-body/.vrt-lead,
callout component for tips/warnings, "Was this helpful? 👍/👎" footer, and "Related articles".

Both use --vrt-* tokens, max width var(--vrt-container-max), fully responsive.
Acceptance: a user can self-serve "how do I…" without contacting support; categories mirror the sidebar.
```

### Prompt 3.4 · Floating help launcher (the always-there "?" )

```
[PASTE MASTER CONTEXT]

Build a floating help launcher present on every workspace page — the single, always-available
entry to help so users never feel stuck. Vanilla JS, no deps. Build as
/templates/includes/help_launcher.html + a small JS module; include it from base.html (or the
workspace layout) for authenticated users.

Closed state: a small circular brand button bottom-right (fa-circle-question / fa-life-ring),
44px+, with a subtle unread dot if there's a new tip.

Open state: a compact panel (paper bg, --vrt-shadow-xl, --vrt-radius-lg) with:
- A search input that filters help articles + glossary terms client-side.
- "On this page" — context-aware: shows 2–3 help links relevant to the CURRENT module
  (read a data-help-context attribute the page sets, e.g. "ai-visibility").
- Quick links: How VRT Works · Getting started checklist · Glossary · Replay tour · Contact.
Keyboard: opens with "?" shortcut, closes on Esc, focus-trapped, fully aria-labeled.
Tokenized styling, respects prefers-reduced-motion.
Acceptance: from any screen, help is one click away and already filtered to where the user is.
```

### Prompt 3.5 (optional power-user) · Command palette navigation

```
[PASTE MASTER CONTEXT]

Add a command palette (Cmd/Ctrl-K) for fast navigation — this makes "many modules" feel small
because power users stop hunting through the sidebar. Vanilla JS, no deps.

Behavior: Cmd/Ctrl-K opens a centered modal with a search input and a fuzzy-filtered list of:
all workspace modules (with their icons), top help articles, glossary terms, and quick actions
("Run audit", "Add prompt", "New project"). Arrow keys to move, Enter to go, Esc to close.
Group results by type with mono section labels. Recent/most-used pinned at top.
Tokenized styling: paper modal, --vrt-shadow-xl, brand highlight on the active row.
Fully keyboard-driven and accessible (combobox/listbox aria roles).
Acceptance: a user can reach any module or action in under 2 seconds without using the mouse.
```

---

## SEQUENCING — build in this order for fastest "feels simpler" payoff

1. **2.2 Info-popovers** + **1.2 Concept primers** — biggest perceived-complexity drop for least effort.
2. **2.1 Module headers & empty states** — no screen is ever blank or unexplained.
3. **3.1 Getting-started checklist** + **2.3 First-run tour** — guide the first session.
4. **1.1 How VRT Works** + **3.2 Glossary** — the orientation backbone everything links to.
5. **3.4 Help launcher** + **3.3 Help Center** — the self-serve safety net.
6. **3.5 Command palette** — power-user polish, last.

## One reusable copy rule to enforce across all of them
> Every explanation answers three things in order: **What it is** (plain) → **Why it matters to you** → **What to do next** (a link/action). If a help element doesn't end in a next step, it isn't finished.
