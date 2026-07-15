from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from webpentestkit.common import KitError
from webpentestkit.core import (
    add_evidence,
    add_finding,
    add_target,
    init_project,
    set_finding_status,
    update_finding,
)
from webpentestkit.reporting import build_reports, export_ppt_bundle, validate_project


class WorkflowTest(unittest.TestCase):
    def test_complete_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = init_project(str(root / "project"), "DEMO-WEB", "데모 점검", "데모 고객")
            add_target(str(project), "WEB-01", "메인 포털", "https://portal.example.com")
            add_target(str(project), "WEB-02", "관리자", "https://admin.example.com")
            finding_folder = add_finding(str(project), "WEB-01", "SQL Injection", "Critical", "Injection")
            self.assertFalse((finding_folder / "finding.md").exists())
            finding_data = json.loads(
                (finding_folder / "finding.json").read_text(encoding="utf-8")
            )
            self.assertIn("technicalDetails", finding_data)
            self.assertTrue(finding_data["technicalDetails"]["includeInReport"])
            second_finding = add_finding(str(project), "WEB-02", "접근통제 미흡", "High", "Access Control")
            second_data_path = second_finding / "finding.json"
            second_data = json.loads(second_data_path.read_text(encoding="utf-8"))
            second_data["presentation"]["include"] = False
            second_data_path.write_text(json.dumps(second_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            update_finding(
                str(project),
                "WEB-01-001",
                cwe="CWE-89",
                cvss_score=9.8,
                summary="검색 파라미터에서 SQL Injection이 발생합니다.",
                impact="데이터베이스 정보 조회 및 변조가 가능합니다.",
                remediation="Prepared Statement를 적용해야 합니다.",
            )
            evidence = root / "evidence.txt"
            evidence.write_text("Cookie: [REDACTED]\nresult=exposed\n", encoding="utf-8")
            evidence_id, _ = add_evidence(
                str(project),
                "WEB-01-001",
                str(evidence),
                "취약 요청",
                "http-exchange",
                "비정상 응답 확인",
                True,
                False,
            )
            self.assertEqual(evidence_id, "EVD-001")
            set_finding_status(str(project), "WEB-01-001", "Confirmed")

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

    def test_sensitive_evidence_cannot_be_report_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = init_project(str(root / "project"), "DEMO-WEB", "데모 점검")
            add_target(str(project), "WEB-01", "메인", "https://example.com")
            add_finding(str(project), "WEB-01", "테스트 취약점")
            evidence = root / "secret.txt"
            evidence.write_text("Authorization: Bearer secret\n", encoding="utf-8")
            with self.assertRaises(KitError):
                add_evidence(
                    str(project),
                    "WEB-01-001",
                    str(evidence),
                    "민감 증적",
                    include_in_report=True,
                    sensitive=True,
                )

    def test_ppt_export_paginates_all_finding_evidence_without_dropping_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = init_project(str(root / "project"), "EVIDENCE-PAGING", "Evidence paging")
            add_target(str(project), "WEB-01", "Portal", "https://example.test")
            add_finding(str(project), "WEB-01", "Evidence-heavy finding")

            expected_ids = []
            for index in range(5):
                source = root / f"evidence-{index + 1}.txt"
                source.write_text(f"evidence {index + 1}\n", encoding="utf-8")
                evidence_id, _ = add_evidence(
                    str(project),
                    "WEB-01-001",
                    str(source),
                    f"Evidence {index + 1}",
                    include_in_report=True,
                )
                expected_ids.append(evidence_id)

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
