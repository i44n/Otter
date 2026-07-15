from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from webpentestkit.common import KitError
from webpentestkit.core import add_target, init_project
from webpentestkit.models import FindingInput, ProcedureStepInput
from webpentestkit.services import ProjectService


class ProjectServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.project = init_project(
            str(self.root / "project"),
            "SERVICE-TEST",
            "Service Test",
            "Original Customer",
        )
        add_target(
            str(self.project),
            "WEB-01",
            "Original Target",
            "https://old.example.test",
            "Staging",
        )
        self.service = ProjectService.open(self.project)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_finding_bundle_saves_structured_finding_and_procedure(self) -> None:
        finding = self.service.create_finding(
            FindingInput(target_id="WEB-01", title="Bundled finding")
        )
        updated, procedure = self.service.update_finding_bundle(
            finding.id,
            finding_values={
                "title": "Bundled finding updated",
                "summary": "Saved together.",
                "technical_root_cause": "The object query omits the authenticated owner constraint.",
            },
            preconditions="Two accounts are available.",
            steps=[
                ProcedureStepInput(
                    title="Request another object",
                    action="Change the object identifier and send the request.",
                )
            ],
        )
        self.assertEqual(updated.title, "Bundled finding updated")
        self.assertEqual(procedure.preconditions, "Two accounts are available.")
        self.assertEqual(procedure.steps[0].id, "STEP-001")
        self.assertIn("authenticated owner constraint", updated.technical_details.root_cause)

    def test_finding_bundle_rolls_back_every_document_on_failure(self) -> None:
        finding = self.service.create_finding(
            FindingInput(target_id="WEB-01", title="Rollback finding")
        )
        self.service.save_procedure(
            finding.id,
            preconditions="Original precondition.",
            steps=[ProcedureStepInput(title="Original", action="Original action.")],
        )
        old_finding = self.service.get_finding(finding.id)
        old_procedure = self.service.get_procedure(finding.id)
        with mock.patch.object(
            self.service.repository,
            "save_procedure",
            side_effect=OSError("simulated procedure write failure"),
        ):
            with self.assertRaises(OSError):
                self.service.update_finding_bundle(
                    finding.id,
                    finding_values={
                        "title": "Must roll back",
                        "technical_root_cause": "Must also roll back",
                    },
                    preconditions="Changed.",
                    steps=[ProcedureStepInput(title="Changed", action="Changed action.")],
                )

        self.assertEqual(self.service.get_finding(finding.id), old_finding)
        self.assertEqual(self.service.get_procedure(finding.id), old_procedure)

    def test_create_finding_bundle_removes_partial_finding_on_failure(self) -> None:
        before_ids = [item.id for item in self.service.list_findings()]
        with mock.patch.object(
            self.service.repository,
            "save_procedure",
            side_effect=OSError("simulated procedure write failure"),
        ):
            with self.assertRaises(OSError):
                self.service.create_finding_bundle(
                    FindingInput(target_id="WEB-01", title="Partial finding"),
                    preconditions="",
                    steps=[],
                )
        self.assertEqual([item.id for item in self.service.list_findings()], before_ids)

    def test_project_target_and_complete_finding_management(self) -> None:
        project = self.service.update_project(
            name="Managed Assessment",
            customer_name="Example Customer",
        )
        self.assertEqual(project.name, "Managed Assessment")
        self.assertEqual(project.customer_name, "Example Customer")
        self.assertTrue(project.updated_at)

        target = self.service.update_target(
            "WEB-01",
            name="Customer Portal",
            base_url="https://portal.example.test",
            environment="Production",
            status="Testing",
        )
        self.assertEqual(target.name, "Customer Portal")
        self.assertEqual(target.base_url, "https://portal.example.test")
        self.assertTrue(target.updated_at)

        finding = self.service.create_finding(
            FindingInput(
                target_id="WEB-01",
                title="Order object authorization missing",
                severity="High",
                status="Confirmed",
                category="Access Control",
                cwe="CWE-639",
                cvss_score=8.1,
                cvss_vector="CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:N",
                url="https://portal.example.test/api/orders/{id}",
                method="GET",
                parameter="id",
                role="Customer",
                tester="Tester One",
                discovered_at="2026-07-15",
                summary="Another customer's order can be retrieved by changing its ID.",
                impact="Order and delivery data can be disclosed.",
                remediation="Authorize every order request against the signed-in customer.",
                order=30,
                template_id="WPK-ACCESS-001",
                template_version=3,
            )
        )
        self.assertEqual(finding.id, "WEB-01-001")
        self.assertEqual(finding.status, "Confirmed")
        self.assertEqual(finding.tester, "Tester One")
        self.assertEqual(finding.cvss.score, 8.1)
        self.assertEqual(finding.presentation.order, 30)
        self.assertIsNotNone(finding.template)
        self.assertEqual(finding.template.id, "WPK-ACCESS-001")
        self.assertEqual(finding.template.version, 3)

        updated = self.service.update_finding(
            finding.id,
            tester="Tester Two",
            cvss_score=None,
            template_version=4,
        )
        self.assertEqual(updated.tester, "Tester Two")
        self.assertIsNone(updated.cvss.score)
        self.assertEqual(updated.template.version, 4)

        snapshot = self.service.snapshot()
        self.assertEqual(len(snapshot.targets), 1)
        self.assertEqual(len(snapshot.findings), 1)

        updated = self.service.update_finding(
            finding.id,
            technical_analyst_notes="Service-managed note.",
        )
        self.assertEqual(updated.technical_details.analyst_notes, "Service-managed note.")

    def test_evidence_move_updates_manifest_and_finding_reference(self) -> None:
        finding = self.service.create_finding(
            FindingInput(
                target_id="WEB-01",
                title="Sample finding",
                severity="Medium",
                status="Confirmed",
                summary="A complete summary.",
                impact="A complete impact statement.",
                remediation="A complete remediation statement.",
            )
        )
        source = self.root / "response.http"
        source.write_text(
            "GET / HTTP/1.1\nAuthorization: [REDACTED]\n\nHTTP/1.1 200 OK\n",
            encoding="utf-8",
        )
        evidence = self.service.add_evidence(
            finding.id,
            source,
            "Redacted response",
            evidence_type="http-exchange",
            include_in_report=True,
        )
        self.assertTrue(evidence.include_in_report)
        self.assertTrue(evidence.file.startswith("report/"))
        self.assertIn(evidence.id, self.service.get_finding(finding.id).presentation.evidence)

        moved = self.service.update_evidence(
            finding.id,
            evidence.id,
            title="Internal response",
            include_in_report=False,
            sensitive=True,
        )
        self.assertFalse(moved.include_in_report)
        self.assertTrue(moved.contains_sensitive_data)
        self.assertTrue(moved.file.startswith("raw/"))
        self.assertNotIn(evidence.id, self.service.get_finding(finding.id).presentation.evidence)

        finding_record = next(self.project.glob("targets/*/findings/*/finding.json"))
        finding_folder = finding_record.parent
        self.assertTrue((finding_folder / "evidence" / moved.file).is_file())
        self.assertFalse((finding_folder / "evidence" / evidence.file).exists())

        with self.assertRaises(KitError) as raised:
            self.service.update_evidence(
                finding.id,
                evidence.id,
                include_in_report=True,
            )
        self.assertEqual(raised.exception.code, "SENSITIVE_REPORT_EVIDENCE")
        self.assertEqual(raised.exception.field, "include_in_report")

    def test_evidence_file_replacement_preserves_id_and_rolls_back(self) -> None:
        finding = self.service.create_finding(
            FindingInput(target_id="WEB-01", title="Replace evidence")
        )
        original = self.root / "original.txt"
        original.write_text("original evidence", encoding="utf-8")
        evidence = self.service.add_evidence(
            finding.id,
            original,
            "Original evidence",
            evidence_type="log",
        )
        old_location = self.service.evidence_location(finding.id, evidence.id)

        replacement = self.root / "replacement.png"
        replacement.write_bytes(b"replacement-image")
        updated = self.service.update_evidence(
            finding.id,
            evidence.id,
            replacement_file=replacement,
            evidence_type="screenshot",
        )
        new_location = self.service.evidence_location(finding.id, evidence.id)
        self.assertEqual(updated.id, evidence.id)
        self.assertEqual(new_location.read_bytes(), b"replacement-image")
        self.assertFalse(old_location.exists())

        failed_replacement = self.root / "failed.png"
        failed_replacement.write_bytes(b"must-not-commit")
        before = new_location.read_bytes()
        original_write = self.service.repository.write_json_records
        calls = 0

        def fail_once(records):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise OSError("simulated manifest failure")
            return original_write(records)

        with mock.patch.object(
            self.service.repository,
            "write_json_records",
            side_effect=fail_once,
        ):
            with self.assertRaises(OSError):
                self.service.update_evidence(
                    finding.id,
                    evidence.id,
                    replacement_file=failed_replacement,
                )
        self.assertEqual(self.service.evidence_location(finding.id, evidence.id), new_location)
        self.assertEqual(new_location.read_bytes(), before)

    def test_structured_field_error_does_not_modify_target(self) -> None:
        before = self.service.get_target("WEB-01")
        with self.assertRaises(KitError) as raised:
            self.service.update_target("WEB-01", base_url="not-a-url")
        self.assertEqual(raised.exception.code, "URL_INVALID")
        self.assertEqual(raised.exception.field, "base_url")
        self.assertEqual(raised.exception.to_dict()["details"]["value"], "not-a-url")
        self.assertEqual(self.service.get_target("WEB-01"), before)

    def test_unknown_json_properties_survive_service_update(self) -> None:
        finding = self.service.create_finding(
            FindingInput(target_id="WEB-01", title="Forward-compatible finding")
        )
        path = next(self.project.glob("targets/*/findings/*/finding.json"))
        value = json.loads(path.read_text(encoding="utf-8"))
        value["futureExtension"] = {"enabled": True}
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        self.service.update_finding(finding.id, tester="Compatibility Tester")
        updated = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(updated["futureExtension"], {"enabled": True})

    def test_report_configuration_and_next_target_id(self) -> None:
        self.assertEqual(self.service.next_target_id(), "WEB-02")
        config = self.service.update_report_config(
            report_title="Customer Web Assessment",
            customer_name="Example Customer",
            classification="Confidential",
            assessment_from="2026-07-01",
            assessment_to="2026-07-15",
            language="ko-KR",
            font="Pretendard",
            theme="corporate",
            include_informational=True,
        )
        self.assertEqual(config.report_title, "Customer Web Assessment")
        self.assertEqual(config.assessment_from, "2026-07-01")
        self.assertTrue(config.include_informational)
        self.assertEqual(self.service.get_report_config(), config)

        with self.assertRaises(KitError) as raised:
            self.service.update_report_config(
                assessment_from="2026-07-20",
                assessment_to="2026-07-10",
            )
        self.assertEqual(raised.exception.code, "ASSESSMENT_PERIOD_INVALID")
        self.assertEqual(self.service.get_report_config(), config)

        old_project = self.service.get_project()
        with self.assertRaises(KitError):
            self.service.update_project_settings(
                project_values={"name": "Must Roll Back"},
                report_values={
                    "assessment_from": "2026-07-20",
                    "assessment_to": "2026-07-10",
                },
            )
        self.assertEqual(self.service.get_project(), old_project)
        self.assertEqual(self.service.get_report_config(), config)


if __name__ == "__main__":
    unittest.main()
