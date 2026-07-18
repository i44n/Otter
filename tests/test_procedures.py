from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from webpentestkit.common import KitError
from webpentestkit.models import FindingInput, ProcedureStepInput
from webpentestkit.reporting import validate_project
from webpentestkit.reporting import export_ppt_bundle
from webpentestkit.services import ProjectService


class ProcedureServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.service = ProjectService.create_project(
            self.root / "project",
            "PROCEDURE-TEST",
            "Procedure Test",
        )
        self.project = self.service.root
        self.service.create_target(
            "WEB-01",
            "Portal",
            "https://portal.example.test",
        )
        self.finding = self.service.create_finding(
            FindingInput(target_id="WEB-01", title="Structured reproduction")
        )

    def tearDown(self) -> None:
        self.service.close()
        self.temporary.cleanup()

    def _procedure_path(self) -> Path:
        return next(self.project.glob("targets/*/findings/*/procedure.json"))

    def test_new_finding_creates_and_saves_structured_procedure(self) -> None:
        path = self._procedure_path()
        self.assertTrue(path.is_file())
        empty = self.service.get_procedure(self.finding.id)
        self.assertEqual(empty.finding_id, self.finding.id)
        self.assertEqual(empty.steps, ())

        image = self.root / "step.png"
        image.write_bytes(b"step-image")
        evidence = self.service.add_evidence(
            self.finding.id,
            image,
            "Step result",
            evidence_type="screenshot",
            classification="report-ready",
        )
        saved = self.service.save_procedure(
            self.finding.id,
            preconditions="Two test accounts are available.",
            steps=[
                ProcedureStepInput(
                    title="Sign in",
                    action="Sign in as account A.",
                    expected_result="Only account A data is available.",
                ),
                ProcedureStepInput(
                    title="Change object ID",
                    action="Request account B's object ID.",
                    observed_result="Account B data is returned.",
                    evidence_ids=(evidence.id,),
                ),
            ],
        )
        self.assertEqual([step.id for step in saved.steps], ["STEP-001", "STEP-002"])
        self.assertEqual([step.order for step in saved.steps], [10, 20])
        self.assertEqual(saved.steps[1].evidence_ids, (evidence.id,))
        self.assertEqual(self.service.get_procedure(self.finding.id), saved)

        revised = self.service.save_procedure(
            self.finding.id,
            preconditions=saved.preconditions,
            steps=[
                ProcedureStepInput(
                    id=saved.steps[1].id,
                    order=10,
                    title=saved.steps[1].title,
                    action=saved.steps[1].action,
                    observed_result=saved.steps[1].observed_result,
                    evidence_ids=saved.steps[1].evidence_ids,
                ),
                ProcedureStepInput(
                    title="Confirm disclosure",
                    action="Compare the returned customer identifier.",
                ),
            ],
        )
        self.assertEqual([step.id for step in revised.steps], ["STEP-002", "STEP-003"])
        self.assertEqual(revised.next_step_number, 4)

    def test_missing_procedure_returns_structured_error(self) -> None:
        path = self._procedure_path()
        path.unlink()
        self.service.close()
        self.service = ProjectService.open(self.project)
        with self.assertRaises(KitError) as raised:
            self.service.get_procedure(self.finding.id)
        self.assertEqual(raised.exception.code, "PROCEDURE_NOT_FOUND")
        issues = validate_project(self.project)
        self.assertIn("PROCEDURE_FILE_MISSING", {item["code"] for item in issues})

    def test_corrupt_next_step_number_returns_structured_error(self) -> None:
        path = self._procedure_path()
        value = json.loads(path.read_text(encoding="utf-8"))
        value["nextStepNumber"] = "not-a-number"
        path.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        with self.assertRaises(KitError) as raised:
            self.service.get_procedure(self.finding.id)
        self.assertEqual(raised.exception.code, "PROCEDURE_INVALID")
        with self.assertRaises(KitError) as save_raised:
            self.service.save_procedure(
                self.finding.id,
                preconditions="",
                steps=[],
            )
        self.assertEqual(save_raised.exception.code, "PROCEDURE_NEXT_STEP_INVALID")

    def test_unknown_evidence_and_duplicate_step_ids_are_rejected(self) -> None:
        with self.assertRaises(KitError) as unknown:
            self.service.save_procedure(
                self.finding.id,
                preconditions="",
                steps=[
                    ProcedureStepInput(
                        title="Unknown evidence",
                        action="Attach a missing file.",
                        evidence_ids=("EVD-999",),
                    )
                ],
            )
        self.assertEqual(unknown.exception.code, "PROCEDURE_EVIDENCE_UNKNOWN")

        duplicate = ProcedureStepInput(
            id="STEP-001",
            title="Duplicate",
            action="Duplicate ID.",
        )
        with self.assertRaises(KitError) as raised:
            self.service.save_procedure(
                self.finding.id,
                preconditions="",
                steps=[duplicate, duplicate],
            )
        self.assertEqual(raised.exception.code, "PROCEDURE_STEP_DUPLICATE")

    def test_validation_marks_internal_links_and_rejects_unknown_link_targets(self) -> None:
        source = self.root / "raw.txt"
        source.write_text("response body", encoding="utf-8")
        evidence = self.service.add_evidence(
            self.finding.id,
            source,
            "Raw evidence",
            classification="internal",
        )
        step = ProcedureStepInput(
            title="Inspect response",
            action="Send the request and inspect the response.",
            evidence_ids=(evidence.id,),
        )
        self.service.save_procedure(
            self.finding.id,
            preconditions="",
            steps=[step],
        )
        codes = {item["code"] for item in validate_project(self.project)}
        self.assertIn("EVIDENCE_LINK_INTERNAL", codes)

        path = self.service.finding_location(self.finding.id) / "evidence" / "links.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["items"][0]["evidenceId"] = "EVD-999"
        path.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        codes = {item["code"] for item in validate_project(self.project)}
        self.assertIn("EVIDENCE_LINK_UNKNOWN", codes)

    def test_validation_allows_optional_and_multiple_procedure_evidence(self) -> None:
        self.service.save_procedure(
            self.finding.id,
            preconditions="",
            steps=[ProcedureStepInput(title="No image", action="Inspect the response.")],
        )
        codes = {item["code"] for item in validate_project(self.project)}
        self.assertNotIn("PROCEDURE_STEP_EVIDENCE_COUNT", codes)

        text_source = self.root / "step.txt"
        text_source.write_text("response", encoding="utf-8")
        text_evidence = self.service.add_evidence(
            self.finding.id,
            text_source,
            "Text evidence",
            classification="internal",
        )
        self.service.save_procedure(
            self.finding.id,
            preconditions="",
            steps=[
                ProcedureStepInput(
                    title="Text evidence",
                    action="Inspect the response.",
                    evidence_ids=(text_evidence.id,),
                )
            ],
        )
        codes = {item["code"] for item in validate_project(self.project)}
        self.assertNotIn("PROCEDURE_STEP_EVIDENCE_IMAGE", codes)
        self.assertNotIn("PROCEDURE_STEP_EVIDENCE_REPORT_READY", codes)
        self.assertIn("EVIDENCE_LINK_INTERNAL", codes)

        first_source = self.root / "first.png"
        second_source = self.root / "second.png"
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8 + (1600).to_bytes(4, "big") + (900).to_bytes(4, "big")
        first_source.write_bytes(png)
        second_source.write_bytes(png)
        first = self.service.add_evidence(
            self.finding.id,
            first_source,
            "First screenshot",
            evidence_type="screenshot",
            classification="report-ready",
        )
        second = self.service.add_evidence(
            self.finding.id,
            second_source,
            "Second screenshot",
            evidence_type="screenshot",
            classification="report-ready",
        )
        self.service.save_procedure(
            self.finding.id,
            preconditions="",
            steps=[
                ProcedureStepInput(
                    title="Two images",
                    action="Inspect both images.",
                    evidence_ids=(first.id, second.id),
                )
            ],
        )
        codes = {item["code"] for item in validate_project(self.project)}
        self.assertNotIn("PROCEDURE_STEP_EVIDENCE_COUNT", codes)

        self.assertNotIn("PROCEDURE_STEP_EVIDENCE_IMAGE", codes)
        self.assertNotIn("PROCEDURE_STEP_EVIDENCE_REPORT_READY", codes)

    def test_export_includes_structured_procedure_slides_and_deduplicated_evidence(self) -> None:
        source = self.root / "step.png"
        source.write_bytes(
            b"\x89PNG\r\n\x1a\n" + b"\x00" * 8 + (1200).to_bytes(4, "big") + (800).to_bytes(4, "big")
        )
        evidence = self.service.add_evidence(
            self.finding.id,
            source,
            "Observed disclosure",
            evidence_type="screenshot",
            classification="report-ready",
        )
        self.service.save_procedure(
            self.finding.id,
            preconditions="Two accounts exist.",
            steps=[
                ProcedureStepInput(
                    title="Change the order ID",
                    action="Replace the order ID with another user's ID.",
                    expected_result="The request is rejected.",
                    observed_result="The other order is returned.",
                    evidence_ids=(evidence.id,),
                ),
                ProcedureStepInput(
                    title="Confirm the owner",
                    action="Compare the customer identifiers.",
                    evidence_ids=(evidence.id,),
                ),
            ],
        )
        export = export_ppt_bundle(self.project, self.root / "ppt-export")
        slides = json.loads((export / "slides.json").read_text(encoding="utf-8"))["slides"]
        procedure_slides = [slide for slide in slides if slide["type"] == "finding-procedure"]
        self.assertEqual([slide["stepId"] for slide in procedure_slides], ["STEP-001", "STEP-002"])
        self.assertEqual(procedure_slides[0]["evidence"][0]["id"], evidence.id)
        self.assertEqual(
            procedure_slides[0]["evidence"][0]["file"],
            procedure_slides[1]["evidence"][0]["file"],
        )
        exported_files = list((export / "findings" / self.finding.id / "evidence").iterdir())
        self.assertEqual(len(exported_files), 1)
        summary = (export / "findings" / self.finding.id / "summary.md").read_text(encoding="utf-8")
        self.assertIn("## Reproduction Procedure", summary)
        self.assertIn("### Step 1. Change the order ID", summary)
        self.assertTrue((export / "findings" / self.finding.id / "procedure.json").is_file())

    def test_link_caption_and_placement_control_both_report_outputs(self) -> None:
        source = self.root / "appendix.png"
        source.write_bytes(b"appendix-image")
        evidence = self.service.add_evidence(
            self.finding.id,
            source,
            "Appendix response",
            evidence_type="screenshot",
            classification="report-ready",
        )
        procedure = self.service.save_procedure(
            self.finding.id,
            preconditions="",
            steps=[
                ProcedureStepInput(
                    title="Verify denial",
                    action="Send the request.",
                    evidence_ids=(evidence.id,),
                )
            ],
        )
        self.service.update_evidence(
            self.finding.id,
            evidence.id,
            link_updates=[
                {
                    "scope_type": "procedure",
                    "scope_id": procedure.steps[0].id,
                    "caption": "Authorization failure captured after remediation.",
                    "placement": "appendix",
                }
            ],
        )
        report = self.service.build_reports() / "report.md"
        text = report.read_text(encoding="utf-8")
        self.assertIn("#### Evidence Appendix", text)
        self.assertIn("Authorization failure captured after remediation.", text)
        export = self.service.export_ppt(self.root / "appendix-export")
        slides = json.loads((export / "slides.json").read_text(encoding="utf-8"))["slides"]
        procedure_slide = next(slide for slide in slides if slide["type"] == "finding-procedure")
        self.assertEqual(procedure_slide["evidence"], [])
        appendix_slide = next(
            slide
            for slide in slides
            if slide["type"] == "finding-evidence" and slide.get("section") == "appendix"
        )
        self.assertEqual(appendix_slide["evidence"][0]["id"], evidence.id)

    def test_export_includes_evidence_linked_to_procedure_steps(self) -> None:
        evidence_ids = []
        for index in range(5):
            source = self.root / f"step-{index + 1}.png"
            source.write_bytes(f"step image {index + 1}".encode("utf-8"))
            evidence = self.service.add_evidence(
                self.finding.id,
                source,
                f"Step evidence {index + 1}",
                evidence_type="screenshot",
                classification="report-ready",
            )
            evidence_ids.append(evidence.id)
        self.service.save_procedure(
            self.finding.id,
            preconditions="",
            steps=[
                ProcedureStepInput(
                    title=f"Collect step {index + 1} evidence",
                    action=f"Run reproduction step {index + 1} and capture its result.",
                    evidence_ids=(evidence_id,),
                )
                for index, evidence_id in enumerate(evidence_ids)
            ],
        )

        export = export_ppt_bundle(self.project, self.root / "ppt-export-paginated")
        slides = json.loads((export / "slides.json").read_text(encoding="utf-8"))["slides"]
        step_slides = [
            slide
            for slide in slides
            if slide["type"] == "finding-procedure"
        ]
        self.assertEqual([slide["stepId"] for slide in step_slides], [f"STEP-{index:03d}" for index in range(1, 6)])
        self.assertEqual([len(slide["evidence"]) for slide in step_slides], [1, 1, 1, 1, 1])
        self.assertEqual(
            [item["id"] for slide in step_slides for item in slide["evidence"]],
            evidence_ids,
        )


if __name__ == "__main__":
    unittest.main()
