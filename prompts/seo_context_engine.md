You are a senior Django architect building an advanced SaaS SEO platform.

Your task is to build a **Context-Aware Business Intelligence Engine** that enhances SEO and performance audits using industry and location data.

---

## 🎯 OBJECTIVE

Make all recommendations:

* Industry-specific
* Location-aware
* Goal-driven

---

## 🧠 FEATURES

### 1. Business Profile System

Collect:

* business_type
* location
* target_goal

Store in Django model.

---

### 2. Industry Intelligence Layer

Create predefined rule sets per industry:

Example:
Hotel:

* prioritize local SEO
* focus on booking keywords
* emphasize amenities and events pages

SaaS:

* focus on feature pages
* comparison keywords
* content marketing

Store rules in JSON.

---

### 3. Local SEO Layer

Generate:

* location-based keywords
* “near me” variations
* city-specific intent queries

---

### 4. Context-Aware Recommendations

Modify all SEO suggestions based on:

* industry
* location
* business goal

Example:

Instead of:
“Add more keywords”

Return:
“You are missing ‘conference venues in Nairobi’ — high intent keyword for hotels in your area.”

---

### 5. Integration

Inject this layer into:

* SEO engine
* Web optimization engine
* Future AEO engine

---

### 6. Output

Return structured recommendations:

{
"context": {...},
"recommendations": [...]
}

---

## ⚠️ RULES

* Do not generate generic advice
* Always include context in every recommendation
* Keep system modular
* Make it extensible for more industries

---

## 🚀 DELIVERABLES

* Django models
* Context engine service
* Example industry rules
* Integration with SEO audit
* Sample outputs

---

Build this as a core system of the SaaS.
