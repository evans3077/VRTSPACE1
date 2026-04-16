You are a senior data systems engineer and SaaS product architect.

Build a scoring engine for a SaaS platform that analyzes websites based on performance, SEO, and AI visibility.

---

## 🎯 OBJECTIVE

Create a unified scoring system that:

* Combines multiple metrics
* Produces meaningful scores
* Feels accurate and trustworthy

---

## 🧠 FEATURES

### 1. Score Categories

Calculate:

* Performance Score (from PageSpeed)
* SEO Score (technical + content + keywords)
* AI Visibility Score (AEO engine)

---

### 2. Weighted Scoring System

Define weights:

Example:

* Performance: 30%
* SEO: 40%
* AI Visibility: 30%

Return:

* Overall Score (0–100)

---

### 3. Subscores

Break SEO into:

* technical SEO
* content quality
* keyword coverage

Break AI into:

* entity clarity
* structure
* completeness

---

### 4. Score Normalization

Ensure:

* All scores use same scale (0–100)
* No bias from one engine

---

### 5. Score Explanation Engine

For every score:
Return:

* what it means
* why it is low/high
* how to improve

---

### 6. Trend Tracking

Compare:

* previous scores
* current scores

Show:

* improvement or decline

---

### 7. Django Integration

Store scores in:

* AuditResult
* SEOAudit
* AEOAudit

---

### 8. Output Structure

{
"overall_score": 78,
"performance": 85,
"seo": 72,
"ai_visibility": 68,
"insights": [...]
}

---

## ⚠️ RULES

* Avoid arbitrary scoring
* Keep scoring transparent
* Ensure consistency across audits
* Make results easy to understand

---

## 🚀 OUTPUT

Provide:

* scoring logic
* weighting system
* Django integration
* example calculations
* explanation generator

---

Build this as a core intelligence system.
