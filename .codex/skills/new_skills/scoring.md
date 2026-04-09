# VRT SPACE — Scoring Engine Skill

## 🧠 PURPOSE

Transform raw analysis into:

* Simple scores
* Actionable insights

---

## 🎯 OBJECTIVES

* Combine multiple engines into one score
* Maintain consistency
* Provide explanations

---

## 🏗️ ARCHITECTURE PRINCIPLES

1. All scores MUST be normalized (0–100)
2. Each engine MUST produce independent scores
3. Final score MUST use weighted aggregation
4. Scores MUST be explainable

---

## 🧩 SCORE COMPONENTS

### Performance Score

Source:

* PageSpeed API

---

### SEO Score

Break into:

* technical
* content
* keyword

---

### AI Visibility Score

Break into:

* entity clarity
* structure
* completeness

---

## ⚙️ WEIGHTING SYSTEM

Example:

```python
WEIGHTS = {
    "performance": 0.3,
    "seo": 0.4,
    "ai": 0.3
}
```

---

## 🧮 FINAL SCORE CALCULATION

```python
def calculate_score(performance, seo, ai):
    return (
        performance * 0.3 +
        seo * 0.4 +
        ai * 0.3
    )
```

---

## 📊 SUBSCORE CALCULATION

Each subscore must:

* Have defined inputs
* Be reproducible
* Avoid randomness

---

## 🧠 EXPLANATION ENGINE

For each score:

Return:

* meaning
* weaknesses
* improvement actions

---

## 📈 TREND TRACKING

Store:

* previous scores
* timestamps

Compare:

* improvement %
* decline %

---

## ⚠️ EDGE CASES

* Missing data → fallback scoring
* Partial audits → weighted adjustment

---

## 📤 OUTPUT FORMAT

```json
{
  "overall": 78,
  "performance": 85,
  "seo": 72,
  "ai": 68,
  "insights": []
}
```

---

## ❌ DO NOT

* Use arbitrary scoring
* Mix raw metrics with scores
* Hide scoring logic

---

## ✅ SUCCESS CONDITION

Users trust the score as:

* accurate
* meaningful
* actionable
