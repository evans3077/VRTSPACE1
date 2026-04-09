⚙️ 02_BACKEND_DJANGO_GUIDE.md
Coding Standards
Class-based views (CBVs)
Service layer pattern
Signals only when necessary
Example Pattern
views → services → models
Rules
No logic in templates
No direct DB access in views beyond simple queries
Every feature must be reusable