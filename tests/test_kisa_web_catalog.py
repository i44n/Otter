from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from webpentestkit.gui.controller import GuiController
from webpentestkit.knowledge import KnowledgeService


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "knowledge" / "kisa-web-2021-templates.json"
EXPECTED_NAMES = (
    "버퍼 오버플로우",
    "포맷스트링",
    "LDAP 인젝션",
    "운영체제 명령 실행",
    "SQL 인젝션",
    "SSI 인젝션",
    "XPath 인젝션",
    "디렉터리 인덱싱",
    "정보 누출",
    "악성 콘텐츠",
    "크로스사이트 스크립팅",
    "약한 문자열 강도",
    "불충분한 인증",
    "취약한 패스워드 복구",
    "크로스사이트 리퀘스트 변조(CSRF)",
    "세션 예측",
    "불충분한 인가",
    "불충분한 세션 만료",
    "세션 고정",
    "자동화 공격",
    "프로세스 검증 누락",
    "파일 업로드",
    "파일 다운로드",
    "관리자 페이지 노출",
    "경로 추적",
    "위치 공개",
    "데이터 평문 전송",
    "쿠키 변조",
)


class KisaWebCatalogTest(unittest.TestCase):
    def test_source_preserves_all_web_names_and_reviewed_content(self) -> None:
        values = json.loads(SOURCE.read_text(encoding="utf-8"))
        self.assertEqual(
            [item["id"] for item in values],
            [f"WEB-{index:02d}" for index in range(1, 29)],
        )
        self.assertEqual([item["name"] for item in values], list(EXPECTED_NAMES))
        self.assertTrue(all(item["title"] == item["name"] for item in values))
        self.assertTrue(all(item["defaultSeverity"] == "High" for item in values))
        self.assertTrue(all(item["cvssVector"] == "" for item in values))
        self.assertTrue(all(item["status"] == "Approved" for item in values))
        self.assertTrue(all(len(item["remediationDetail"]) >= 3 for item in values))
        self.assertTrue(all(len(item["references"]) >= 3 for item in values))
        self.assertTrue(
            all(
                any("krcert.or.kr" in reference for reference in item["references"])
                for item in values
            )
        )

    def test_database_bundle_import_and_project_application(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_database = root / "source.db"
            source = KnowledgeService.open(source_database, seed_path=SOURCE)
            templates = source.search_templates(status="Approved")
            self.assertEqual(len(templates), 28)
            self.assertEqual({template.name for template in templates}, set(EXPECTED_NAMES))

            bundle = source.export_bundle(root / "kisa-web.knowledge.json")
            destination = KnowledgeService.open(root / "destination.db")
            first = destination.import_bundle(bundle)
            second = destination.import_bundle(bundle)
            self.assertEqual(first.added_versions, 28)
            self.assertEqual(first.template_count, 28)
            self.assertEqual(second.added_versions, 0)
            self.assertEqual(second.skipped_versions, 28)

            controller = GuiController(root / "controller.db")
            imported = controller.import_knowledge(bundle)
            self.assertEqual(imported.added_versions, 28)
            self.assertEqual(
                [template.id for template in controller.search_templates("WEB-05")],
                ["WEB-05"],
            )
            controller.create_project(
                root / "project",
                "KISA-WEB-TEST",
                "KISA WEB Catalog Test",
                "Example Customer",
            )
            controller.create_target(
                "WEB-01",
                "Test Web",
                "https://example.test",
                "Test",
            )
            finding = controller.create_finding_from_template(
                "WEB-05",
                "WEB-01",
            )
            self.assertEqual(finding.title, "SQL 인젝션")
            self.assertEqual(finding.cwe, "CWE-89")
            self.assertIsNotNone(finding.template)
            self.assertEqual(finding.template.id, "WEB-05")
            self.assertEqual(finding.template.version, 1)
            self.assertIsNone(finding.cvss.score)
            self.assertEqual(finding.cvss.vector, "")


if __name__ == "__main__":
    unittest.main()
