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
from PySide6.QtWidgets import QDialog, QGroupBox, QLabel, QMessageBox  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from webpentestkit.errors import KitError  # noqa: E402
from webpentestkit.gui.controller import GuiController  # noqa: E402
from webpentestkit.models import (  # noqa: E402
    CredentialInput,
    EvidenceDraft,
    FindingInput,
    ProcedureStepInput,
)
from webpentestkit.qt_gui import MainWindow, create_application  # noqa: E402
from webpentestkit.qt_gui.dialogs import (  # noqa: E402
    EncryptProjectDialog,
    EvidenceEditorDialog,
    FindingEditorDialog,
    RetestEditorDialog,
    TargetEditorDialog,
    TemplateApplyDialog,
    TemplateEditorDialog,
)
from webpentestkit.qt_gui.pages import FindingsPage, KnowledgePage  # noqa: E402


class QtGuiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        settings = QSettings("Otter", "Otter")
        cls._ui_language_was_set = settings.contains("appearance/uiLanguage")
        cls._previous_ui_language = settings.value("appearance/uiLanguage")
        settings.remove("appearance/darkMode")
        settings.setValue("appearance/uiLanguage", "ko-KR")
        settings.sync()
        cls.app = create_application([])

    @classmethod
    def tearDownClass(cls) -> None:
        settings = QSettings("Otter", "Otter")
        if cls._ui_language_was_set:
            settings.setValue("appearance/uiLanguage", cls._previous_ui_language)
        else:
            settings.remove("appearance/uiLanguage")
        settings.sync()

    def setUp(self) -> None:
        self.settings = QSettings()
        self.settings.remove("appearance/darkMode")
        self.settings.remove("appearance/uiLanguage")
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
            self.assertEqual(window.settings_page.tabs.count(), 2)

            window.findings_page.severity_filter.setCurrentIndex(
                window.findings_page.severity_filter.findData("High")
            )
            self.assertEqual(window.findings_page.proxy.rowCount(), 1)
            window.findings_page.search.setText("IDOR")
            self.assertEqual(window.findings_page.proxy.rowCount(), 1)
            window.findings_page.select_finding(high.id)
            self.assertEqual(window.findings_page.detail.finding_id, high.id)
            self.assertIn("Order IDOR", window.findings_page.detail.title_label.text())
            window.findings_page.show_list()
            self.assertEqual(window.findings_page.search.text(), "IDOR")
            self.assertEqual(window.findings_page.severity_filter.currentData(), "High")
            self.assertEqual(window.findings_page.proxy.rowCount(), 1)
        finally:
            window.close()

    def test_dashboard_counts_canonical_info_severity(self) -> None:
        self._create_finding("GraphQL introspection enabled", "Info")
        window = MainWindow(controller=self.controller)
        try:
            window.show()
            self.app.processEvents()
            info_item = next(
                window.dashboard_page.severity_list.item(index)
                for index in range(window.dashboard_page.severity_list.count())
                if window.dashboard_page.severity_list.item(index).data(
                    Qt.ItemDataRole.UserRole
                )
                == "Info"
            )
            info_row = window.dashboard_page.severity_list.itemWidget(info_item)
            self.assertEqual(info_row.count_label.text(), "1")
            self.assertTrue(
                info_item.data(Qt.ItemDataRole.AccessibleTextRole).endswith(
                    ": 1"
                )
            )
            count_labels = [
                window.dashboard_page.severity_list.itemWidget(
                    window.dashboard_page.severity_list.item(index)
                ).count_label
                for index in range(
                    window.dashboard_page.severity_list.count()
                )
            ]
            self.assertEqual({label.width() for label in count_labels}, {42})
            self.assertEqual(
                len(
                    {
                        label.mapTo(
                            window.dashboard_page,
                            label.rect().topRight(),
                        ).x()
                        for label in count_labels
                    }
                ),
                1,
            )
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
            "report-ready",
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
            editor.evidence_links.table.item(0, 0).setCheckState(Qt.CheckState.Checked)
            editor.evidence_links.link_caption_edit.setText(
                "Response observed during the first request."
            )
            editor.evidence_links.link_placement_combo.setCurrentIndex(
                editor.evidence_links.link_placement_combo.findData("appendix")
            )
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
        procedure_link = next(
            link
            for link in self.controller.list_evidence_links(finding.id)
            if link.scope_type == "procedure" and link.evidence_id == evidence.id
        )
        self.assertEqual(
            procedure_link.caption,
            "Response observed during the first request.",
        )
        self.assertEqual(procedure_link.placement, "appendix")

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
                page.detail.retest_list.item(0).text(),
                "등록된 재검증 이력이 없습니다.",
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
        source = Path(self.temporary.name) / "retest-response.http"
        source.write_text("HTTP/1.1 403 Forbidden", encoding="utf-8")
        evidence = self.controller.add_evidence(
            finding.id,
            source,
            "Retest response",
            "http-response",
            "The remediated endpoint rejects the request.",
            "report-ready",
        )
        dialog = RetestEditorDialog(self.controller, finding.id)
        try:
            dialog.evidence_links.set_selected_ids({evidence.id})
            self.assertEqual(dialog.evidence_links.selected_ids(), [evidence.id])
            dialog.evidence_links.link_caption_edit.setText(
                "Retest-specific rejection response."
            )
            dialog.evidence_links.link_placement_combo.setCurrentIndex(
                dialog.evidence_links.link_placement_combo.findData("attachment")
            )
            dialog.tester_edit.setText("GUI Tester")
            dialog.result_combo.setCurrentIndex(dialog.result_combo.findData("Passed"))
            dialog.remediation_edit.setPlainText("The server rejects the request.")
            dialog.verification_edit.setPlainText("HTTP 403 is returned.")
            dialog._save()
            self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        finally:
            dialog.close()
        retests = self.controller.get_retests(finding.id)
        self.assertEqual(retests.items[0].id, "RT-001")
        self.assertEqual(retests.items[0].verification_details, "HTTP 403 is returned.")
        self.assertEqual(retests.items[0].evidence_ids, (evidence.id,))
        retest_link = next(
            link
            for link in self.controller.list_evidence_links(finding.id)
            if link.scope_type == "retest"
        )
        self.assertEqual(retest_link.caption, "Retest-specific rejection response.")
        self.assertEqual(retest_link.placement, "attachment")
        self.assertEqual(self.controller.get_finding(finding.id).status, "Confirmed")
        self.assertEqual(retests.latest_result, "Passed")

        editor = RetestEditorDialog(
            self.controller, finding.id, retest_id=retests.items[0].id
        )
        try:
            self.assertEqual(editor.evidence_links.selected_ids(), [evidence.id])
            editor.verification_edit.setPlainText("HTTP 403 remains enforced.")
            editor._save()
            self.assertEqual(editor.result(), QDialog.DialogCode.Accepted)
        finally:
            editor.close()
        self.assertEqual(
            self.controller.get_retest(finding.id, "RT-001").verification_details,
            "HTTP 403 remains enforced.",
        )

        window = MainWindow(controller=self.controller)
        try:
            window.findings_page.select_finding(finding.id)
            window.findings_page.retest_edit_requested.disconnect(
                window.edit_retest
            )
            emitted: list[tuple[str, str]] = []
            window.findings_page.detail.retest_edit_requested.connect(
                lambda finding_id, retest_id: emitted.append((finding_id, retest_id))
            )
            window.findings_page.detail.retest_edit_button.click()
            self.assertEqual(emitted, [(finding.id, "RT-001")])
        finally:
            window.close()

    def test_target_editor_updates_validated_status(self) -> None:
        dialog = TargetEditorDialog(self.controller, target_id="WEB-01")
        try:
            dialog.status.setCurrentIndex(dialog.status.findData("Paused"))
            dialog._save()
            self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        finally:
            dialog.close()
        self.assertEqual(self.controller.get_target("WEB-01").status, "Paused")

    def test_sidebar_hierarchy_and_compact_layout_keep_proportions(self) -> None:
        finding = self._create_finding("Full-width finding detail")
        window = MainWindow(controller=self.controller)
        try:
            window.show()
            window.resize(1440, 900)
            self.app.processEvents()
            groups = window.findChildren(QLabel, "navGroupLabel")
            self.assertEqual([label.text() for label in groups], [
                "프로젝트", "도구"
            ])
            self.assertTrue(all(label.property("navLevel") == 1 for label in groups))
            self.assertTrue(
                all(
                    button.property("navLevel") == 2
                    for button in window.nav_buttons.values()
                )
            )
            self.assertTrue(
                all(not button.icon().isNull() for button in window.nav_buttons.values())
            )
            self.assertEqual(window.sidebar.width(), 216)
            self.assertEqual(window.nav_buttons["findings"].text(), "취약점")
            self.assertGreater(
                window.side_layout.indexOf(window.nav_buttons["settings"]),
                window.side_layout.indexOf(window.nav_footer_separator),
            )
            window.navigate("findings")
            self.app.processEvents()
            self.assertFalse(hasattr(window.findings_page, "splitter"))
            index = window.findings_page.proxy.index(0, 0)
            window.findings_page.table.setCurrentIndex(index)
            window.findings_page.table.selectRow(0)
            self.app.processEvents()
            self.assertTrue(window.findings_page.open_button.isEnabled())
            window.findings_page.table.clicked.emit(index)
            self.assertEqual(
                window.findings_page.stack.currentWidget(),
                window.findings_page.list_page,
            )
            window.findings_page.open_button.click()
            self.assertEqual(window.findings_page.detail.finding_id, finding.id)
            self.assertEqual(
                window.findings_page.stack.currentWidget(),
                window.findings_page.detail,
            )
            QTest.keyClick(window.findings_page, Qt.Key.Key_Escape)
            self.assertEqual(
                window.findings_page.stack.currentWidget(),
                window.findings_page.list_page,
            )

            window.resize(1100, 650)
            self.app.processEvents()
            self.assertEqual(window.sidebar.width(), 216)
            self.assertTrue(all(label.isVisible() for label in groups))
            self.assertEqual(window.nav_buttons["findings"].text(), "취약점")
            self.assertEqual(window.nav_buttons["findings"].toolTip(), "")
            self.assertTrue(window.brand_label.isVisible())
            self.assertTrue(window.brand_subtitle.isVisible())
            self.assertFalse(window.project_meta.isVisible())
            self.assertTrue(window.findings_page.table.isColumnHidden(2))
            self.assertTrue(window.findings_page.table.isColumnHidden(7))
            self.assertTrue(window.evidence_page.table.isColumnHidden(2))
            self.assertTrue(window.evidence_page.table.isColumnHidden(6))
        finally:
            window.close()

    def test_main_window_uses_roomier_screen_aware_default_size(self) -> None:
        window = MainWindow(controller=self.controller)
        try:
            available = self.app.primaryScreen().availableGeometry()
            expected_width = max(1024, min(1800, int(available.width() * 0.95)))
            expected_height = max(600, min(1000, int(available.height() * 0.95)))
            self.assertEqual(window.width(), expected_width)
            self.assertEqual(window.height(), expected_height)
        finally:
            window.close()

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
        dialog.severity_combo.setCurrentIndex(dialog.severity_combo.findData("Critical"))
        dialog.status_combo.setCurrentIndex(dialog.status_combo.findData("Confirmed"))
        dialog.category_combo.setCurrentIndex(
            dialog.category_combo.findData("Access Control")
        )
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
        dialog.analysis_edit.setPlainText("The returned account belongs to another user.")
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
        edit.status_combo.setCurrentIndex(edit.status_combo.findData("Resolved"))
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

    def test_new_finding_defers_evidence_until_the_whole_editor_is_saved(self) -> None:
        source = Path(self.temporary.name) / "deferred.http"
        source.write_text("HTTP/1.1 403 Forbidden", encoding="utf-8")
        before = len(self.controller.snapshot().findings)

        cancelled = FindingEditorDialog(self.controller)
        cancelled.procedure_editor._add_step()
        token = "draft:cancelled"
        cancelled.procedure_editor.evidence_links._drafts[token] = EvidenceDraft(
            source_path=str(source),
            title="Cancelled evidence",
            evidence_type="http-response",
            classification="report-ready",
        )
        cancelled.procedure_editor.evidence_links.set_selected_ids({token})
        cancelled.reject()
        self.assertEqual(len(self.controller.snapshot().findings), before)

        dialog = FindingEditorDialog(self.controller)
        dialog.title_edit.setText("Deferred evidence workflow")
        dialog.url_edit.setText("https://portal.example.test/api/items/2")
        dialog.procedure_editor._add_step()
        dialog.procedure_editor.step_title_edit.setText("Send the request")
        dialog.procedure_editor.action_edit.setPlainText("Request another object.")
        token = "draft:saved"
        dialog.procedure_editor.evidence_links._drafts[token] = EvidenceDraft(
            source_path=str(source),
            title="Deferred response",
            evidence_type="http-response",
            classification="report-ready",
        )
        dialog.procedure_editor.evidence_links.set_selected_ids({token})
        dialog._save()

        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        finding = dialog.result_value
        evidence = self.controller.list_evidence(finding.id)
        self.assertEqual(len(evidence), 1)
        self.assertEqual(
            self.controller.get_procedure(finding.id).steps[0].evidence_ids,
            (evidence[0].id,),
        )

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
        dialog.classification_combo.setCurrentIndex(
            dialog.classification_combo.findData("report-ready")
        )
        dialog._save()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        evidence = dialog.result_value
        self.assertEqual(evidence.type, "http-exchange")
        self.assertTrue(evidence.is_report_ready)

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
        edit.classification_combo.setCurrentIndex(
            edit.classification_combo.findData("sensitive")
        )
        edit._save()
        updated = self.controller.get_evidence(finding.id, evidence.id)
        self.assertTrue(updated.is_sensitive)
        self.assertFalse(updated.is_report_ready)
        self.assertEqual(
            self.controller.evidence_location(finding.id, evidence.id).read_bytes(),
            b"replacement",
        )

        window = MainWindow(controller=self.controller)
        try:
            window.refresh_evidence()
            self.assertFalse(hasattr(window.evidence_page, "finding_combo"))
            self.assertEqual(
                window.evidence_page.count_label.text(),
                "1 / 1개",
            )
            self.assertEqual(window.evidence_page.model.rowCount(), 1)
            index = window.evidence_page.proxy.index(0, 0)
            window.evidence_page.table.setCurrentIndex(index)
            window.evidence_page.table.selectRow(0)
            self.app.processEvents()
            self.assertTrue(window.evidence_page.open_button.isEnabled())
            window.evidence_page.table.clicked.emit(index)
            self.assertEqual(
                window.evidence_page.stack.currentWidget(),
                window.evidence_page.list_page,
            )
            window.evidence_page.open_button.click()
            self.assertEqual(
                window.evidence_page.stack.currentWidget(),
                window.evidence_page.detail,
            )
            self.assertEqual(window.evidence_page.detail.evidence_id, evidence.id)
            window.evidence_page.detail.back_requested.emit()
            self.assertEqual(
                window.evidence_page.stack.currentWidget(),
                window.evidence_page.list_page,
            )
        finally:
            window.close()

    def test_finding_detail_opens_linked_evidence_from_table(self) -> None:
        finding = self._create_finding("Linked evidence table")
        source = Path(self.temporary.name) / "linked-response.http"
        source.write_text("HTTP/1.1 200 OK\n\nlinked", encoding="utf-8")
        linked = self.controller.add_evidence(
            finding.id,
            source,
            "Linked response",
            "http-exchange",
            "Response used in the finding.",
            "report-ready",
            True,
        )
        self.controller.add_evidence(
            finding.id,
            source,
            "Unlinked working file",
            "http-exchange",
            "Stored without a usage link.",
            "internal",
            False,
        )

        window = MainWindow(controller=self.controller)
        try:
            window.resize(1024, 600)
            window.show()
            self.app.processEvents()
            window.navigate("findings")
            window.findings_page.select_finding(finding.id)
            self.app.processEvents()
            detail = window.findings_page.detail
            self.assertEqual(detail.evidence_model.rowCount(), 1)
            self.assertEqual(detail.evidence_count_label.text(), "1개")
            self.assertEqual(
                detail.evidence_model.data(detail.evidence_model.index(0, 0)),
                linked.id,
            )
            self.assertEqual(
                detail.evidence_model.data(detail.evidence_model.index(0, 1)),
                "Linked response",
            )
            self.assertEqual(
                detail.evidence_model.data(detail.evidence_model.index(0, 5)),
                "취약점 본문",
            )
            self.assertTrue(detail.evidence_table.isColumnHidden(4))
            self.assertTrue(detail.evidence_table.isColumnHidden(6))
            original_scroll = min(
                120,
                detail.verticalScrollBar().maximum(),
            )
            self.assertGreater(original_scroll, 0)
            detail.verticalScrollBar().setValue(original_scroll)

            detail.evidence_table.doubleClicked.emit(
                detail.evidence_model.index(0, 0)
            )
            self.app.processEvents()
            self.assertEqual(window.stack.currentWidget(), window.evidence_page)
            self.assertEqual(
                window.evidence_page.stack.currentWidget(),
                window.evidence_page.detail,
            )
            self.assertEqual(window.evidence_page.detail.evidence_id, linked.id)
            window.evidence_page.detail.back_requested.emit()
            self.app.processEvents()
            self.assertEqual(window.stack.currentWidget(), window.findings_page)
            self.assertEqual(
                window.findings_page.stack.currentWidget(),
                window.findings_page.detail,
            )
            self.assertEqual(window.findings_page.detail.finding_id, finding.id)
            self.assertEqual(
                window.evidence_page.stack.currentWidget(),
                window.evidence_page.list_page,
            )
            self.assertEqual(
                detail.verticalScrollBar().value(),
                original_scroll,
            )
            detail.evidence_table.doubleClicked.emit(
                detail.evidence_model.index(0, 0)
            )
            self.app.processEvents()
            QTest.keyClick(window.evidence_page, Qt.Key.Key_Escape)
            self.app.processEvents()
            self.assertEqual(window.stack.currentWidget(), window.findings_page)
            self.assertEqual(window.findings_page.detail.finding_id, finding.id)
        finally:
            window.close()

    def test_global_evidence_add_separates_asset_fields_from_usage(self) -> None:
        first = self._create_finding("First finding")
        second = self._create_finding("Second finding")
        source = Path(self.temporary.name) / "global.http"
        source.write_text("GET / HTTP/1.1", encoding="utf-8")

        dialog = EvidenceEditorDialog(
            self.controller,
            None,
            source_path=source,
            select_finding=True,
        )
        groups = [group.title() for group in dialog.findChildren(QGroupBox)]
        self.assertIn("증적 정보", groups)
        self.assertIn("사용처 · 연결된 항목", groups)
        self.assertIsNotNone(dialog.finding_combo)
        dialog.finding_combo.setCurrentIndex(
            dialog.finding_combo.findData(second.id)
        )
        self.assertFalse(dialog.finding_usage_check.isChecked())
        self.assertFalse(dialog.finding_link_caption_edit.isEnabled())
        dialog.title_edit.setText("Global HTTP request")
        dialog._save()

        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        self.assertEqual(dialog.result_value.finding_id, second.id)
        self.assertEqual(self.controller.list_evidence(first.id), [])
        self.assertFalse(
            self.controller.get_evidence_usage(
                second.id, dialog.result_value.id
            ).finding_presentation
        )

        linked = EvidenceEditorDialog(
            self.controller,
            None,
            source_path=source,
            select_finding=True,
        )
        linked.finding_combo.setCurrentIndex(
            linked.finding_combo.findData(first.id)
        )
        linked.title_edit.setText("Report HTTP request")
        linked.finding_usage_check.setChecked(True)
        linked.finding_link_caption_edit.setText("Request used in the finding body.")
        linked.finding_link_placement_combo.setCurrentIndex(
            linked.finding_link_placement_combo.findData("appendix")
        )
        linked._save()
        finding_link = next(
            item
            for item in self.controller.list_evidence_links(first.id)
            if item.scope_type == "finding"
        )
        self.assertEqual(finding_link.caption, "Request used in the finding body.")
        self.assertEqual(finding_link.placement, "appendix")

        window = MainWindow(controller=self.controller)
        try:
            self.assertEqual(window.evidence_page.model.rowCount(), 2)
            window.evidence_page.search.setText("Second finding")
            self.assertEqual(window.evidence_page.proxy.rowCount(), 1)
            window.evidence_page.reset_filters()
            self.assertEqual(window.evidence_page.proxy.rowCount(), 2)
            window.evidence_page.search.setText("Request used in the finding body")
            self.assertEqual(window.evidence_page.proxy.rowCount(), 1)
            window.evidence_page.reset_filters()
            window.evidence_page.usage_filter.setCurrentIndex(
                window.evidence_page.usage_filter.findData("unlinked")
            )
            self.assertEqual(window.evidence_page.proxy.rowCount(), 1)
            window.evidence_page.reset_filters()
            index = window.evidence_page.proxy.index(0, 0)
            window.evidence_page._open_index(index)
            self.assertIn("GET / HTTP/1.1", window.evidence_page.detail.preview_label.text())
            QTest.keyClick(window.evidence_page, Qt.Key.Key_Escape)
            self.assertEqual(
                window.evidence_page.stack.currentWidget(),
                window.evidence_page.list_page,
            )
        finally:
            window.close()

    def test_evidence_editor_updates_usage_specific_caption_and_placement(self) -> None:
        finding = self._create_finding("Evidence link context")
        source = Path(self.temporary.name) / "context.http"
        source.write_text("HTTP/1.1 403 Forbidden", encoding="utf-8")
        evidence = self.controller.add_evidence(
            finding.id,
            source,
            "Context response",
            "http-response",
            "Asset-level description",
            "report-ready",
            True,
        )
        procedure = self.controller.save_procedure(
            finding.id,
            preconditions="",
            steps=[
                ProcedureStepInput(
                    title="Verify access control",
                    action="Send the request.",
                    evidence_ids=(evidence.id,),
                )
            ],
        )
        dialog = EvidenceEditorDialog(
            self.controller, finding.id, evidence_id=evidence.id
        )
        self.assertEqual(len(dialog.link_editors), 1)
        dialog.finding_link_caption_edit.setText("Finding-level response.")
        dialog.finding_link_placement_combo.setCurrentIndex(
            dialog.finding_link_placement_combo.findData("attachment")
        )
        _link, caption, placement = dialog.link_editors[0]
        caption.setText("Procedure-specific denial response.")
        placement.setCurrentIndex(placement.findData("appendix"))
        dialog._save()
        link = next(
            item
            for item in self.controller.list_evidence_links(finding.id)
            if item.scope_type == "procedure"
            and item.scope_id == procedure.steps[0].id
        )
        self.assertEqual(link.caption, "Procedure-specific denial response.")
        self.assertEqual(link.placement, "appendix")
        finding_link = next(
            item
            for item in self.controller.list_evidence_links(finding.id)
            if item.scope_type == "finding"
        )
        self.assertEqual(finding_link.caption, "Finding-level response.")
        self.assertEqual(finding_link.placement, "attachment")
        asset_only = EvidenceEditorDialog(
            self.controller,
            finding.id,
            evidence_id=evidence.id,
            asset_only=True,
        )
        asset_only.finding_usage_check.setChecked(False)
        asset_only.title_edit.setText("Renamed asset only")
        asset_only._save()
        self.assertTrue(
            self.controller.get_evidence_usage(
                finding.id, evidence.id
            ).finding_presentation
        )

    def test_finding_editor_stages_technical_usage_settings_until_save(self) -> None:
        finding = self._create_finding("Atomic technical evidence")
        source = Path(self.temporary.name) / "technical.http"
        source.write_text("HTTP/1.1 401 Unauthorized", encoding="utf-8")
        evidence = self.controller.add_evidence(
            finding.id,
            source,
            "Unauthorized response",
            "http-response",
            "Asset description",
            "report-ready",
        )

        cancelled = FindingEditorDialog(
            self.controller, finding_id=finding.id, initial_tab="technical"
        )
        cancelled.technical_evidence_links.table.item(0, 0).setCheckState(
            Qt.CheckState.Checked
        )
        cancelled.technical_evidence_links.link_caption_edit.setText(
            "Technical-only response."
        )
        cancelled.reject()
        self.assertFalse(
            any(
                link.scope_type == "technical"
                for link in self.controller.list_evidence_links(finding.id)
            )
        )

        saved = FindingEditorDialog(
            self.controller, finding_id=finding.id, initial_tab="technical"
        )
        saved.technical_evidence_links.table.item(0, 0).setCheckState(
            Qt.CheckState.Checked
        )
        saved.technical_evidence_links.link_caption_edit.setText(
            "Technical-only response."
        )
        saved.technical_evidence_links.link_placement_combo.setCurrentIndex(
            saved.technical_evidence_links.link_placement_combo.findData("appendix")
        )
        saved._save()
        self.assertEqual(saved.result(), QDialog.DialogCode.Accepted)
        link = next(
            link
            for link in self.controller.list_evidence_links(finding.id)
            if link.scope_type == "technical" and link.evidence_id == evidence.id
        )
        self.assertEqual(link.caption, "Technical-only response.")
        self.assertEqual(link.placement, "appendix")

    def test_template_edit_apply_archive_and_delete(self) -> None:
        template = self.controller.search_templates("IDOR")[0]
        editor = TemplateEditorDialog(self.controller, template_id=template.id)
        editor.remediation_edit.setPlainText("Enforce ownership in the service layer.")
        editor._save()
        self.assertEqual(editor.result(), QDialog.DialogCode.Accepted)
        self.assertEqual(editor.result_value.version, template.version)

        apply_dialog = TemplateApplyDialog(self.controller, template.id)
        apply_dialog.title_edit.setText("Profile object IDOR")
        apply_dialog.status_combo.setCurrentIndex(
            apply_dialog.status_combo.findData("Confirmed")
        )
        apply_dialog.url_edit.setText("https://portal.example.test/api/profile/{id}")
        apply_dialog.parameter_edit.setText("id")
        apply_dialog._save()
        self.assertEqual(apply_dialog.result(), QDialog.DialogCode.Accepted)
        finding = apply_dialog.result_value
        self.assertEqual(finding.template.id, template.id)
        self.assertEqual(finding.template.version, template.version)
        self.assertEqual(
            finding.presentation.remediation,
            "Enforce ownership in the service layer.",
        )

        window = MainWindow(controller=self.controller)
        try:
            self.assertGreaterEqual(window.knowledge_page.model.rowCount(), 3)
            window.knowledge_page.select_template(template.id)
            self.assertIs(
                window.knowledge_page.stack.currentWidget(),
                window.knowledge_page.list_page,
            )
            self.assertEqual(window.knowledge_page.detail.template_id, "")
            selected = window.knowledge_page.table.selectionModel().selectedRows()[0]
            window.knowledge_page.table.activated.emit(selected)
            self.assertEqual(window.knowledge_page.detail.template_id, template.id)
            self.assertEqual(window.knowledge_page.detail.edit_button.text(), "수정")
            self.assertEqual(
                window.knowledge_page.detail.apply_button.text(),
                "이 템플릿으로 취약점 추가",
            )
            self.assertEqual(window.knowledge_page.detail.archive_button.text(), "보관")
            self.assertEqual(window.knowledge_page.detail.delete_button.text(), "삭제")
            self.assertIs(
                window.knowledge_page.stack.currentWidget(),
                window.knowledge_page.detail,
            )
            window.knowledge_page.detail.back_requested.emit()
            self.assertIs(
                window.knowledge_page.stack.currentWidget(),
                window.knowledge_page.list_page,
            )

            with mock.patch.object(
                QMessageBox,
                "question",
                return_value=QMessageBox.StandardButton.Yes,
            ):
                window.archive_template(template.id)
            archived = self.controller.get_template(template.id)
            self.assertTrue(archived.archived)
            self.assertEqual(archived.status, "Approved")
            self.assertEqual(window.knowledge_page.proxy.rowCount(), 2)

            with mock.patch.object(
                QMessageBox,
                "question",
                return_value=QMessageBox.StandardButton.Yes,
            ):
                window.archive_template(template.id)
            self.assertFalse(self.controller.get_template(template.id).archived)
            self.assertEqual(self.controller.get_template(template.id).status, "Approved")

            with mock.patch(
                "webpentestkit.qt_gui.main_window.QInputDialog.getText",
                return_value=(template.id, True),
            ):
                window.delete_template(template.id)
            with self.assertRaises(KitError):
                self.controller.get_template(template.id)
            self.assertEqual(
                self.controller.get_finding(finding.id).presentation.remediation,
                "Enforce ownership in the service layer.",
            )
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
            self.assertIn(
                "암호화 프로젝트",
                window.reports_page.protection_label.text(),
            )
            self.assertFalse(hasattr(window.reports_page, "encrypt_project_button"))
            self.assertTrue(window.settings_page.encrypt_project_button.isHidden())
            self.assertFalse(window.settings_page.backup_project_button.isHidden())
            self.assertFalse(
                window.settings_page.change_project_password_button.isHidden()
            )
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
        notes.analysis_edit.setPlainText("Structured tester analysis.")
        notes._save()
        self.assertEqual(
            self.controller.get_finding(finding.id).technical_details.analysis,
            "Structured tester analysis.",
        )
        window = MainWindow(controller=self.controller)
        try:
            self.assertEqual(window.settings_page.tabs.count(), 2)
            self.assertEqual(window.settings_page.tabs.tabText(0), "프로그램")
            self.assertEqual(
                window.settings_page.ui_language.currentData(),
                "ko-KR",
            )
            self.assertEqual(window.settings_page.tabs.tabText(1), "프로젝트")
            self.assertFalse(hasattr(window.settings_page, "report_title"))
            window.settings_page._save_ui_language()
            self.assertEqual(
                QSettings().value("appearance/uiLanguage", type=str),
                "ko-KR",
            )
            window.settings_page.project_name.setText("Updated Qt Project")
            window.settings_page._save()
            self.assertEqual(self.controller.get_project().name, "Updated Qt Project")
            window.navigate("reports")
            self.assertFalse(hasattr(window.reports_page, "settings_button"))
            self.assertEqual(
                window.reports_page.tabs.tabText(4),
                "보고서 설정",
            )
            window.reports_page.tabs.setCurrentIndex(4)
            self.assertEqual(window.reports_page.tabs.currentIndex(), 4)
            self.assertEqual(
                window.reports_page.report_language.currentData(),
                "en-US",
            )
            window.reports_page.report_title_edit.setText(
                "Updated Security Report"
            )
            window.reports_page._save_report_settings()
            self.assertEqual(
                self.controller.get_report_config().report_title,
                "Updated Security Report",
            )
            self.assertEqual(window.stack.currentWidget(), window.reports_page)
            self.assertEqual(window.reports_page.tabs.currentIndex(), 4)

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
            self.assertIn("최근 산출물:", window.reports_page.output_path.text())
            self.assertEqual(window.reports_page.tabs.currentIndex(), 2)
            self.assertEqual(
                window.reports_page.outputs_table.item(0, 1).text(),
                "생성됨",
            )

            self.controller.archive_finding(finding.id, "Qt archive page test")
            window.refresh_all()
            self.assertEqual(window.archive_page.table.rowCount(), 1)
            window.archive_page.table.selectRow(0)
            self.assertTrue(window.archive_page.selected_archive_id())
            self.assertTrue(window.archive_page.restore_button.isEnabled())
        finally:
            window.close()

    def test_reports_page_filters_categories_and_tracks_outputs_separately(self) -> None:
        window = MainWindow(controller=self.controller)
        try:
            page = window.reports_page
            self.assertEqual(page.tabs.count(), 5)
            self.assertIn("언어: en-US", page.profile_label.text())
            self.assertIn("평문 프로젝트", page.protection_label.text())
            self.assertFalse(hasattr(page, "settings_button"))
            self.assertFalse(hasattr(page, "encrypt_project_button"))
            self.assertFalse(window.settings_page.encrypt_project_button.isHidden())
            self.assertTrue(window.settings_page.backup_project_button.isHidden())
            self.assertFalse(hasattr(window.credentials_page, "encrypt_button"))
            with mock.patch.object(
                EncryptProjectDialog,
                "exec",
                return_value=QDialog.DialogCode.Rejected,
            ) as encrypt_dialog:
                window.settings_page.encrypt_project_button.click()
            encrypt_dialog.assert_called_once()
            page.project_protection_button.click()
            self.assertEqual(window.stack.currentWidget(), window.settings_page)
            self.assertEqual(window.settings_page.tabs.currentIndex(), 1)
            window.navigate("reports")
            page.set_issues(
                [
                    {
                        "level": "ERROR",
                        "category": "project-structure",
                        "code": "PROJECT_REQUIRED",
                        "message": "Project name is required.",
                        "path": "project.json",
                    },
                    {
                        "level": "WARNING",
                        "category": "evidence-security",
                        "code": "POSSIBLE_SECRET",
                        "message": "A secret may be present.",
                        "path": "evidence/request.http",
                    },
                ]
            )
            self.assertEqual(page.issues.columnCount(), 5)
            self.assertEqual(page.issue_count_label.text(), "2 / 2")
            page.category_filter.setCurrentIndex(
                page.category_filter.findData("evidence-security")
            )
            self.assertTrue(page.issues.isRowHidden(0))
            self.assertFalse(page.issues.isRowHidden(1))
            self.assertEqual(page.issue_count_label.text(), "1 / 2")
            page.category_filter.setCurrentIndex(0)
            page.issue_search.setText("PROJECT_REQUIRED")
            self.assertFalse(page.issues.isRowHidden(0))
            self.assertTrue(page.issues.isRowHidden(1))

            report_dir = Path(self.temporary.name) / "report-output"
            report_dir.mkdir()
            (report_dir / "report.md").write_text("# Report\n", encoding="utf-8")
            ppt_dir = Path(self.temporary.name) / "ppt-output"
            ppt_dir.mkdir()
            page.set_output("report", report_dir)
            self.assertEqual(page.outputs_table.item(0, 1).text(), "생성됨")
            self.assertEqual(page.outputs_table.item(1, 1).text(), "미생성")
            page.set_output("ppt", ppt_dir)
            self.assertIn(str(report_dir.resolve()), page.report_output_label.text())
            self.assertIn(str(ppt_dir.resolve()), page.ppt_output_label.text())
            self.assertEqual(page.tabs.currentIndex(), 3)

            opened: list[str] = []
            page.open_output_requested.connect(opened.append)
            page.open_report_button.click()
            page.open_ppt_button.click()
            self.assertEqual(
                opened,
                [str(report_dir.resolve()), str(ppt_dir.resolve())],
            )
            self.assertEqual(page.tabs.tabText(4), "보고서 설정")
        finally:
            window.close()

    def test_reports_page_detects_existing_project_outputs_on_open(self) -> None:
        self._create_finding("Existing report output")
        report_dir = self.controller.build_reports()
        window = MainWindow(controller=self.controller)
        try:
            page = window.reports_page
            self.assertEqual(page.tabs.currentIndex(), 0)
            self.assertEqual(page.report_output_label.text(), str(report_dir.resolve()))
            self.assertTrue(page.open_report_button.isEnabled())
            self.assertEqual(page.outputs_table.item(0, 1).text(), "생성됨")
            self.assertEqual(page.outputs_table.item(4, 1).text(), "생성됨")
        finally:
            window.close()


if __name__ == "__main__":
    unittest.main()
