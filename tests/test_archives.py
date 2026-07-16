from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from webpentestkit.models import FindingInput, ProcedureStepInput, RetestInput
from webpentestkit.services import ProjectService


class ArchiveWorkflowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.service = ProjectService.create_project(
            self.root / "project", "ARCHIVE-TEST", "Archive Test"
        )
        self.project = self.service.root
        self.service.create_target(
            "WEB-01",
            "Portal",
            "https://portal.example.test",
        )
        self.finding = self.service.create_finding(
            FindingInput(
                target_id="WEB-01",
                title="Archived finding",
                summary="Summary for archive testing.",
                impact="Impact for archive testing.",
                remediation="Remediation for archive testing.",
            )
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_evidence_archive_and_restore_preserve_file_and_reference(self) -> None:
        source = self.root / "evidence.http"
        source.write_text(
            "GET / HTTP/1.1\nAuthorization: [REDACTED]\n\nHTTP/1.1 200 OK\n",
            encoding="utf-8",
        )
        evidence = self.service.add_evidence(
            self.finding.id,
            source,
            "Report evidence",
            evidence_type="http-exchange",
            classification="report-ready",
            use_in_finding=True,
        )
        self.service.save_procedure(
            self.finding.id,
            preconditions="Two test accounts are available.",
            steps=[
                ProcedureStepInput(
                    title="Request another user's object",
                    action="Change the object identifier and send the request.",
                    evidence_ids=(evidence.id,),
                )
            ],
        )
        self.service.create_retest(
            self.finding.id,
            RetestInput(
                tested_at="2026-07-15",
                tester="Archive Tester",
                result="Passed",
                verification_details="The server rejects the request.",
                evidence_ids=(evidence.id,),
            ),
        )
        usage = self.service.get_evidence_usage(self.finding.id, evidence.id)
        self.assertTrue(usage.finding_presentation)
        self.assertEqual(usage.procedure_step_ids, ("STEP-001",))
        self.assertEqual(usage.retest_ids, ("RT-001",))
        original = self.service.evidence_location(self.finding.id, evidence.id)
        archived = self.service.archive_evidence(
            self.finding.id, evidence.id, "No longer needed in current report"
        )
        self.assertEqual(archived.entity_type, "evidence")
        self.assertFalse(original.exists())
        self.assertEqual(self.service.list_evidence(self.finding.id), [])
        self.assertEqual(
            self.service.get_retests(self.finding.id).items[0].evidence_ids, ()
        )
        self.assertFalse(
            self.service.list_evidence_usages(self.finding.id).get(evidence.id)
        )
        self.assertEqual(self.service.list_archives()[0].reason, archived.reason)
        self.assertEqual(
            self.service.get_procedure(self.finding.id).steps[0].evidence_ids, ()
        )

        restored = self.service.restore_archive(archived.archive_id)
        self.assertEqual(restored.entity_id, evidence.id)
        restored_evidence = self.service.get_evidence(self.finding.id, evidence.id)
        self.assertTrue(self.service.evidence_location(self.finding.id, evidence.id).is_file())
        self.assertTrue(restored_evidence.is_report_ready)
        self.assertTrue(
            self.service.get_evidence_usage(self.finding.id, evidence.id).finding_presentation
        )
        self.assertEqual(
            self.service.get_procedure(self.finding.id).steps[0].evidence_ids,
            (evidence.id,),
        )
        self.assertEqual(
            self.service.get_retests(self.finding.id).items[0].evidence_ids,
            (evidence.id,),
        )
        self.assertEqual(self.service.list_archives(), [])

    def test_finding_and_target_archive_and_restore(self) -> None:
        finding_archive = self.service.archive_finding(
            self.finding.id, "Finding withdrawn for later review"
        )
        self.assertEqual(self.service.list_findings(), [])
        self.assertEqual(finding_archive.parent_id, "WEB-01")
        self.service.restore_archive(finding_archive.archive_id)
        self.assertEqual(self.service.get_finding(self.finding.id).title, "Archived finding")

    def test_permanent_delete_is_archive_only_and_restores_entry_on_failure(self) -> None:
        source = self.root / "purge.txt"
        source.write_text("redacted evidence", encoding="utf-8")
        evidence = self.service.add_evidence(
            self.finding.id,
            source,
            "Purge evidence",
            classification="internal",
        )
        archived = self.service.archive_evidence(self.finding.id, evidence.id, "Expired")

        with mock.patch("webpentestkit.archives.shutil.rmtree", side_effect=OSError("busy")):
            with self.assertRaises(Exception) as failed:
                self.service.purge_archive(archived.archive_id)
        self.assertEqual(getattr(failed.exception, "code", ""), "ARCHIVE_PURGE_FAILED")
        self.assertEqual(self.service.list_archives()[0].archive_id, archived.archive_id)

        purged = self.service.purge_archive(archived.archive_id)
        self.assertEqual(purged.entity_id, evidence.id)
        self.assertEqual(self.service.list_archives(), [])
        with self.assertRaises(Exception) as missing:
            self.service.restore_archive(archived.archive_id)
        self.assertEqual(getattr(missing.exception, "code", ""), "ARCHIVE_NOT_FOUND")

        target_archive = self.service.archive_target(
            "WEB-01", "Target temporarily removed from scope"
        )
        self.assertEqual(self.service.list_targets(), [])
        self.assertEqual(self.service.list_findings(), [])
        self.service.restore_archive(target_archive.archive_id)
        self.assertEqual(self.service.get_target("WEB-01").name, "Portal")
        self.assertEqual(self.service.get_finding(self.finding.id).title, "Archived finding")


if __name__ == "__main__":
    unittest.main()
