from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from webpentestkit.common import KitError
from webpentestkit.models import FindingInput
from webpentestkit.reporting import (
    build_reports,
    export_ppt_bundle,
    issue,
    validate_project,
    validation_markdown,
)
from webpentestkit.services import ProjectService


class WorkflowTest(unittest.TestCase):
    def test_report_language_changes_generated_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            outputs = {}
            validation_outputs = {}
            for locale in ("en-US", "ko-KR"):
                service = ProjectService.create_project(
                    root / locale,
                    f"LANG-{locale[:2].upper()}",
                    "Language Test",
                )
                service.update_report_config(language=locale)
                service.create_target(
                    "WEB-01", "Portal", "https://portal.example.test"
                )
                service.create_finding(
                    FindingInput(
                        target_id="WEB-01",
                        title="Authorization issue",
                        status="Confirmed",
                        summary="Summary",
                        impact="Impact",
                        remediation="Fix",
                    )
                )
                report_dir = service.build_reports()
                outputs[locale] = (
                    report_dir / "findings-summary.md"
                ).read_text(encoding="utf-8")
                validation_outputs[locale] = (
                    report_dir / "validation-report.md"
                ).read_text(encoding="utf-8")
                service.close()
            self.assertIn("# Findings Summary", outputs["en-US"])
            self.assertIn("# 취약점 요약", outputs["ko-KR"])
            self.assertNotEqual(outputs["en-US"], outputs["ko-KR"])
            self.assertIn("# Validation Result", validation_outputs["en-US"])
            self.assertIn("| Category | Level |", validation_outputs["en-US"])
            self.assertIn(
                "Technical details for the report are empty.",
                validation_outputs["en-US"],
            )
            self.assertIn(
                "The project is stored as plaintext.",
                validation_outputs["en-US"],
            )
            self.assertIn("# 검증 결과", validation_outputs["ko-KR"])
            self.assertIn("| 분류 | 수준 |", validation_outputs["ko-KR"])
            self.assertIn(
                "보고서용 기술 상세가 비어 있습니다.",
                validation_outputs["ko-KR"],
            )
            self.assertIn(
                "프로젝트가 평문으로 저장되어 있습니다.",
                validation_outputs["ko-KR"],
            )

    def test_validation_issues_have_categories_and_localized_report_columns(self) -> None:
        cases = (
            ("SCHEMA_VERSION_INVALID", "project-structure"),
            ("PROJECT_PLAINTEXT", "project-security"),
            ("FINDING_REQUIRED", "targets-findings"),
            ("PRESENTATION_EMPTY", "report-content"),
            ("POSSIBLE_SECRET", "evidence-security"),
            ("PROCEDURE_STEP_REQUIRED", "procedure"),
            ("RETEST_RESULT_INVALID", "retest"),
            ("UNCLASSIFIED_CHECK", "general"),
        )
        issues = [
            issue("WARNING", code, "project/path.json", code)
            for code, _category in cases
        ]
        self.assertEqual(
            [item["category"] for item in issues],
            [category for _code, category in cases],
        )
        english = validation_markdown(issues, "en-US")
        korean = validation_markdown(issues, "ko-KR")
        self.assertIn("Project structure and schema", english)
        self.assertIn("Project security", english)
        self.assertIn("Evidence and sensitive data", english)
        self.assertIn("Unredacted credentials may be present.", english)
        self.assertIn("프로젝트 구조·스키마", korean)
        self.assertIn("프로젝트 보안", korean)
        self.assertIn("증적·민감정보", korean)

    def test_complete_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            service = ProjectService.create_project(
                root / "project", "DEMO-WEB", "데모 점검", "데모 고객"
            )
            project = service.root
            service.create_target("WEB-01", "메인 포털", "https://portal.example.com")
            service.create_target("WEB-02", "관리자", "https://admin.example.com")
            finding = service.create_finding(
                FindingInput(
                    target_id="WEB-01",
                    title="SQL Injection",
                    severity="Critical",
                    category="Injection",
                )
            )
            finding_folder = service.finding_location(finding.id)
            self.assertFalse((finding_folder / "finding.md").exists())
            finding_data = json.loads(
                (finding_folder / "finding.json").read_text(encoding="utf-8")
            )
            self.assertIn("technicalDetails", finding_data)
            self.assertEqual(
                finding_data["technicalDetails"],
                {"rootCause": "", "analysis": ""},
            )
            second_finding = service.create_finding(
                FindingInput(
                    target_id="WEB-02",
                    title="접근통제 미흡",
                    severity="High",
                    category="Access Control",
                )
            )
            second_data_path = service.finding_location(second_finding.id) / "finding.json"
            second_data = json.loads(second_data_path.read_text(encoding="utf-8"))
            second_data["presentation"]["include"] = False
            second_data_path.write_text(json.dumps(second_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            service.update_finding(
                "WEB-01-001",
                cwe="CWE-89",
                cvss_score=9.8,
                summary="검색 파라미터에서 SQL Injection이 발생합니다.",
                impact="데이터베이스 정보 조회 및 변조가 가능합니다.",
                remediation="Prepared Statement를 적용해야 합니다.",
            )
            evidence = root / "evidence.txt"
            evidence.write_text("Cookie: [REDACTED]\nresult=exposed\n", encoding="utf-8")
            evidence_model = service.add_evidence(
                "WEB-01-001",
                evidence,
                "취약 요청",
                evidence_type="http-exchange",
                caption="비정상 응답 확인",
                classification="report-ready",
                use_in_finding=True,
            )
            evidence_id = evidence_model.id
            self.assertEqual(evidence_id, "EVD-001")
            service.set_scope_evidence(
                "WEB-01-001", "technical", "", (evidence_id,)
            )
            service.update_finding("WEB-01-001", status="Confirmed")

            issues = validate_project(project)
            self.assertFalse([item for item in issues if item["level"] == "ERROR"])
            report_dir = build_reports(project)
            self.assertTrue((report_dir / "findings-summary.csv").is_file())
            findings_summary = (report_dir / "findings-summary.md").read_text(encoding="utf-8")
            self.assertIn("# Findings Summary", findings_summary)
            self.assertIn("## Overall Summary", findings_summary)
            report = (report_dir / "report.md").read_text(encoding="utf-8")
            self.assertIn("#### Technical Details", report)
            self.assertIn("##### Root Cause", report)

            export = export_ppt_bundle(project, root / "ppt-export")
            slides = json.loads((export / "slides.json").read_text(encoding="utf-8"))
            finding_slides = [slide for slide in slides["slides"] if slide["type"] == "finding-detail"]
            self.assertEqual(len(finding_slides), 1)
            self.assertEqual(finding_slides[0]["findingId"], "WEB-01-001")
            self.assertEqual(finding_slides[0]["evidence"][0]["id"], "EVD-001")
            self.assertTrue((export / finding_slides[0]["evidence"][0]["file"]).is_file())
            self.assertTrue(
                (export / "findings" / "WEB-01-001" / "technical-details.md").is_file()
            )
            exported_summary = (
                export / "findings" / "WEB-01-001" / "summary.md"
            ).read_text(encoding="utf-8")
            self.assertIn("## Technical Details", exported_summary)
            self.assertIn("#### Root Cause", exported_summary)
            self.assertTrue((export / "charts" / "severity-distribution.svg").is_file())

    def test_sensitive_evidence_can_be_linked_but_is_never_exported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            service = ProjectService.create_project(
                root / "project", "DEMO-WEB", "데모 점검"
            )
            project = service.root
            service.create_target("WEB-01", "메인", "https://example.com")
            service.create_finding(
                FindingInput(target_id="WEB-01", title="테스트 취약점")
            )
            evidence = root / "secret.txt"
            evidence.write_text("Authorization: Bearer secret\n", encoding="utf-8")
            model = service.add_evidence(
                "WEB-01-001",
                evidence,
                "민감 증적",
                classification="sensitive",
                use_in_finding=True,
            )
            self.assertTrue(model.is_sensitive)
            codes = {item["code"] for item in service.validate()}
            self.assertIn("EVIDENCE_LINK_INTERNAL", codes)
            export = service.export_ppt(root / "sensitive-export")
            slides = json.loads((export / "slides.json").read_text(encoding="utf-8"))["slides"]
            finding_slide = next(slide for slide in slides if slide["type"] == "finding-detail")
            self.assertEqual(finding_slide["evidence"], [])

    def test_ppt_export_paginates_all_finding_evidence_without_dropping_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            service = ProjectService.create_project(
                root / "project", "EVIDENCE-PAGING", "Evidence paging"
            )
            project = service.root
            service.create_target("WEB-01", "Portal", "https://example.test")
            service.create_finding(
                FindingInput(target_id="WEB-01", title="Evidence-heavy finding")
            )

            expected_ids = []
            for index in range(5):
                source = root / f"evidence-{index + 1}.txt"
                source.write_text(f"evidence {index + 1}\n", encoding="utf-8")
                evidence_model = service.add_evidence(
                    "WEB-01-001",
                    source,
                    f"Evidence {index + 1}",
                    classification="report-ready",
                    use_in_finding=True,
                )
                expected_ids.append(evidence_model.id)

            export = export_ppt_bundle(project, root / "ppt-export")
            slides = json.loads((export / "slides.json").read_text(encoding="utf-8"))["slides"]
            evidence_slides = [
                slide
                for slide in slides
                if slide["type"] in {"finding-detail", "finding-evidence"}
                and slide.get("findingId") == "WEB-01-001"
            ]
            self.assertEqual([len(slide["evidence"]) for slide in evidence_slides], [2, 2, 1])
            self.assertEqual(
                [item["id"] for slide in evidence_slides for item in slide["evidence"]],
                expected_ids,
            )
            self.assertEqual([slide["page"] for slide in evidence_slides[1:]], [2, 3])
            exported_files = list((export / "findings" / "WEB-01-001" / "evidence").iterdir())
            self.assertEqual(len(exported_files), 5)


if __name__ == "__main__":
    unittest.main()
