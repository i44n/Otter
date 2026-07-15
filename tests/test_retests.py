from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from webpentestkit.core import add_target, init_project
from webpentestkit.models import (
    FindingInput,
    ProcedureStepInput,
    RetestInput,
    RetestStepInput,
)
from webpentestkit.reporting import export_ppt_bundle, validate_project
from webpentestkit.services import ProjectService


class RetestServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.project = init_project(str(self.root / "project"), "RETEST-TEST", "Retest Test")
        add_target(str(self.project), "WEB-01", "Portal", "https://portal.example.test")
        self.service = ProjectService.open(self.project)
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

    def test_retests_are_numbered_snapshotted_and_update_finding_status(self) -> None:
        first = self.service.create_retest(
            self.finding.id,
            RetestInput(
                tested_at="2026-07-15",
                tester="Tester One",
                result="Failed",
                remediation_summary="Ownership validation was partially deployed.",
            ),
        )
        self.assertEqual(first.id, "RT-001")
        self.assertEqual(first.steps[0].procedure_step_id, "STEP-001")
        self.assertEqual(first.steps[0].title, "Request another account")
        self.assertEqual(self.service.get_finding(self.finding.id).status, "RetestFailed")

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
        self.assertEqual(self.service.get_finding(self.finding.id).status, "RetestPassed")
        collection = self.service.get_retests(self.finding.id)
        self.assertEqual([item.id for item in collection.items], ["RT-001", "RT-002"])
        self.assertEqual(collection.next_retest_number, 3)

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

    def test_retest_step_evidence_is_validated_and_project_validation_passes(self) -> None:
        source = self.root / "retest.txt"
        source.write_text("HTTP/1.1 403 Forbidden", encoding="utf-8")
        evidence = self.service.add_evidence(
            self.finding.id,
            source,
            "Retest denial",
            include_in_report=True,
        )
        self.service.create_retest(
            self.finding.id,
            RetestInput(
                tested_at="2026-07-15",
                tester="Tester",
                result="Passed",
                steps=(
                    RetestStepInput(
                        procedure_step_id="STEP-001",
                        title="Request another account",
                        action="Change the object identifier.",
                        result="Passed",
                        observed_result="The server returns 403.",
                        evidence_ids=(evidence.id,),
                    ),
                ),
            ),
        )
        errors = [item for item in validate_project(self.project) if item["level"] == "ERROR"]
        self.assertEqual(errors, [])
        export = export_ppt_bundle(self.project, self.root / "ppt-export")
        slides = json.loads((export / "slides.json").read_text(encoding="utf-8"))["slides"]
        retest_slides = [slide for slide in slides if slide["type"] == "finding-retest"]
        self.assertEqual(len(retest_slides), 1)
        self.assertEqual(retest_slides[0]["retestId"], "RT-001")
        self.assertEqual(retest_slides[0]["evidence"][0]["id"], evidence.id)
        finding_export = export / "findings" / self.finding.id
        self.assertTrue((finding_export / "retests.json").is_file())
        self.assertIn("RT-001 Passed", (finding_export / "retests.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
