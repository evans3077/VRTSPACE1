import os
from django.core.wsgi import get_wsgi_application

# Proxy for Render's auto-detection (gunicorn app:app)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
app = get_wsgi_application()
application = app
