from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings, Qt  # noqa: E402
from PySide6.QtGui import QFontMetrics  # noqa: E402
from PySide6.QtWidgets import QDialog, QMessageBox  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from webpentestkit.gui.controller import GuiController  # noqa: E402
from webpentestkit.models import CredentialInput, FindingInput, ProcedureStepInput  # noqa: E402
from webpentestkit.qt_gui import MainWindow, create_application  # noqa: E402
from webpentestkit.qt_gui.dialogs import (  # noqa: E402
    EvidenceEditorDialog,
    FindingEditorDialog,
    RetestEditorDialog,
    TemplateApplyDialog,
    TemplateEditorDialog,
)
from webpentestkit.qt_gui.pages import FindingsPage, KnowledgePage  # noqa: E402


class QtGuiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        settings = QSettings("Otter", "Otter")
        settings.remove("appearance/darkMode")
        settings.sync()
        cls.app = create_application([])

    def setUp(self) -> None:
        self.settings = QSettings()
        self.settings.remove("appearance/darkMode")
        self.settings.remove("layout/findingsSplitter")
        self.settings.sync()
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.controller = GuiController(root / "knowledge.db")
        self.controller.create_project(
            root / "project",
            "QT-TEST",
            "Qt GUI Test",
            "Example Customer",
        )
        self.controller.create_target(
            "WEB-01",
            "Customer Portal",
            "https://portal.example.test",
            "Staging",
        )

    def tearDown(self) -> None:
        self.app.closeAllWindows()
        self.app.processEvents()
        self.settings.remove("appearance/darkMode")
        self.settings.sync()
        self.temporary.cleanup()

    def _create_finding(self, title: str, severity: str = "High"):
        return self.controller.create_finding(
            FindingInput(
                target_id="WEB-01",
                title=title,
                severity=severity,
                status="Confirmed",
                category="Access Control",
                url="https://portal.example.test/api/orders/{id}",
                method="GET",
                summary="Object ownership is not checked.",
                impact="Another customer's data may be disclosed.",
                remediation="Verify ownership for every object request.",
            )
        )

    def test_main_window_loads_snapshot_and_filters_findings(self) -> None:
        high = self._create_finding("Order IDOR", "High")
        self._create_finding("Verbose error", "Low")
        window = MainWindow(controller=self.controller)
        try:
            self.assertEqual(window.windowTitle(), "Otter")
            self.assertFalse(self.app.windowIcon().isNull())
            self.assertEqual(window.project_label.text(), "Qt GUI Test")
            self.assertEqual(window.findings_page.model.rowCount(), 2)
            self.assertEqual(set(window.pages), {
                "dashboard", "targets", "findings", "evidence", "credentials", "knowledge",
                "reports", "archive", "settings"
            })
            self.assertEqual(window.targets_page.table.rowCount(), 1)
            self.assertEqual(window.settings_page.tabs.count(), 1)

            window.findings_page.severity_filter.setCurrentText("High")
            self.assertEqual(window.findings_page.proxy.rowCount(), 1)
            window.findings_page.search.setText("IDOR")
            self.assertEqual(window.findings_page.proxy.rowCount(), 1)
            window.findings_page.select_finding(high.id)
            self.assertEqual(window.findings_page.detail.finding_id, high.id)
            self.assertIn("Order IDOR", window.findings_page.detail.title_label.text())
        finally:
            window.close()

    def test_application_font_can_render_korean(self) -> None:
        metrics = QFontMetrics(self.app.font())
        self.assertTrue(metrics.inFontUcs4(ord("한")))

    def test_theme_toggle_is_accessible_persistent_and_renders_both_modes(self) -> None:
        window = MainWindow(controller=self.controller)
        try:
            window.show()
            self.app.processEvents()
            self.assertFalse(window.theme_toggle.isChecked())
            self.assertEqual(window.theme_toggle.accessibleName(), "다크 모드")
            light = window.grab().toImage()

            window.theme_toggle.clearFocus()
            QTest.mouseClick(window.theme_toggle, Qt.MouseButton.LeftButton)
            self.assertFalse(window.theme_toggle.hasFocus())
            QTest.mouseClick(window.theme_toggle, Qt.MouseButton.LeftButton)
            self.assertFalse(window.theme_toggle.isChecked())

            window.theme_toggle.setFocus()
            QTest.keyClick(window.theme_toggle, Qt.Key.Key_Return)
            self.app.processEvents()
            self.assertTrue(window.dark_mode)
            self.assertTrue(
                QSettings().value("appearance/darkMode", False, type=bool)
            )
            dark = window.grab().toImage()
            self.assertFalse(light.isNull())
            self.assertFalse(dark.isNull())
            self.assertNotEqual(light.pixelColor(5, 5), dark.pixelColor(5, 5))
        finally:
            window.close()

        reopened = MainWindow(controller=self.controller)
        try:
            self.assertTrue(reopened.theme_toggle.isChecked())
            self.assertTrue(reopened.dark_mode)
        finally:
            reopened.close()

    def test_procedure_editor_manages_steps_order_and_evidence_links(self) -> None:
        finding = self._create_finding("Procedure GUI")
        source = Path(self.temporary.name) / "step.txt"
        source.write_text("observed response", encoding="utf-8")
        evidence = self.controller.add_evidence(
            finding.id,
            source,
            "Step evidence",
            "log",
            "Observed response",
            True,
            False,
        )
        dialog = FindingEditorDialog(
            self.controller, finding_id=finding.id, initial_tab="procedure"
        )
        try:
            editor = dialog.procedure_editor
            self.assertEqual(dialog.tabs.currentWidget(), editor)
            editor.preconditions_edit.setPlainText("Two accounts exist.")
            editor._add_step()
            editor.step_title_edit.setText("First request")
            editor.action_edit.setPlainText("Send the first request.")
            editor.evidence_list.item(0).setCheckState(Qt.CheckState.Checked)
            editor._add_step()
            editor.step_title_edit.setText("Second request")
            editor.action_edit.setPlainText("Change the object ID.")
            editor._move_step(-1)
            dialog._save()
            self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        finally:
            dialog.close()

        procedure = self.controller.get_procedure(finding.id)
        self.assertEqual(
            [step.title for step in procedure.steps],
            ["Second request", "First request"],
        )
        self.assertEqual(procedure.steps[1].evidence_ids, (evidence.id,))

        page = FindingsPage()
        try:
            page.set_snapshot(
                self.controller.snapshot(),
                procedures={finding.id: procedure},
                retests={finding.id: self.controller.get_retests(finding.id)},
            )
            page.select_finding(finding.id)
            self.assertIn("Second request", page.detail.procedure_label.text())
            self.assertIn(evidence.id, page.detail.procedure_label.text())
            self.assertEqual(
                page.detail.retest_label.text(), "등록된 재검증 이력이 없습니다."
            )
            self.assertFalse(hasattr(page, "procedure_requested"))
        finally:
            page.close()

    def test_status_bar_restores_project_summary_after_work(self) -> None:
        window = MainWindow(controller=self.controller)
        try:
            expected = "대상 1개 · 취약점 0개"
            self.assertEqual(window.statusBar().currentMessage(), expected)
            window._set_busy("보고서를 생성하고 있습니다…")
            self.assertEqual(
                window.statusBar().currentMessage(),
                "보고서를 생성하고 있습니다…",
            )
            window._set_busy("")
            self.assertEqual(window.statusBar().currentMessage(), expected)
            window._show_transient_status("임시 오류", 20)
            self.assertEqual(window.statusBar().currentMessage(), "임시 오류")
            QTest.qWait(100)
            self.app.processEvents()
            self.assertEqual(window.statusBar().currentMessage(), expected)
        finally:
            window.close()

    def test_retest_editor_creates_structured_history_and_updates_status(self) -> None:
        finding = self._create_finding("Retest GUI")
        self.controller.save_procedure(
            finding.id,
            preconditions="A test account exists.",
            steps=[
                ProcedureStepInput(
                    title="Repeat request",
                    action="Send the original reproduction request.",
                )
            ],
        )
        dialog = RetestEditorDialog(self.controller, finding.id)
        try:
            dialog.tester_edit.setText("GUI Tester")
            dialog.result_combo.setCurrentText("Passed")
            dialog.remediation_edit.setPlainText("The server rejects the request.")
            dialog.step_result_combo.setCurrentText("Passed")
            dialog.step_observed_edit.setPlainText("HTTP 403 is returned.")
            dialog._save()
            self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        finally:
            dialog.close()
        retests = self.controller.get_retests(finding.id)
        self.assertEqual(retests.items[0].id, "RT-001")
        self.assertEqual(retests.items[0].steps[0].result, "Passed")
        self.assertEqual(self.controller.get_finding(finding.id).status, "RetestPassed")

    def test_plain_project_auto_lock_only_locks_vault(self) -> None:
        self.controller.create_credential_vault("correct horse battery staple")
        window = MainWindow(controller=self.controller)
        try:
            self.assertTrue(window.auto_lock_timer.isActive())
            window._auto_lock_project()
            self.assertIsNotNone(self.controller.project)
            self.assertFalse(self.controller.credential_vault_unlocked())
            self.assertFalse(window.auto_lock_timer.isActive())
        finally:
            window.close()

    def test_finding_editor_creates_and_updates_complete_record(self) -> None:
        dialog = FindingEditorDialog(self.controller)
        dialog.title_edit.setText("Account takeover through IDOR")
        dialog.severity_combo.setCurrentText("Critical")
        dialog.status_combo.setCurrentText("Confirmed")
        dialog.category_combo.setCurrentText("Access Control")
        dialog.cwe_edit.setText("CWE-639")
        dialog.cvss_score.setText("9.1")
        dialog.url_edit.setText("https://portal.example.test/api/users/{id}")
        dialog.method_combo.setCurrentText("GET")
        dialog.parameter_edit.setText("id")
        dialog.role_edit.setText("Authenticated user")
        dialog.summary_edit.setPlainText("Changing the ID returns another account.")
        dialog.impact_edit.setPlainText("Account data and tokens can be exposed.")
        dialog.remediation_edit.setPlainText("Authorize every object request.")
        dialog.procedure_editor._add_step()
        dialog.procedure_editor.step_title_edit.setText("Change the account ID")
        dialog.procedure_editor.action_edit.setPlainText("Request another user's ID.")
        dialog.root_cause_edit.setPlainText(
            "The query does not constrain records by the authenticated account."
        )
        dialog.request_edit.setPlainText("GET /api/users/2 HTTP/1.1")
        dialog._save()

        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        finding = dialog.result_value
        self.assertEqual(finding.severity, "Critical")
        self.assertEqual(finding.cvss.score, 9.1)
        self.assertEqual(finding.presentation.impact, "Account data and tokens can be exposed.")
        self.assertEqual(
            self.controller.get_procedure(finding.id).steps[0].title,
            "Change the account ID",
        )
        self.assertIn("authenticated account", finding.technical_details.root_cause)

        edit = FindingEditorDialog(self.controller, finding_id=finding.id)
        edit.status_combo.setCurrentText("Resolved")
        edit.remediation_edit.setPlainText("Server-side ownership checks were deployed.")
        edit._save()
        updated = self.controller.get_finding(finding.id)
        self.assertEqual(updated.status, "Resolved")
        self.assertEqual(
            updated.presentation.remediation,
            "Server-side ownership checks were deployed.",
        )

    def test_finding_editor_keeps_values_on_validation_error(self) -> None:
        dialog = FindingEditorDialog(self.controller)
        dialog.title_edit.setText("Invalid CVSS sample")
        dialog.cvss_score.setText("not-a-number")
        dialog._save()
        self.assertNotEqual(dialog.result(), QDialog.DialogCode.Accepted)
        self.assertFalse(dialog.error_label.isHidden())
        self.assertEqual(dialog.title_edit.text(), "Invalid CVSS sample")
        self.assertEqual(self.controller.snapshot().findings, ())

    def test_evidence_editor_and_page_preview_metadata(self) -> None:
        finding = self._create_finding("Evidence workflow")
        source = Path(self.temporary.name) / "response.http"
        source.write_text("HTTP/1.1 200 OK\n\n{\"id\": 2}\n", encoding="utf-8")
        dialog = EvidenceEditorDialog(
            self.controller,
            finding.id,
            source_path=source,
        )
        dialog.title_edit.setText("Redacted response")
        dialog.caption_edit.setPlainText("Another account response.")
        dialog.include_check.setChecked(True)
        dialog._save()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        evidence = dialog.result_value
        self.assertEqual(evidence.type, "http-exchange")
        self.assertTrue(evidence.include_in_report)

        edit = EvidenceEditorDialog(
            self.controller,
            finding.id,
            evidence_id=evidence.id,
        )
        replacement = Path(self.temporary.name) / "replacement.png"
        replacement.write_bytes(b"replacement")
        self.assertTrue(edit.browse_button.isEnabled())
        self.assertEqual(edit.browse_button.text(), "파일 교체")
        with mock.patch(
            "webpentestkit.qt_gui.dialogs.QFileDialog.getOpenFileName",
            return_value=(str(replacement), ""),
        ):
            edit._browse()
        self.assertEqual(edit._replacement_path, str(replacement))
        edit.sensitive_check.setChecked(True)
        self.assertFalse(edit.include_check.isChecked())
        edit._save()
        updated = self.controller.get_evidence(finding.id, evidence.id)
        self.assertTrue(updated.contains_sensitive_data)
        self.assertFalse(updated.include_in_report)
        self.assertEqual(
            self.controller.evidence_location(finding.id, evidence.id).read_bytes(),
            b"replacement",
        )

        window = MainWindow(controller=self.controller)
        try:
            window.evidence_page.finding_combo.setCurrentIndex(0)
            window.refresh_evidence(finding.id)
            self.assertEqual(window.evidence_page.count_label.text(), "1개")
            self.assertEqual(window.evidence_page.grid.count(), 1)
        finally:
            window.close()

    def test_template_version_and_apply_dialog(self) -> None:
        template = self.controller.search_templates("IDOR")[0]
        editor = TemplateEditorDialog(self.controller, template_id=template.id)
        editor.remediation_edit.setPlainText("Enforce ownership in the service layer.")
        editor._save()
        self.assertEqual(editor.result(), QDialog.DialogCode.Accepted)
        self.assertEqual(editor.result_value.version, template.version + 1)

        apply_dialog = TemplateApplyDialog(self.controller, template.id)
        apply_dialog.title_edit.setText("Profile object IDOR")
        apply_dialog.status_combo.setCurrentText("Confirmed")
        apply_dialog.url_edit.setText("https://portal.example.test/api/profile/{id}")
        apply_dialog.parameter_edit.setText("id")
        apply_dialog._save()
        self.assertEqual(apply_dialog.result(), QDialog.DialogCode.Accepted)
        finding = apply_dialog.result_value
        self.assertEqual(finding.template.id, template.id)
        self.assertEqual(finding.template.version, template.version + 1)
        self.assertEqual(
            finding.presentation.remediation,
            "Enforce ownership in the service layer.",
        )

        window = MainWindow(controller=self.controller)
        try:
            self.assertGreaterEqual(window.knowledge_page.model.rowCount(), 3)
            window.knowledge_page.select_template(template.id)
            self.assertEqual(window.knowledge_page.detail.template_id, template.id)
        finally:
            window.close()

    def test_knowledge_page_exposes_database_transfer_actions(self) -> None:
        page = KnowledgePage()
        try:
            imported: list[bool] = []
            exported: list[bool] = []
            page.import_requested.connect(lambda: imported.append(True))
            page.export_requested.connect(lambda: exported.append(True))
            page.import_button.click()
            page.export_button.click()
            self.assertEqual(imported, [True])
            self.assertEqual(exported, [True])

            destination = Path(self.temporary.name) / "gui-knowledge.json"
            self.assertEqual(
                self.controller.export_knowledge(destination),
                destination.resolve(),
            )
            result = self.controller.import_knowledge(destination)
            self.assertEqual(result.added_versions, 0)
            self.assertGreaterEqual(result.skipped_versions, 3)
        finally:
            page.close()

    def test_encrypted_project_credentials_and_lock_flow(self) -> None:
        password = "correct horse battery staple"
        encrypted_path = Path(self.temporary.name) / "assessment.wpkproj"
        self.controller.create_encrypted_copy(encrypted_path, password)
        self.controller.close_project()

        encrypted_controller = GuiController(Path(self.temporary.name) / "encrypted-knowledge.db")
        encrypted_controller.open_encrypted_project(encrypted_path, password=password)
        encrypted_controller.create_credential_vault("separate vault password")
        encrypted_controller.add_credential(
            CredentialInput(
                name="Staging administrator",
                credential_type="password",
                secret_values={"password": "not-in-the-table"},
                target_ids=("WEB-01",),
                environment="Staging",
                role="Administrator",
                username="tester@example.test",
            )
        )

        window = MainWindow(controller=encrypted_controller)
        try:
            self.assertFalse(window.project_lock_button.isHidden())
            self.assertTrue(window.auto_lock_timer.isActive())
            self.assertEqual(window.credentials_page.table.rowCount(), 1)
            values = [
                window.credentials_page.table.item(0, column).text()
                for column in range(window.credentials_page.table.columnCount())
            ]
            self.assertNotIn("not-in-the-table", values)

            window.lock_project()
            deadline = time.monotonic() + 10
            while window.tasks.is_busy and time.monotonic() < deadline:
                self.app.processEvents()
                QTest.qWait(20)
            self.assertFalse(window.tasks.is_busy)
            self.assertIsNone(encrypted_controller.project)
            self.assertFalse(window.auto_lock_timer.isActive())
            self.assertEqual(window.credentials_page.table.rowCount(), 0)
        finally:
            window.close()

    def test_archive_page_restores_and_permanently_deletes_credentials(self) -> None:
        password = "correct horse battery staple"
        self.controller.create_credential_vault(password)
        credential = self.controller.add_credential(
            CredentialInput(
                name="Archived operator",
                credential_type="password",
                secret_values={"password": "vault-only-secret"},
                target_ids=("WEB-01",),
                status="Active",
            )
        )
        self.controller.archive_credential(credential.id, "GUI archive test")
        window = MainWindow(controller=self.controller)
        try:
            self.assertEqual(window.archive_page.table.rowCount(), 1)
            window.archive_page.table.selectRow(0)
            archive_id, entity_type, entity_id = window.archive_page.selected_archive()
            self.assertEqual(archive_id, f"credential:{credential.id}")
            self.assertEqual(entity_type, "계정")
            self.assertEqual(entity_id, credential.id)
            self.assertTrue(window.archive_page.restore_button.isEnabled())
            self.assertTrue(window.archive_page.purge_button.isEnabled())

            with mock.patch(
                "webpentestkit.qt_gui.main_window.QInputDialog.getText",
                return_value=(credential.id, True),
            ):
                window.purge_archive(archive_id, entity_type, entity_id)
            deadline = time.monotonic() + 10
            while window.tasks.is_busy and time.monotonic() < deadline:
                self.app.processEvents()
                QTest.qWait(20)
            self.assertFalse(window.tasks.is_busy)
            self.assertEqual(self.controller.list_credentials(include_archived=True), [])

            second = self.controller.add_credential(
                CredentialInput(
                    name="Restorable operator",
                    credential_type="password",
                    secret_values={"password": "another-secret"},
                    target_ids=("WEB-01",),
                    status="Active",
                )
            )
            self.assertEqual(second.id, "ACC-002")
            self.controller.archive_credential(second.id, "Restore test")
            window.refresh_all()
            with mock.patch(
                "webpentestkit.qt_gui.main_window.QMessageBox.question",
                return_value=QMessageBox.StandardButton.Yes,
            ):
                window.restore_archive(f"credential:{second.id}")
            self.assertEqual(self.controller.get_credential(second.id).status, "Active")

            self.controller.archive_credential(second.id, "Locked vault notice")
            self.controller.lock_credential_vault()
            window.refresh_credentials()
            self.assertEqual(window.archive_page.table.rowCount(), 0)
            self.assertFalse(window.archive_page.vault_notice.isHidden())
        finally:
            window.close()

    def test_settings_reports_and_archive_pages_use_controller_boundary(self) -> None:
        finding = self._create_finding("Operational page workflow")
        notes = FindingEditorDialog(
            self.controller, finding_id=finding.id, initial_tab="technical"
        )
        self.assertEqual(notes.tabs.currentIndex(), 4)
        notes.analyst_notes_edit.setPlainText("Structured tester notes.")
        notes._save()
        self.assertEqual(
            self.controller.get_finding(finding.id).technical_details.analyst_notes,
            "Structured tester notes.",
        )
        window = MainWindow(controller=self.controller)
        try:
            window.settings_page.project_name.setText("Updated Qt Project")
            window.settings_page.report_title.setText("Updated Security Report")
            window.settings_page._save()
            self.assertEqual(self.controller.get_project().name, "Updated Qt Project")
            self.assertEqual(
                self.controller.get_report_config().report_title,
                "Updated Security Report",
            )

            window.run_validation()
            deadline = time.monotonic() + 15
            while window.tasks.is_busy and time.monotonic() < deadline:
                self.app.processEvents()
                QTest.qWait(20)
            self.assertFalse(window.tasks.is_busy)
            self.assertIn("오류", window.reports_page.validation_state.text())

            window.build_reports()
            deadline = time.monotonic() + 15
            while window.tasks.is_busy and time.monotonic() < deadline:
                self.app.processEvents()
                QTest.qWait(20)
            self.assertFalse(window.tasks.is_busy)
            self.assertIn("보고서:", window.reports_page.output_path.text())

            self.controller.archive_finding(finding.id, "Qt archive page test")
            window.refresh_all()
            self.assertEqual(window.archive_page.table.rowCount(), 1)
            window.archive_page.table.selectRow(0)
            self.assertTrue(window.archive_page.selected_archive_id())
            self.assertTrue(window.archive_page.restore_button.isEnabled())
        finally:
            window.close()


if __name__ == "__main__":
    unittest.main()
