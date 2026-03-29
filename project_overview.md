🧠 00_PROJECT_OVERVIEW.md
Purpose

Define what VRT SPACE is building:

A high-performance SEO/AEO agency platform optimized for:

Organic search (Google)
AI search (ChatGPT, Gemini, Perplexity)
Lead generation
Authority building
Core Outcomes
Rank globally
Generate inbound leads
Become a cited AI source
Core Differentiator

“We don’t just rank websites. We make brands answer engines trust.”

🏗️ 01_SYSTEM_ARCHITECTURE.md
Stack (STRICT)
Backend: Django (monolith, modular apps)
Frontend: Django Templates + HTMX (or Alpine)
DB: PostgreSQL
Cache: Redis
Queue: Celery
CDN: Cloudflare
Apps Structure
apps/
├── core/
├── seo/
├── aeo/
├── content/
├── leads/
├── case_studies/
├── tools/
├── analytics/
Rules
No fat views
Business logic → services layer
DB queries → optimized (select_related/prefetch)