# VRT SPACE AGENCY – Product & UX Improvement Plan (AI‑First SEO & AEO)

Goal: Evolve VRT SPACE AGENCY into a clearly differentiated, AI‑first SEO/AEO platform that can compete with and stand alongside Ahrefs, Semrush, Surfer, Frase, Similarweb, SE Ranking, and other AI visibility tools.[web:31][web:100][web:101][web:102][web:103][web:104][web:110][web:98]

---

## 1. Positioning & Narrative

### 1.1 Core positioning

**Current:**  
- Strong “audit → gaps → workspaces → rerun” story, but “AI visibility” and “AEO” are still mostly conceptual.[web:98]

**Target:**  
- VRT SPACE AGENCY = “AI visibility and Answer Engine Optimization control center” for brands, agencies, and SaaS teams.

**Proposed positioning statement:**

> VRT SPACE AGENCY is an AI‑first SEO and Answer Engine Optimization platform that shows where AI systems talk about you, where they ignore you, and what you need to fix in your SEO, content, and performance to become the source behind the answer.

Key ideas:
- “AI‑first” and “Answer Engine Optimization” are the main story, not a side feature.[web:102][web:104][web:110]
- Classic SEO audits, technical diagnostics, and speed insights are the infrastructure that supports AI visibility.

### 1.2 Hero copy (homepage)

**Replace generic audit copy with:**

- **Headline:**  
  “Be the source behind the answer.”

- **Subheadline:**  
  “VRT SPACE AGENCY audits your site, tracks where AI chatbots and AI Overviews cite you, and shows exactly what to fix so you win more AI‑driven traffic.”

- **Hero bullets:**  
  - “See when AI answers mention you vs your competitors.”  
  - “Fix technical, speed, and content gaps that block AI citations.”  
  - “Track AI visibility scores and improvements over time.”

- **Hero CTA buttons:**  
  - Primary: “Run free AI visibility audit”  
  - Secondary: “View sample AI visibility dashboard”

### 1.3 Explicit AI surfaces

Add a line clearly listing the AI environments VRT works with:

> “Optimized for visibility across ChatGPT, Perplexity, Gemini, Claude, Bing Copilot, and Google AI Overviews.”

This mirrors how Frase, Similarweb AEO, SE Ranking, and others now explicitly name AI platforms they support.[web:102][web:103][web:104][web:110]

### 1.4 “Why Answer Engine Optimization?” section

Add a band that explains AEO vs traditional SEO in simple terms.

**Section title:**  
“Search is moving from links to answers.”

**Key points (bulleted):**
- Traditional SEO optimizes for rankings and SERP clicks.  
- Answer Engine Optimization optimizes for citations and recommendations in AI answers.[web:95][web:104][web:110]  
- AI chatbots and AI Overviews can recommend competitors without your website ever being clicked.  
- VRT measures and improves your presence in those answers.

Optionally, include a simple comparison table (SEO vs AEO) for clarity.

---

## 2. Homepage Structure & IA

### 2.1 Recommended homepage structure

1. **Hero (AEO + AI visibility focus)**  
2. **Social proof**  
   - “Trusted by [future logos]” + short stats where possible.  
3. **Why AI visibility matters now**  
   - One band with 2–3 short facts about AI search usage and AI Overviews.  
4. **Product overview sections**  
   - AI Visibility & AEO  
   - SEO & Technical Audits  
   - Speed & Web Vitals  
   - Workspaces & Collaboration  
5. **Use cases by persona**  
   - Agencies / In‑house SEO & Growth / SaaS & product‑led teams.  
6. **Testimonials / Case snippets**  
7. **FAQ focused on AI search & AEO**  

### 2.2 Product sections (marketing site)

**AI Visibility & AEO section**

- Headline: “AI visibility you can actually measure and improve.”  
- Elements to describe:  
  - AI Visibility Score (AVS) per domain/topic.  
  - AI citations tracking (which engines, which prompts, which pages).  
  - Competitor share‑of‑voice in AI answers.  
  - AI traffic insights (estimated value of being cited).  

**SEO & Technical Audits section**

- Headline: “SEO and technical health built for AI‑first search.”  
- Describe: crawl diagnostics, indexation issues, structured data, internal links.

**Speed & Web Vitals section**

- Headline: “Speed and web vitals that keep you in AI’s good graces.”  
- Describe: LCP, CLS, INP and their impact on eligibility for AI Overviews and AI crawlers.[web:10][web:14]

**Workspaces & collaboration section**

- Headline: “Workspaces that turn audits into ongoing missions.”  
- Describe: project‑based workspaces, saved runs, rerun cycles, and shareable reports.

---

## 3. Product Architecture – AI Visibility & AEO

### 3.1 Core modules to formalize

Make AEO tangible by naming and structuring modules.

**AI Visibility Score (AVS)**  
- Composite score that summarises how visible and recommended a brand is across AI engines for specific topics.  
- Inputs:  
  - Citation frequency per engine.  
  - Share‑of‑voice vs competitors.  
  - Recommendation strength (how strongly the answer recommends you).  
  - Topic coverage breadth.  
  - Technical readiness (core SEO + performance).  

**AI Citation Tracker**  
- For each query/prompt or topic, capture:  
  - Which engines were checked.  
  - The exact domains/URLs cited.  
  - Whether the brand was mentioned or recommended.  
- Provide both granular and aggregate views (e.g., per topic, per brand, per engine).

**Prompt & Topic Explorer**  
- Group related prompts into “topics” (e.g., “best CRM for freelancers”).  
- For each topic:  
  - Show AI Visibility Score, citations, and main pages used as sources.  
  - Show competitor list and gaps (topics where competitors are cited but you’re not).

**AI Traffic Insights (later iteration)**  
- Rough estimates of potential AI‑driven traffic and value based on prompt volume and visibility.

### 3.2 Sidebar & navigation (in‑app)

Reorganise the in‑app sidebar so AEO is the first‑class citizen:

- Overview  
- **AI Visibility**  
- SEO Audit  
- Speed & Web Vitals  
- Backlinks  
- Keywords & SERPs  
- Competitors  
- Workspaces / Projects  
- Reports & Exports  
- Settings & Integrations  

Each module should open to a dashboard, not a blank table.

---

## 4. Dashboard & UX Improvements

### 4.1 Mission Control overview (per project)

Design a project‑level overview dashboard that surfaces primary KPIs:

**Top row cards:**
- AI Visibility Score (with trend indicator).  
- AI citations count (by engine, with small sparkline).  
- Competitor share‑of‑voice (bar chart snippet).  
- Technical health score.  
- Web vitals status (percentage of URLs in “good” state).

**Second row:**
- Topic map grid:  
  - Each card = topic cluster.  
  - Colors indicate win/lose status (e.g., green = winning, red = missing AI citations).  
- AVS over time chart.  
- “Top opportunities” list:  
  - Topics where you rank in search but are missing in AI answers.  
  - Pages with AI citations but poor performance metrics.  

### 4.2 AI Visibility module UX

When user clicks “AI Visibility” in the sidebar:

1. **Default view:**
   - Competitor bar chart showing AVS for your domain vs up to 5 competitors.  
   - Filters: engine, topic cluster, time range.

2. **Topics list:**
   - Table or grid of topics with:  
     - AVS, citations count, engines covered.  
     - Key pages used as sources.  
     - “View prompts” and “See recommended fixes” actions.

3. **Prompt detail view:**
   - For a specific prompt or question:  
     - Snapshot of AI answers across engines.  
     - Domains cited, rank in answer, whether your brand is included.  
     - Notes and recommended changes (content, technical, schema).

### 4.3 Audit & speed UX

- Follow the pattern of GTmetrix and PageSpeed Insights:  
  - Overall performance score.  
  - CWV metrics with thresholds.  
  - “Top issues” list with severity and count.[web:10][web:14]  
- Group issues by category: Crawlability, Indexation, Performance, Content, Schema, Security.

---

## 5. Onboarding & Activation

### 5.1 First‑run experience

After account creation:

1. **Project creation wizard:**
   - Domain input.  
   - Option to add main competitors.  
   - Select key topics/goals (checklist or text input).

2. **Checklist for activation (visible in app):**
   - [ ] Run first AI visibility audit.  
   - [ ] Run first SEO + technical audit.  
   - [ ] Review AI Visibility Score and top 5 opportunities.  
   - [ ] Schedule a rerun.

3. **Guided tour for AI Visibility dashboard:**
   - Short overlays pointing to AVS, competitor chart, topic cards, and “next actions.”

### 5.2 Sample workspace

Provide a **sample project** (demo site) with populated AI visibility data:

- Let users explore the full experience while their first audit runs in the background.  
- Include a toggle like “View: sample data / my data”.

### 5.3 “First 30 days” flow

Create an email/onboarding sequence aligned with product actions:

- **Week 1:** Run audits, understand AI Visibility Score.  
- **Week 2:** Fix core technical & speed issues.  
- **Week 3:** Expand topics and prompts, improve content for key topics.  
- **Week 4:** Compare AI visibility month‑over‑month, share a report internally or with clients.

---

## 6. Workspaces & Collaboration

### 6.1 Workspace design

Clarify and highlight workspaces as a key differentiator:

- Each workspace holds multiple projects (domains).  
- Each project has its own Mission Control + AI Visibility + SEO/Audit dashboards.  
- Provide role‑based access (owner, editor, viewer).

### 6.2 Collaboration features

- Commenting on specific findings or metrics (e.g., “tag dev here to fix CLS”).  
- Shareable links to dashboards or snapshot reports.  
- Ability to pin specific views (“Pinned: AI visibility for product pages”).

---

## 7. Reporting & Exports

### 7.1 Report templates

Define 2–3 prebuilt report templates:

1. **AI Visibility Report**
   - Summary of AVS, citations, AI engines, top topics, competitors.  
   - Suggested next steps.

2. **Technical & Speed Report**
   - Technical health score, key issues, CWV metrics.

3. **Monthly Progress Report**
   - AI visibility trend, key fixes implemented, results month‑over‑month.

### 7.2 Export options

- PDF exports with clean, card‑based layout.  
- CSV exports for advanced users.  
- “Copy as Notion/markdown” section for agencies to paste into their own systems.

---

## 8. Partner‑Readiness (Influencer & Agency)

### 8.1 Partner‑centric assets

Even though this doc is focused on product, you should have product‑driven assets that support partner efforts:

- A “Partners” page explaining the AI visibility problem and how VRT solves it.  
- Short, embedded product tour video focused on AEO and AI visibility.  
- A one‑pager that describes the AI Visibility Score, AI Citation Tracker, and how agencies can resell “AI visibility audits.”

### 8.2 API & integrations (later phase)

As you mature:

- Expose read‑only endpoints for:  
  - AI Visibility Score  
  - AI citations data  
  - Technical/audit summaries  
- Offer simple webhooks for alerts (e.g., major AVS drop, AI citations missing for a core topic).

---

## 9. Implementation Phases (Product & UX only)

**Phase 1 – 4–6 weeks**

- Update homepage hero and AEO narrative.  
- Create named AI Visibility modules in the UI (AVS card + simple competitor chart + citations table).  
- Reorganize in‑app sidebar to surface AI Visibility first.  
- Add basic Mission Control overview with top‑row cards.

**Phase 2 – 2–3 months**

- Expand AI visibility capabilities (topics, prompts, AI Overviews tracking).  
- Build topic map and opportunity list in AI Visibility module.  
- Improve audit & speed dashboards and issue grouping.  
- Implement onboarding checklist and sample workspace.

**Phase 3 – 3–6 months**

- Introduce AI traffic and sentiment insights.  
- Enhance collaboration (comments, pinned views).  
- Add robust reports and export templates.  
- Build initial API endpoints for AI visibility data and audit summaries.

---

This Markdown file captures the core product, UX, messaging, and feature improvements that will help VRT SPACE AGENCY feel like a **first‑class AI‑first SEO/AEO platform** rather than “just another SEO audit tool,” and give you a concrete blueprint to refine further with Claude.