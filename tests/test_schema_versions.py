from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from webpentestkit.errors import KitError
from webpentestkit.models import FindingInput
from webpentestkit.schema_versions import CURRENT_SCHEMA_VERSION
from webpentestkit.services import ProjectService


class SchemaVersionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.service = ProjectService.create_project(
            self.root / "project", "SCHEMA-TEST", "Schema Test"
        )
        self.project = self.service.root
        self.service.create_target(
            "WEB-01", "Portal", "https://portal.example.test"
        )
        self.service.create_finding(
            FindingInput(target_id="WEB-01", title="Schema finding")
        )
        self.service.close()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_new_documents_use_the_current_schema(self) -> None:
        records = ProjectService.inspect_schema(self.project)
        self.assertTrue(records)
        self.assertTrue(
            all(record.version == CURRENT_SCHEMA_VERSION for record in records)
        )

    def test_older_schema_is_rejected_without_modification(self) -> None:
        project_path = self.project / "project.json"
        value = json.loads(project_path.read_text(encoding="utf-8"))
        value["schemaVersion"] = CURRENT_SCHEMA_VERSION - 1
        project_path.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        before = project_path.read_text(encoding="utf-8")

        with self.assertRaises(KitError) as raised:
            ProjectService.open(self.project)
        self.assertEqual(raised.exception.code, "SCHEMA_VERSION_UNSUPPORTED")
        self.assertEqual(project_path.read_text(encoding="utf-8"), before)

    def test_newer_schema_is_rejected_without_modification(self) -> None:
        project_path = self.project / "project.json"
        value = json.loads(project_path.read_text(encoding="utf-8"))
        value["schemaVersion"] = CURRENT_SCHEMA_VERSION + 1
        project_path.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        before = project_path.read_text(encoding="utf-8")

        with self.assertRaises(KitError) as raised:
            ProjectService.open(self.project)
        self.assertEqual(raised.exception.code, "SCHEMA_VERSION_NEWER")
        self.assertEqual(project_path.read_text(encoding="utf-8"), before)


if __name__ == "__main__":
    unittest.main()
