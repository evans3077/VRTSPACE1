🧩 06_DATA_MODELS.md
Core Models
Service
CaseStudy
Article
Lead
AuditRequest
FAQ
Example
class Article(models.Model):
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    content = models.TextField()
    pillar = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
Rule
Every model must support SEO fields:
meta_title
meta_description
schema_json