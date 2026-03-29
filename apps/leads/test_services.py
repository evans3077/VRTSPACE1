from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.leads.models import AuditRequest, Lead
from apps.leads.services import _ensure_model_table


class EnsureModelTableTests(SimpleTestCase):
    @patch("apps.leads.services.connection")
    def test_skips_schema_create_when_table_exists(self, mocked_connection):
        cursor = MagicMock()
        mocked_connection.cursor.return_value.__enter__.return_value = cursor
        mocked_connection.introspection.table_names.return_value = [Lead._meta.db_table]

        _ensure_model_table(Lead)

        mocked_connection.schema_editor.assert_not_called()

    @patch("apps.leads.services.connection")
    def test_creates_model_when_table_is_missing(self, mocked_connection):
        cursor = MagicMock()
        mocked_connection.cursor.return_value.__enter__.return_value = cursor
        mocked_connection.introspection.table_names.return_value = []

        schema_editor = MagicMock()
        mocked_connection.schema_editor.return_value.__enter__.return_value = schema_editor

        _ensure_model_table(AuditRequest)

        schema_editor.create_model.assert_called_once_with(AuditRequest)
