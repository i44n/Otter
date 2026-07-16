from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from webpentestkit.errors import KitError
from webpentestkit.knowledge import KnowledgeService
from webpentestkit.models import VulnerabilityTemplateInput
from webpentestkit.services import ProjectService


class KnowledgeBaseTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.database = self.root / "knowledge.db"
        self.knowledge = KnowledgeService.open(self.database)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_seed_search_and_immutable_version_history(self) -> None:
        templates = self.knowledge.search_templates()
        self.assertGreaterEqual(len(templates), 3)
        matches = self.knowledge.search_templates("IDOR")
        self.assertEqual([item.id for item in matches], ["WPK-ACCESS-001"])
        self.assertEqual(
            self.knowledge.search_templates("CWE-89")[0].id,
            "WPK-INJECTION-001",
        )

        original = self.knowledge.get_template("WPK-ACCESS-001", 1)
        updated = self.knowledge.create_next_version(
            "WPK-ACCESS-001",
            remediation="Updated remediation text for version two.",
            tags=("Authorization", "IDOR", "Reviewed"),
            status="Reviewed",
        )
        self.assertEqual(updated.version, 2)
        self.assertEqual(
            self.knowledge.get_template("WPK-ACCESS-001").remediation,
            "Updated remediation text for version two.",
        )
        historical = self.knowledge.get_template("WPK-ACCESS-001", 1)
        self.assertEqual(historical.remediation, original.remediation)
        self.assertEqual(historical.status, "Approved")
        self.assertNotIn("Reviewed", historical.tags)

    def test_template_application_copies_snapshot_into_project(self) -> None:
        project_service = ProjectService.create_project(
            self.root / "project",
            "KNOWLEDGE-TEST",
            "Knowledge Test",
            "Sensitive Customer Name",
        )
        project = project_service.root
        project_service.create_target(
            "WEB-01",
            "Portal",
            "https://portal.example.test",
        )
        template = self.knowledge.get_template("WPK-ACCESS-001", 1)
        finding = self.knowledge.create_finding_from_template(
            project_service,
            template.id,
            "WEB-01",
            version=1,
            title="Order object authorization missing",
            status="Confirmed",
            url="https://portal.example.test/api/orders/{id}",
            method="GET",
            parameter="id",
            role="Customer",
            tester="Template Tester",
        )
        self.assertEqual(finding.template.id, template.id)
        self.assertEqual(finding.template.version, 1)
        self.assertEqual(finding.presentation.impact, template.impact)
        self.assertEqual(finding.tester, "Template Tester")

        self.knowledge.create_next_version(
            template.id,
            impact="A new impact statement that must not alter old projects.",
        )
        unchanged = project_service.get_finding(finding.id)
        self.assertEqual(unchanged.template.version, 1)
        self.assertEqual(unchanged.presentation.impact, template.impact)

        connection = sqlite3.connect(self.database)
        try:
            table_names = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            columns = {
                row[1].lower()
                for table in table_names
                for row in connection.execute(f'PRAGMA table_info("{table}")')
            }
        finally:
            connection.close()
        self.assertNotIn("customer_name", columns)
        self.assertNotIn("evidence", columns)
        self.assertNotIn("affected_url", columns)
        self.assertNotIn("Sensitive Customer Name", self.database.read_bytes().decode("utf-8", errors="ignore"))

    def test_template_can_be_updated_archived_restored_and_deleted(self) -> None:
        created = self.knowledge.add_template_version(
            VulnerabilityTemplateInput(
                id="WPK-CATALOG-001",
                name="Catalog entry",
                title="Catalog entry",
                category="Other",
                summary="Original summary.",
                impact="Original impact.",
                remediation="Original remediation.",
                default_severity="Medium",
                tags=("Original",),
                status="Draft",
            )
        )

        updated = self.knowledge.update_template(
            created.id,
            remediation="Updated remediation without a duplicate version.",
            tags=("Updated",),
            status="Approved",
            reviewed_by="Security Reviewer",
            reviewed_at="2026-07-16",
        )
        self.assertEqual(updated.version, created.version)
        self.assertEqual(
            updated.remediation,
            "Updated remediation without a duplicate version.",
        )
        self.assertEqual(updated.tags, ("Updated",))
        self.assertEqual(
            len([item for item in self.knowledge.repository.list_versions() if item.id == created.id]),
            1,
        )

        archived = self.knowledge.archive_template(created.id)
        self.assertTrue(archived.archived)
        self.assertEqual(archived.status, "Approved")
        with self.assertRaises(KitError) as archived_apply:
            project_service = ProjectService.create_project(
                self.root / "archived-project", "ARCHIVED-T", "Archived Test"
            )
            project_service.create_target(
                "WEB-01", "Portal", "https://portal.example.test"
            )
            self.knowledge.create_finding_from_template(
                project_service, created.id, "WEB-01"
            )
        self.assertEqual(archived_apply.exception.code, "TEMPLATE_ARCHIVED")
        restored = self.knowledge.restore_template(created.id)
        self.assertFalse(restored.archived)
        self.assertEqual(restored.status, "Approved")

        self.knowledge.delete_template(created.id)
        with self.assertRaises(KitError) as missing:
            self.knowledge.get_template(created.id)
        self.assertEqual(missing.exception.code, "TEMPLATE_NOT_FOUND")

    def test_approved_template_requires_review_metadata(self) -> None:
        with self.assertRaises(KitError) as missing_reviewer:
            self.knowledge.add_template_version(
                VulnerabilityTemplateInput(
                    id="WPK-REVIEW-001",
                    name="Review required",
                    title="Review required",
                    category="Other",
                    summary="Summary.",
                    impact="Impact.",
                    remediation="Remediation.",
                    status="Approved",
                )
            )
        self.assertEqual(
            missing_reviewer.exception.code, "TEMPLATE_REVIEWER_REQUIRED"
        )

    def test_export_import_preserves_all_versions_and_is_idempotent(self) -> None:
        self.knowledge.create_next_version(
            "WPK-ACCESS-001",
            remediation="Version two ownership guidance.",
            status="Reviewed",
        )
        self.knowledge.add_template_version(
            VulnerabilityTemplateInput(
                id="WPK-CUSTOM-001",
                version=1,
                name="Custom authorization issue",
                title="Custom authorization issue",
                category="Access Control",
                summary="A custom summary.",
                impact="A custom impact.",
                remediation="A custom remediation.",
                default_severity="High",
                cwes=("CWE-285",),
                tags=("Custom", "Authorization"),
                status="Reviewed",
            )
        )
        bundle_path = self.root / "knowledge-export.json"
        self.assertEqual(self.knowledge.export_bundle(bundle_path), bundle_path.resolve())

        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        self.assertEqual(bundle["format"], "web-pentest-kit-knowledge")
        self.assertEqual(bundle["bundleVersion"], 1)
        exported_keys = {(item["id"], item["version"]) for item in bundle["templates"]}
        self.assertIn(("WPK-ACCESS-001", 1), exported_keys)
        self.assertIn(("WPK-ACCESS-001", 2), exported_keys)
        self.assertIn(("WPK-CUSTOM-001", 1), exported_keys)
        self.assertNotIn("customerName", bundle_path.read_text(encoding="utf-8"))

        imported = KnowledgeService.open(self.root / "imported.db")
        first = imported.import_bundle(bundle_path)
        self.assertEqual(first.added_versions, 2)
        self.assertEqual(first.skipped_versions, 3)
        self.assertEqual(first.template_count, 4)
        self.assertEqual(
            imported.get_template("WPK-ACCESS-001", 2).remediation,
            "Version two ownership guidance.",
        )
        self.assertEqual(imported.get_template("WPK-CUSTOM-001").version, 1)

        second = imported.import_bundle(bundle_path)
        self.assertEqual(second.added_versions, 0)
        self.assertEqual(second.skipped_versions, len(bundle["templates"]))

    def test_import_conflict_rolls_back_every_change(self) -> None:
        bundle_path = self.root / "conflict.json"
        self.knowledge.export_bundle(bundle_path)
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        new_item = dict(bundle["templates"][0])
        new_item.update(
            {
                "id": "WPK-CUSTOM-ROLLBACK-001",
                "version": 1,
                "name": "Rollback candidate",
                "title": "Rollback candidate",
                "summary": "Must never be committed.",
                "impact": "Must never be committed.",
                "remediation": "Must never be committed.",
            }
        )
        conflict = next(
            item
            for item in bundle["templates"]
            if item["id"] == "WPK-ACCESS-001" and item["version"] == 1
        )
        conflict["remediation"] = "Conflicting imported remediation."
        bundle["templates"] = [new_item, conflict]
        bundle_path.write_text(
            json.dumps(bundle, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        original = self.knowledge.get_template("WPK-ACCESS-001", 1).remediation
        with self.assertRaises(KitError) as raised:
            self.knowledge.import_bundle(bundle_path)
        self.assertEqual(raised.exception.code, "KNOWLEDGE_IMPORT_CONFLICT")
        self.assertEqual(
            self.knowledge.get_template("WPK-ACCESS-001", 1).remediation,
            original,
        )
        with self.assertRaises(KitError) as missing:
            self.knowledge.get_template("WPK-CUSTOM-ROLLBACK-001", 1)
        self.assertEqual(missing.exception.code, "TEMPLATE_NOT_FOUND")
        self.assertEqual(list(self.root.glob(".knowledge-import-*.db")), [])


if __name__ == "__main__":
    unittest.main()
