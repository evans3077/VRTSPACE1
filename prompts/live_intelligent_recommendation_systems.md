You are a senior Python Django engineer, performance optimization expert, and product-focused SaaS architect.

I have already built a web optimization audit system using Google PageSpeed Insights API. The system fetches Core Web Vitals and performance data for a given URL.

Your task is to transform the current static audit output into a **live, intelligent recommendation engine** that provides real-time, structured, prioritized, and actionable insights to users.

---

## 🎯 OBJECTIVE

Convert raw PageSpeed API data into:

1. Human-readable insights
2. Prioritized recommendations
3. Actionable steps
4. Live UI updates (dynamic rendering)
5. SaaS-ready output (storable, reusable, scalable)

---

## 🧠 SYSTEM REQUIREMENTS

### 1. Data Processing Layer

* Parse PageSpeed API JSON response

* Extract:

  * LCP
  * CLS
  * INP / FID
  * TTFB
  * Performance score
  * Opportunities
  * Diagnostics

* Normalize values into a consistent structure

---

### 2. Intelligent Recommendation Engine

Build a rule-based + weighted scoring engine:

Each issue must include:

* `title`
* `description`
* `impact_level` (High / Medium / Low)
* `priority_score` (numeric ranking)
* `affected_metric` (e.g., LCP, CLS)
* `recommended_fix`
* `technical_steps`
* `estimated_impact` (e.g., "Improve load time by ~1.2s")

---

### 3. Priority Logic

* High impact issues (e.g., LCP > 4s, CLS > 0.25) must appear first
* Combine:

  * Severity
  * Frequency
  * User impact

Sort recommendations automatically.

---

### 4. Real-Time UX (CRITICAL)

Recommendations must feel “live”:

* Show loading states (skeleton UI)
* Stream or progressively render results
* Animate score updates
* Highlight improvements dynamically

Use:

* HTMX or AJAX for partial updates
* No full page reloads

---

### 5. Output Structure (API / Backend)

Return structured JSON:

{
"score": 72,
"metrics": {...},
"recommendations": [
{
"title": "...",
"impact_level": "High",
"priority_score": 95,
"fix": "...",
"steps": [...]
}
]
}

---

### 6. Database Integration (Django Models)

Store results for SaaS use:

Model: AuditResult

* user (FK)
* url
* score
* metrics (JSONField)
* recommendations (JSONField)
* created_at

---

### 7. Frontend Display (Conversion-Focused)

Each recommendation must be shown as:

* Color-coded card:

  * Red = High
  * Yellow = Medium
  * Green = Low

Include:

* Clear problem
* Why it matters
* Exact fix
* Expandable technical steps

---

### 8. “Fix This For Me” CTA

For every HIGH priority issue:

Add a CTA:
👉 “Fix this for me”

Trigger:

* Lead capture form OR
* Service request endpoint

---

### 9. Performance Requirements

* Use async processing (Celery if needed)
* Cache repeated requests
* Avoid blocking UI

---

### 10. Extendability (IMPORTANT)

Design system so it can later support:

* SEO recommendations
* AEO (AI search) optimization
* Content analysis

---

## 🚀 DELIVERABLES

Provide:

1. Django service layer (recommendation engine logic)
2. Sample rules for Core Web Vitals issues
3. Django model for storing audit results
4. API or view to return structured recommendations
5. Frontend rendering approach (HTMX or JS)
6. Example UI structure (HTML)

---

## 🧭 PRODUCT THINKING

This is not just a feature.

Build it as:

* A SaaS engine
* A conversion tool
* A scalable module

Every recommendation must:

* Educate the user
* Push them toward action
* Increase perceived value

---

## ⚠️ RULES

* Do NOT output raw PageSpeed data directly
* Always translate into human insights
* Avoid generic advice
* Be specific and actionable
* Optimize for speed and UX

---

Now implement the system cleanly and modularly.
