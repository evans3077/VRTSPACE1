import tempfile
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from apps.core import runtime


class RuntimeDatabaseTests(SimpleTestCase):
    def setUp(self):
        runtime._runtime_db_ready = False

    def tearDown(self):
        runtime._runtime_db_ready = False

    @override_settings(
        DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
    )
    def test_sqlite_runtime_triggers_migrate_once(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("apps.core.runtime.tempfile.gettempdir", return_value=tmpdir):
                with patch("apps.core.runtime.call_command") as mocked_migrate:
                    runtime.ensure_runtime_database()
                    runtime.ensure_runtime_database()
                    sentinel = Path(tmpdir) / ".vrtspace-runtime-db-ready"
                    self.assertTrue(sentinel.exists())

        self.assertEqual(mocked_migrate.call_count, 1)

    @override_settings(
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": "vrt",
                "USER": "vrt",
                "PASSWORD": "vrt",
                "HOST": "localhost",
                "PORT": "5432",
            }
        }
    )
    def test_non_sqlite_runtime_skips_migrate(self):
        with patch("apps.core.runtime.call_command") as mocked_migrate:
            runtime.ensure_runtime_database()

        mocked_migrate.assert_not_called()

    @override_settings(
        DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
    )
    def test_missing_required_table_forces_runtime_migrate(self):
        runtime._runtime_db_ready = True

        with tempfile.TemporaryDirectory() as tmpdir:
            sentinel = Path(tmpdir) / ".vrtspace-runtime-db-ready"
            sentinel.touch()

            with patch("apps.core.runtime.tempfile.gettempdir", return_value=tmpdir):
                with patch(
                    "apps.core.runtime._required_tables_present",
                    side_effect=[False, False, False, True],
                ):
                    with patch("apps.core.runtime.call_command") as mocked_migrate:
                        runtime.ensure_runtime_database(
                            required_tables=("leads_auditrequest",)
                        )

        mocked_migrate.assert_called_once_with("migrate", interactive=False, verbosity=0)
        self.assertTrue(runtime._runtime_db_ready)
