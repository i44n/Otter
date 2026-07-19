from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from webpentestkit.common import KitError
from webpentestkit.models import EvidenceLinkInput, FindingInput, ProcedureStepInput
from webpentestkit.services import ProjectService


class ProjectServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.service = ProjectService.create_project(
            self.root / "project",
            "SERVICE-TEST",
            "Service Test",
            "Original Customer",
        )
        self.project = self.service.root
        self.service.create_target(
            "WEB-01",
            "Original Target",
            "https://old.example.test",
            "Staging",
        )

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

    def test_finding_bundle_saves_technical_link_metadata_atomically(self) -> None:
        finding = self.service.create_finding(
            FindingInput(target_id="WEB-01", title="Technical link metadata")
        )
        source = self.root / "technical.http"
        source.write_text("HTTP/1.1 403 Forbidden", encoding="utf-8")
        evidence = self.service.add_evidence(
            finding.id,
            source,
            "Forbidden response",
            evidence_type="http-response",
            classification="report-ready",
        )
        self.service.update_finding_bundle(
            finding.id,
            finding_values={},
            preconditions="",
            steps=[],
            technical_evidence_links=(
                EvidenceLinkInput(
                    evidence.id,
                    "Technical detail response.",
                    "appendix",
                ),
            ),
        )
        link = next(
            item
            for item in self.service.list_evidence_links(finding.id)
            if item.scope_type == "technical"
        )
        self.assertEqual(link.caption, "Technical detail response.")
        self.assertEqual(link.placement, "appendix")
        with self.assertRaises(KitError):
            self.service.update_finding_bundle(
                finding.id,
                finding_values={"title": "Must roll back"},
                preconditions="changed",
                steps=[],
                technical_evidence_links=(
                    EvidenceLinkInput(evidence.id, "Invalid placement", "sideways"),
                ),
            )
        restored = next(
            item
            for item in self.service.list_evidence_links(finding.id)
            if item.scope_type == "technical"
        )
        self.assertEqual(self.service.get_finding(finding.id).title, "Technical link metadata")
        self.assertEqual(restored.caption, "Technical detail response.")
        self.assertEqual(restored.placement, "appendix")

    def test_finding_bundle_saves_result_evidence_usage_and_display_order(self) -> None:
        finding = self.service.create_finding(
            FindingInput(target_id="WEB-01", title="Result evidence")
        )
        source = self.root / "result.png"
        source.write_bytes(b"result image fixture")
        evidence = self.service.add_evidence(
            finding.id,
            source,
            "Final result",
            evidence_type="screenshot",
            classification="report-ready",
        )

        self.service.update_finding_bundle(
            finding.id,
            finding_values={},
            preconditions="",
            steps=[],
            finding_evidence_links=(
                EvidenceLinkInput(
                    evidence.id,
                    "The final vulnerable response.",
                    "inline",
                    30,
                ),
            ),
        )

        link = next(
            item
            for item in self.service.list_evidence_links(finding.id)
            if item.scope_type == "finding"
        )
        self.assertEqual(link.scope_id, "")
        self.assertEqual(link.caption, "The final vulnerable response.")
        self.assertEqual(link.placement, "inline")
        self.assertEqual(link.order, 30)

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
            self.service,
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
            self.service,
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
        self.assertEqual(
            self.service.update_target("WEB-01", status="Paused").status,
            "Paused",
        )
        with self.assertRaises(KitError) as invalid_target_status:
            self.service.update_target("WEB-01", status="banana")
        self.assertEqual(invalid_target_status.exception.code, "CHOICE_INVALID")

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
                result_summary="The authorization bypass was reproduced for another customer's order.",
                template_id="WPK-ACCESS-001",
                template_version=3,
            )
        )
        self.assertEqual(finding.id, "WEB-01-001")
        self.assertEqual(finding.status, "Confirmed")
        self.assertEqual(finding.tester, "Tester One")
        self.assertEqual(finding.cvss.score, 8.1)
        self.assertEqual(finding.presentation.order, 30)
        self.assertEqual(
            finding.presentation.result_summary,
            "The authorization bypass was reproduced for another customer's order.",
        )
        self.assertIsNotNone(finding.template)
        self.assertEqual(finding.template.id, "WPK-ACCESS-001")
        self.assertEqual(finding.template.version, 3)

        updated = self.service.update_finding(
            finding.id,
            tester="Tester Two",
            cvss_score=None,
            cvss_vector="",
            template_version=4,
        )
        self.assertEqual(updated.tester, "Tester Two")
        self.assertIsNone(updated.cvss.score)
        self.assertEqual(updated.template.version, 4)

        with self.assertRaises(KitError) as mismatch:
            self.service.update_finding(
                finding.id,
                cvss_score=9.9,
                cvss_vector="CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:N",
            )
        self.assertEqual(
            mismatch.exception.code,
            "CVSS_SCORE_VECTOR_MISMATCH",
        )

        snapshot = self.service.snapshot()
        self.assertEqual(len(snapshot.targets), 1)
        self.assertEqual(len(snapshot.findings), 1)

        updated = self.service.update_finding(
            finding.id,
            technical_analysis="Service-managed analysis.",
        )
        self.assertEqual(updated.technical_details.analysis, "Service-managed analysis.")

    def test_validation_warns_about_legacy_cvss_score_vector_mismatch(self) -> None:
        finding = self.service.create_finding(
            FindingInput(
                target_id="WEB-01",
                title="Legacy CVSS mismatch",
                cvss_score=8.1,
                cvss_vector="CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:N",
            )
        )
        record = self.service.repository.get_finding(finding.id)
        value = dict(record.data)
        value["cvss"] = dict(value["cvss"])
        value["cvss"]["score"] = 9.9
        self.service.repository.save_finding(record, value)

        issues = self.service.validate()
        mismatch = [
            item
            for item in issues
            if item["code"] == "CVSS_SCORE_VECTOR_MISMATCH"
        ]
        self.assertEqual(len(mismatch), 1)
        self.assertEqual(mismatch[0]["level"], "WARNING")

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
            classification="report-ready",
            use_in_finding=True,
        )
        self.assertTrue(evidence.is_report_ready)
        self.assertTrue(evidence.file.startswith("files/"))
        self.assertTrue(self.service.get_evidence_usage(finding.id, evidence.id).finding_presentation)
        original_location = self.service.evidence_location(finding.id, evidence.id)

        moved = self.service.update_evidence(
            finding.id,
            evidence.id,
            title="Internal response",
            classification="sensitive",
            use_in_finding=False,
        )
        self.assertFalse(moved.is_report_ready)
        self.assertTrue(moved.is_sensitive)
        self.assertTrue(moved.file.startswith("files/"))
        self.assertFalse(self.service.get_evidence_usage(finding.id, evidence.id).finding_presentation)

        finding_record = next(self.project.glob("targets/*/findings/*/finding.json"))
        finding_folder = finding_record.parent
        self.assertTrue((finding_folder / "evidence" / moved.file).is_file())
        self.assertEqual(self.service.evidence_location(finding.id, evidence.id), original_location)

        report_ready = self.service.update_evidence(
            finding.id,
            evidence.id,
            classification="report-ready",
        )
        self.assertEqual(report_ready.classification, "report-ready")
        self.assertEqual(self.service.evidence_location(finding.id, evidence.id), original_location)

    def test_report_eligibility_and_finding_usage_are_independent(self) -> None:
        finding = self.service.create_finding(
            FindingInput(target_id="WEB-01", title="Reusable evidence")
        )
        source = self.root / "reusable.http"
        source.write_text("HTTP/1.1 403 Forbidden", encoding="utf-8")
        evidence = self.service.add_evidence(
            finding.id,
            source,
            "Reusable response",
            classification="report-ready",
        )
        self.assertTrue(evidence.is_report_ready)
        usage = self.service.get_evidence_usage(finding.id, evidence.id)
        self.assertFalse(usage.finding_presentation)

        self.service.update_evidence(
            finding.id, evidence.id, use_in_finding=True
        )
        self.assertTrue(
            self.service.get_evidence_usage(finding.id, evidence.id).finding_presentation
        )

    def test_report_ready_copy_can_reference_its_sensitive_original(self) -> None:
        finding = self.service.create_finding(
            FindingInput(target_id="WEB-01", title="Derived evidence")
        )
        original_path = self.root / "original.http"
        original_path.write_text("Authorization: Bearer secret", encoding="utf-8")
        original = self.service.add_evidence(
            finding.id,
            original_path,
            "Sensitive original",
            classification="sensitive",
        )
        redacted_path = self.root / "redacted.http"
        redacted_path.write_text("Authorization: [REDACTED]", encoding="utf-8")
        redacted = self.service.add_evidence(
            finding.id,
            redacted_path,
            "Report copy",
            classification="report-ready",
            derived_from=original.id,
        )
        self.assertEqual(redacted.derived_from, original.id)
        self.assertTrue(redacted.is_report_ready)
        self.assertTrue(original.is_sensitive)

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

        with self.assertRaises(KitError) as invalid_language:
            self.service.update_report_config(language="banana")
        self.assertEqual(invalid_language.exception.code, "CHOICE_INVALID")
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
