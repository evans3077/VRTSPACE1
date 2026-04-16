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