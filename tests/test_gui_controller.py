from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from webpentestkit.gui.controller import GuiController


class GuiControllerIntegrationTest(unittest.TestCase):
    def test_complete_gui_controller_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            controller = GuiController(root / "knowledge.db")
            controller.create_project(
                root / "project",
                "GUI-TEST",
                "GUI Controller Test",
                "Example Customer",
            )
            target = controller.create_target(
                "WEB-01",
                "Portal",
                "https://portal.example.test",
                "Staging",
            )
            self.assertEqual(target.id, "WEB-01")
            templates = controller.search_templates("IDOR")
            self.assertEqual(len(templates), 1)
            finding = controller.create_finding_from_template(
                templates[0].id,
                target.id,
                version=templates[0].version,
                title="Order object authorization missing",
                status="Confirmed",
                url="https://portal.example.test/api/orders/{id}",
                method="GET",
                parameter="id",
                role="Customer",
                tester="GUI Tester",
            )
            self.assertEqual(finding.template.id, templates[0].id)
            self.assertEqual(finding.template.version, templates[0].version)
            finding = controller.update_finding(
                finding.id,
                technical_root_cause="Object ownership is not validated on the server.",
                technical_request="GET /api/orders/2 HTTP/1.1",
                technical_response="HTTP/1.1 200 OK",
                technical_analyst_notes="A second customer's order was returned.",
            )

            source = root / "response.http"
            source.write_text(
                "GET /api/orders/2 HTTP/1.1\n"
                "Authorization: [REDACTED]\n\n"
                "HTTP/1.1 200 OK\n",
                encoding="utf-8",
            )
            evidence = controller.add_evidence(
                finding.id,
                source,
                "Redacted order response",
                "http-exchange",
                "Another sample user's response.",
                True,
                False,
            )
            self.assertTrue(evidence.include_in_report)
            updated = controller.update_evidence(
                finding.id,
                evidence.id,
                caption="Updated report caption.",
            )
            self.assertEqual(updated.caption, "Updated report caption.")

            archived = controller.archive_evidence(
                finding.id, evidence.id, "Temporary GUI archive test"
            )
            self.assertEqual(len(controller.list_archives()), 1)
            controller.restore_archive(archived.archive_id)
            self.assertEqual(len(controller.list_evidence(finding.id)), 1)

            config = controller.update_report_config(
                report_title="GUI Test Report",
                assessment_from="2026-07-01",
                assessment_to="2026-07-15",
                font="Pretendard",
                theme="corporate",
            )
            self.assertEqual(config.report_title, "GUI Test Report")
            self.assertFalse([issue for issue in controller.validate() if issue["level"] != "INFO"])
            self.assertTrue(controller.build_reports().is_dir())
            export = controller.export_ppt(root / "ppt-export")
            self.assertTrue((export / "slides.json").is_file())


if __name__ == "__main__":
    unittest.main()
