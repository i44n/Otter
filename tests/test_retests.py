from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from webpentestkit.errors import KitError
from webpentestkit.models import (
    FindingInput,
    ProcedureStepInput,
    RetestInput,
)
from webpentestkit.reporting import export_ppt_bundle, validate_project
from webpentestkit.services import ProjectService


class RetestServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.service = ProjectService.create_project(
            self.root / "project", "RETEST-TEST", "Retest Test"
        )
        self.project = self.service.root
        self.service.create_target("WEB-01", "Portal", "https://portal.example.test")
        self.finding = self.service.create_finding(
            FindingInput(target_id="WEB-01", title="Retestable finding")
        )
        self.service.save_procedure(
            self.finding.id,
            preconditions="Two accounts exist.",
            steps=[
                ProcedureStepInput(
                    title="Request another account",
                    action="Change the object identifier.",
                )
            ],
        )

    def tearDown(self) -> None:
        self.service.close()
        self.temporary.cleanup()

    def test_retests_are_numbered_without_overwriting_workflow_status(self) -> None:
        first = self.service.create_retest(
            self.finding.id,
            RetestInput(
                tested_at="2026-07-15",
                tester="Tester One",
                result="Failed",
                remediation_summary="Ownership validation was partially deployed.",
                verification_details="The original IDOR remains reproducible.",
            ),
        )
        self.assertEqual(first.id, "RT-001")
        self.assertEqual(first.verification_details, "The original IDOR remains reproducible.")
        self.assertEqual(self.service.get_finding(self.finding.id).status, "Draft")

        second = self.service.create_retest(
            self.finding.id,
            RetestInput(
                tested_at="2026-07-16",
                tester="Tester Two",
                result="Passed",
                remediation_summary="Ownership validation is enforced everywhere.",
            ),
        )
        self.assertEqual(second.id, "RT-002")
        self.assertEqual(self.service.get_finding(self.finding.id).status, "Draft")
        collection = self.service.get_retests(self.finding.id)
        self.assertEqual([item.id for item in collection.items], ["RT-001", "RT-002"])
        self.assertEqual(collection.next_retest_number, 3)
        self.assertEqual(collection.latest_result, "Passed")

    def test_retest_update_preserves_id_and_created_at(self) -> None:
        created = self.service.create_retest(
            self.finding.id,
            RetestInput(
                tested_at="2026-07-15",
                tester="Tester",
                result="Pending",
            ),
        )
        updated = self.service.update_retest(
            self.finding.id,
            created.id,
            RetestInput(
                tested_at="2026-07-16",
                tester="Tester",
                result="Passed",
                notes="Verified after deployment.",
            ),
        )
        self.assertEqual(updated.id, created.id)
        self.assertEqual(updated.created_at, created.created_at)
        self.assertEqual(updated.notes, "Verified after deployment.")

    def test_retest_evidence_is_validated_and_project_validation_passes(self) -> None:
        source = self.root / "retest.txt"
        source.write_text("HTTP/1.1 403 Forbidden", encoding="utf-8")
        evidence = self.service.add_evidence(
            self.finding.id,
            source,
            "Retest denial",
            classification="report-ready",
        )
        with self.assertRaises(KitError) as raised:
            self.service.create_retest(
                self.finding.id,
                RetestInput(
                    tested_at="2026-07-15",
                    tester="Tester",
                    result="Passed",
                    evidence_ids=("EVD-999",),
                ),
            )
        self.assertEqual(raised.exception.code, "RETEST_EVIDENCE_UNKNOWN")
        self.service.create_retest(
            self.finding.id,
            RetestInput(
                tested_at="2026-07-15",
                tester="Tester",
                result="Passed",
                verification_details="The server returns 403.",
                evidence_ids=(evidence.id,),
            ),
        )
        errors = [item for item in validate_project(self.project) if item["level"] == "ERROR"]
        self.assertEqual(errors, [])
        export = export_ppt_bundle(self.project, self.root / "ppt-export")
        slides = json.loads((export / "slides.json").read_text(encoding="utf-8"))["slides"]
        retest_slides = [slide for slide in slides if slide["type"] == "finding-retest"]
        self.assertEqual(len(retest_slides), 1)
        self.assertEqual(retest_slides[0]["retestId"], "RT-001")
        self.assertEqual(retest_slides[0]["verificationDetails"], "The server returns 403.")
        self.assertEqual(retest_slides[0]["evidence"][0]["id"], evidence.id)
        finding_export = export / "findings" / self.finding.id
        self.assertTrue((finding_export / "retests.json").is_file())
        self.assertIn("RT-001 Passed", (finding_export / "retests.md").read_text(encoding="utf-8"))

    def test_internal_retest_evidence_is_linked_but_not_exported(self) -> None:
        source = self.root / "internal-retest.txt"
        source.write_text("internal diagnostic log", encoding="utf-8")
        evidence = self.service.add_evidence(
            self.finding.id,
            source,
            "Internal retest log",
            classification="internal",
        )
        value = RetestInput(
            tested_at="2026-07-15",
            tester="Tester",
            result="Partial",
            evidence_ids=(evidence.id,),
        )
        internal = self.service.create_retest(
            self.finding.id,
            value,
        )
        self.assertEqual(internal.evidence_ids, (evidence.id,))
        codes = {item["code"] for item in validate_project(self.project)}
        self.assertIn("EVIDENCE_LINK_INTERNAL", codes)
        export = export_ppt_bundle(self.project, self.root / "internal-ppt-export")
        slides = json.loads((export / "slides.json").read_text(encoding="utf-8"))["slides"]
        retest_slide = next(slide for slide in slides if slide["type"] == "finding-retest")
        self.assertEqual(retest_slide["evidence"], [])


if __name__ == "__main__":
    unittest.main()
