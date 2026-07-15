from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from webpentestkit.common import KitError
from webpentestkit.core import add_finding, add_target, init_project
from webpentestkit.services import ProjectService


class MigrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.project = init_project(
            str(root / "project"), "MIGRATION-TEST", "Migration Test"
        )
        add_target(
            str(self.project),
            "WEB-01",
            "Portal",
            "https://portal.example.test",
        )
        add_finding(str(self.project), "WEB-01", "Migration finding")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_v0_documents_are_backed_up_and_migrated_to_v1(self) -> None:
        project_path = self.project / "project.json"
        finding_path = next(self.project.glob("targets/*/findings/*/finding.json"))
        for path in (project_path, finding_path):
            value = json.loads(path.read_text(encoding="utf-8"))
            value.pop("schemaVersion")
            path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        with self.assertRaises(KitError) as raised:
            ProjectService.open(self.project)
        self.assertEqual(raised.exception.code, "MIGRATION_REQUIRED")

        result = ProjectService.migrate(self.project)
        self.assertEqual(len(result.changed_files), 2)
        self.assertIsNotNone(result.backup_path)
        self.assertTrue((result.backup_path / "migration-backup.json").is_file())
        self.assertTrue((result.backup_path / "files" / "project.json").is_file())
        self.assertEqual(
            json.loads(project_path.read_text(encoding="utf-8"))["schemaVersion"], 1
        )
        self.assertEqual(
            json.loads(finding_path.read_text(encoding="utf-8"))["schemaVersion"], 1
        )
        self.assertEqual(ProjectService.open(self.project).get_project().project_id, "MIGRATION-TEST")

    def test_newer_schema_is_rejected_without_modification(self) -> None:
        project_path = self.project / "project.json"
        value = json.loads(project_path.read_text(encoding="utf-8"))
        value["schemaVersion"] = 999
        project_path.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        before = project_path.read_text(encoding="utf-8")

        with self.assertRaises(KitError) as raised:
            ProjectService.open(self.project)
        self.assertEqual(raised.exception.code, "SCHEMA_VERSION_NEWER")
        with self.assertRaises(KitError) as migrate_raised:
            ProjectService.migrate(self.project)
        self.assertEqual(migrate_raised.exception.code, "SCHEMA_VERSION_NEWER")
        self.assertEqual(project_path.read_text(encoding="utf-8"), before)


if __name__ == "__main__":
    unittest.main()
