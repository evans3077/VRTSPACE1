import tempfile
from pathlib import Path
from threading import Lock

from django.conf import settings
from django.core.management import call_command
from django.db import connection


_runtime_db_lock = Lock()
_runtime_db_ready = False


def _required_tables_present(required_tables):
    if not required_tables:
        return True

    with connection.cursor() as cursor:
        existing_tables = set(connection.introspection.table_names(cursor))

    return all(table_name in existing_tables for table_name in required_tables)


def ensure_runtime_database(*, required_tables=None):
    global _runtime_db_ready
    required_tables = tuple(required_tables or ())

    if _runtime_db_ready and _required_tables_present(required_tables):
        return

    engine = settings.DATABASES["default"]["ENGINE"]
    if engine != "django.db.backends.sqlite3":
        _runtime_db_ready = True
        return

    sentinel = Path(tempfile.gettempdir()) / ".vrtspace-runtime-db-ready"
    if sentinel.exists() and _required_tables_present(required_tables):
        _runtime_db_ready = True
        return

    with _runtime_db_lock:
        if sentinel.exists() and _required_tables_present(required_tables):
            _runtime_db_ready = True
            return

        call_command("migrate", interactive=False, verbosity=0)
        sentinel.touch()
        _runtime_db_ready = _required_tables_present(required_tables)
