You are a senior Django engineer, content-systems architect, and AI search optimization expert.

Build a context-aware AI content generation system for VRT SPACE AGENCY.

---

## OBJECTIVE

Create a generation engine that turns business context, SEO signals, and AEO rules into structured, reusable content that:

- ranks in traditional search
- gets cited by AI systems
- supports conversion goals
- stays editable by humans

---

## CURRENT PROJECT CONTEXT

The project already has:

- a Django monolith
- service and marketing content in `apps/core/site_content.py`
- a public audit engine in `apps/tools/`
- lead capture in `apps/leads/`

The project does not yet have:

- a dedicated content generation app
- a generated-content model
- generator APIs
- editorial generation workflows

Build this to fit the existing monolith instead of inventing a separate architecture.

---

## REQUIRED CAPABILITIES

### 1. Context Loader

The generator must accept and use:

- business type
- location
- target audience
- page goal
- offer or service

If context is missing, the system should degrade gracefully and request the minimum extra input.

---

### 2. SEO Intelligence Layer

Use SEO-aware inputs such as:

- target keywords
- search intent
- keyword gaps
- internal-link opportunities
- competitor heading patterns

---

### 3. AEO Structure Layer

The system must shape output for AI readability by supporting:

- direct answer intros
- structured sections
- concise summaries
- FAQ sections
- entity-rich phrasing
- schema-friendly formatting

---

### 4. Supported Output Types

Build templates for:

- service pages
- landing pages
- blog articles
- AI answer blocks
- meta titles and descriptions
- FAQ sets

---

### 5. Output Contract

Return structured output, not just plain text.

Example shape:

```json
{
  "title": "...",
  "meta_description": "...",
  "content": "...",
  "faq_items": [],
  "keywords_used": [],
  "suggested_internal_links": [],
  "cta": "..."
}
```

---

### 6. Django Integration

Design:

- a `GeneratedContent` model or equivalent
- service-layer generation functions
- optional JSON endpoint for async generation
- review and edit workflow before publication

Keep generation logic in services, not in views.

---

### 7. Validation Layer

Before returning output, validate:

- required sections exist
- target keywords are used naturally
- output is not generic
- duplication risk is low
- CTA is relevant
- answer-first structure is preserved

---

## RULES

- Do not generate generic agency copy.
- Always use business and location context when available.
- Keep generation deterministic where possible.
- Separate generated drafts from published content.
- Make the system reusable across multiple page types.
- Preserve VRT SPACE positioning and proprietary method language where relevant.

---

## DELIVERABLES

Provide:

1. Django models
2. service-layer generation design
3. template system for output types
4. validation rules
5. example API or view contract
6. sample generated output

---

## PRODUCT THINKING

This is not just a writing helper.

Build it as:

- a reusable content engine
- a structured publishing assistant
- a future SaaS capability
- a system that can eventually consume audit outputs and business context together

---

Now implement the system cleanly and modularly inside the existing VRT SPACE architecture.
