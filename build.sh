#!/usr/bin/env bash
# Render build script. Runs on every deploy.
# Exit immediately on any error.
set -o errexit

echo "── Installing Python dependencies ───────────────────────────────"
pip install -r requirements.txt

echo "── Collecting static files ──────────────────────────────────────"
python manage.py collectstatic --no-input

echo "── Applying database migrations ─────────────────────────────────"
python manage.py migrate --no-input

echo "── Ensuring superuser account ───────────────────────────────────"
# Runs only when SUPERUSER_EMAIL + SUPERUSER_PASSWORD env vars are set.
# Remove the env vars from Render dashboard after first successful deploy.
python manage.py ensure_superuser || echo "INFO ensure_superuser skipped (env vars not set)"

echo "── Syncing workspace plan catalog ───────────────────────────────"
# Idempotent: only inserts/updates plans that don't already exist.
python -c "
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from apps.leads.billing import sync_workspace_plan_catalog
sync_workspace_plan_catalog()
print('OK plan catalog synced')
"

echo "── Seeding blog articles + case studies ─────────────────────────"
# Idempotent: update_or_create per slug, so it just refreshes content.
python manage.py seed_blog || echo "WARN seed_blog failed (non-fatal)"

# Demo users / data — only seeds if SEED_DEMO=1 in env. Skip in production.
if [ "${SEED_DEMO:-0}" = "1" ]; then
  echo "── Seeding demo users (SEED_DEMO=1) ────────────────────────────"
  python manage.py seed_demo || echo "WARN seed_demo failed (non-fatal)"
fi

echo "── Build complete ✓ ─────────────────────────────────────────────"
