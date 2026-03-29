# VRT SPACE — AI Content Generator Skill

## 🧠 PURPOSE

Generate high-quality, structured, and optimized content that:

* Ranks on search engines (SEO)
* Gets cited by AI systems (AEO)
* Converts users (business goals)

---

## 🎯 OBJECTIVES

The AI Generator MUST:

1. Understand the business context (industry, location, goal)
2. Use SEO insights (keyword gaps, competitor patterns)
3. Apply AEO principles (structured, direct answers)
4. Generate content that is:

   * actionable
   * structured
   * relevant
   * non-generic

---

## 🏗️ ARCHITECTURE PRINCIPLES

1. Content MUST be context-aware (no generic outputs)
2. Content MUST follow structure templates
3. Content MUST integrate SEO + AEO rules
4. Output MUST be editable and modular
5. Generation MUST be deterministic where possible (reduce randomness)

---

## 🧩 CORE MODULES

### 1. Context Loader

Pull:

* business_type
* location
* goal

Example:
Hotel + Nairobi + Bookings

---

### 2. SEO Data Loader

Pull from SEO Engine:

* target keywords
* keyword gaps
* competitor headings
* top-ranking patterns

---

### 3. AEO Structure Engine

Define required structure:

* direct answer blocks
* FAQs
* summaries
* structured sections

---

### 4. Content Template System

Each content type MUST follow a template.

---

## 📄 CONTENT TYPES TO SUPPORT

### 1. SEO Landing Pages

Example:
“Best Hotels in Nairobi”

Structure:

* H1
* intro (direct answer)
* sections (rooms, amenities, location)
* FAQs
* CTA

---

### 2. Blog Articles

Structure:

* H1
* introduction
* topic clusters
* internal linking suggestions
* summary

---

### 3. Service Pages

Structure:

* value proposition
* methodology
* benefits
* case examples
* CTA

---

### 4. AI Answer Blocks (CRITICAL)

Short structured responses like:

* definitions
* lists
* comparisons

---

### 5. Meta Content

Generate:

* titles
* meta descriptions
* headings

---

## ⚙️ GENERATION FLOW

```text
User selects content type
↓
Context Engine loads business data
↓
SEO Engine provides keyword gaps
↓
AEO Engine provides structure rules
↓
Template selected
↓
AI generates structured content
↓
Post-processing (format, validation)
↓
Output returned
```

---

## 🧠 PROMPT ENGINEERING RULES

Every generation MUST include:

* business context
* location context
* keyword targets
* tone (professional, conversion-focused)

---

## ✍️ OUTPUT REQUIREMENTS

Content MUST:

* include target keywords naturally
* include headings (H1, H2, H3)
* include FAQ section
* include summary or conclusion
* include CTA where relevant

---

## 🧪 QUALITY VALIDATION

Before returning content:

Check:

* keyword presence
* structure completeness
* readability
* duplication

---

## ⚠️ EDGE CASES

* Missing context → request user input
* Weak keyword data → fallback to general patterns
* Over-optimization → reduce keyword stuffing

---

## 🧠 PERSONALIZATION RULES

Example:

Hotel in Nairobi:

DO:

* include “Nairobi”
* include local intent keywords
* include booking-focused CTA

DO NOT:

* generate generic global content

---

## 📤 OUTPUT FORMAT

```json
{
  "title": "...",
  "meta_description": "...",
  "content": "...",
  "keywords_used": [...],
  "suggested_internal_links": [...]
}
```

---

## 🔌 DJANGO INTEGRATION

Create:

### Model: GeneratedContent

Fields:

* user
* project
* content_type
* content
* keywords
* created_at

---

### Service Layer

Functions:

* generate_content()
* validate_content()
* optimize_content()

---

## 💰 MONETIZATION HOOKS

* Free users:

  * limited generations
  * restricted word count

* Paid users:

  * full content
  * advanced templates
  * AI answer blocks

---

## ❌ DO NOT

* Generate generic filler content
* Ignore SEO/AEO inputs
* Return unstructured text
* Skip validation

---

## ✅ SUCCESS CONDITION

The system produces content that:

* ranks
* converts
* gets cited by AI
* feels tailored to the business
