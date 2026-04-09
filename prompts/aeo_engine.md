You are a senior Django engineer and AI search optimization expert.

Build a Context-Aware AEO (Answer Engine Optimization) system for a SaaS platform.

---

## 🎯 OBJECTIVE

Analyze a website and determine its visibility and readiness for AI-powered search engines like ChatGPT, Gemini, and Perplexity.

---

## 🧠 FEATURES

### 1. AI Visibility Checker

* Accept URL and keyword
* Determine if content is likely to be used in AI answers
* Return visibility score

---

### 2. Entity Optimization

Check if the website clearly defines:

* business name
* services
* location
* industry

---

### 3. Content Structure Analysis

Detect:

* lack of direct answers
* poor formatting
* missing summaries
* absence of FAQ sections

---

### 4. AI Answer Simulation

* Analyze top-ranking competitor content
* Identify patterns used in AI-friendly answers
* Compare against user content

---

### 5. Context Awareness

Use:

* business type
* location
* target goal

Modify all recommendations accordingly.

---

### 6. Recommendation Engine

Each recommendation must include:

* issue
* why AI ignores this
* fix
* example rewrite
* expected impact

---

### 7. Scoring System

Return:

* visibility score
* entity score
* structure score
* completeness score

---

### 8. Django Integration

Create models:

* AEOAudit
* AIRecommendation

---

### 9. Performance

* Use async tasks
* Cache results
* Limit scraping depth

---

## ⚠️ RULES

* Avoid generic advice
* Always include context (industry + location)
* Focus on actionable insights
* Optimize for SaaS scalability

---

## 🚀 OUTPUT

Provide:

* Django services
* analysis logic
* recommendation engine
* models
* sample output
* frontend structure

---

Build this as a modular engine.
