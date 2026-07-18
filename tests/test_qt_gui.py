from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import (  # noqa: E402
    QCoreApplication,
    QEvent,
    QItemSelectionModel,
    QPoint,
    QSettings,
    Qt,
)
from PySide6.QtGui import QFontMetrics  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QAbstractItemView,
    QApplication,
    QDialog,
    QFrame,
    QGroupBox,
    QHeaderView,
    QLabel,
    QMessageBox,
    QWidget,
)
from PySide6.QtTest import QTest  # noqa: E402

from webpentestkit.errors import KitError  # noqa: E402
from webpentestkit.localization import configure_localization  # noqa: E402
from webpentestkit.gui.controller import GuiController  # noqa: E402
from webpentestkit.models import (  # noqa: E402
    CredentialInput,
    EvidenceDraft,
    FindingInput,
    ProcedureStepInput,
)
from webpentestkit.qt_gui import MainWindow, create_application  # noqa: E402
from webpentestkit.qt_gui.dialogs import (  # noqa: E402
    CvssCalculatorDialog,
    CvssFieldWidget,
    EncryptProjectDialog,
    EvidenceEditorDialog,
    FindingEditorDialog,
    RetestEditorDialog,
    TargetEditorDialog,
    TemplateApplyDialog,
    TemplateEditorDialog,
)
from webpentestkit.qt_gui.pages import (  # noqa: E402
    FindingsPage,
    KnowledgePage,
    PresentationsPage,
)
from webpentestkit.qt_gui.theme import LIGHT, build_stylesheet  # noqa: E402


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
        for widget in QApplication.topLevelWidgets():
            widget.close()
            widget.deleteLater()
        QCoreApplication.sendPostedEvents(
            None,
            QEvent.Type.DeferredDelete,
        )
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
            "reports", "presentations", "archive", "settings"
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

    def test_template_workspace_is_global_and_project_output_is_embedded(self) -> None:
        controller = GuiController(Path(self.temporary.name) / "global-knowledge.db")
        window = MainWindow(controller=controller)
        try:
            project_title = window.project_label.text()
            project_meta = window.project_meta.text()
            self.assertIn(
                "공용 라이브러리",
                [label.text() for label in window.nav_group_labels],
            )
            self.assertTrue(window.presentations_page.analyze_button.isEnabled())
            self.assertTrue(window.presentations_page.create_profile_button.isEnabled())
            self.assertTrue(window.presentations_page.load_profile_button.isEnabled())
            self.assertFalse(window.presentations_page.plan_button.isEnabled())
            self.assertFalse(window.presentation_output_page.render_button.isEnabled())
            self.assertEqual(
                window.reports_page.tabs.indexOf(window.presentation_output_page),
                4,
            )
            self.assertTrue(window.presentations_page.tabs.isTabVisible(0))
            self.assertFalse(window.presentations_page.tabs.isTabVisible(3))
            self.assertFalse(window.presentation_output_page.tabs.tabBar().isVisible())
            window.presentation_output_page.set_template_library(
                [
                    {"id": "ready", "name": "Ready", "status": "ready"},
                    {"id": "review", "name": "Review", "status": "review"},
                ]
            )
            self.assertEqual(window.presentation_output_page.output_template_combo.count(), 2)
            window.navigate("presentations")
            self.assertEqual(window.project_label.text(), "PPT 템플릿 워크스페이스")
            self.assertIn("모든 프로젝트", window.project_meta.text())
            window.navigate("dashboard")
            self.assertEqual(window.project_label.text(), project_title)
            self.assertEqual(window.project_meta.text(), project_meta)
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
        source = Path(self.temporary.name) / "step.png"
        source.write_bytes(b"observed-response-image")
        evidence = self.controller.add_evidence(
            finding.id,
            source,
            "Step evidence",
            "screenshot",
            "Observed response",
            "report-ready",
        )
        second_source = Path(self.temporary.name) / "step-2.png"
        second_source.write_bytes(b"second-observed-response-image")
        second_evidence = self.controller.add_evidence(
            finding.id,
            second_source,
            "Second step evidence",
            "screenshot",
            "Second observed response",
            "report-ready",
        )
        dialog = FindingEditorDialog(
            self.controller, finding_id=finding.id, initial_tab="procedure"
        )
        try:
            editor = dialog.procedure_editor
            self.assertEqual(dialog.tabs.currentWidget(), editor)
            self.assertEqual(
                editor.evidence_links.settings_group.title(),
                "선택한 증적의 표시 방식",
            )
            self.assertIn("재현 절차", editor.evidence_links.link_context_label.text())
            self.assertEqual(
                editor.evidence_links.link_placement_combo.currentText(),
                "연결 위치에 표시",
            )
            editor.preconditions_edit.setPlainText("Two accounts exist.")
            editor._add_step()
            editor.step_title_edit.setText("First request")
            editor.action_edit.setPlainText("Send the first request.")
            editor.evidence_links.table.item(0, 0).setCheckState(Qt.CheckState.Checked)
            editor.evidence_links.table.item(1, 0).setCheckState(Qt.CheckState.Checked)
            self.assertEqual(
                editor.evidence_links.selected_ids(),
                [evidence.id, second_evidence.id],
            )
            self.assertFalse(hasattr(editor.evidence_links, "max_links"))
            self.assertFalse(hasattr(editor.evidence_links, "require_report_image"))
            for row in range(editor.evidence_links.table.rowCount()):
                item = editor.evidence_links.table.item(row, 0)
                if item.data(Qt.ItemDataRole.UserRole) == evidence.id:
                    editor.evidence_links.table.selectRow(row)
                    break
            editor.evidence_links.link_caption_edit.setText(
                "Response observed during the first request."
            )
            editor.evidence_links.link_placement_combo.setCurrentIndex(
                editor.evidence_links.link_placement_combo.findData("appendix")
            )
            editor.evidence_links.link_order_spin.setValue(30)
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
        self.assertEqual(
            set(procedure.steps[1].evidence_ids),
            {evidence.id, second_evidence.id},
        )
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
        self.assertEqual(procedure_link.order, 30)

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
                "프로젝트", "공용 라이브러리"
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
            expected_width = max(1440, min(1800, int(available.width() * 0.95)))
            expected_height = max(810, min(1000, int(available.height() * 0.95)))
            self.assertEqual(window.width(), expected_width)
            self.assertEqual(window.height(), expected_height)
            self.assertEqual(window.minimumWidth(), 1440)
            self.assertEqual(window.minimumHeight(), 810)
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
        dialog.source_mode_combo.setCurrentIndex(
            dialog.source_mode_combo.findData("manual")
        )
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
        self.assertEqual(dialog.source_mode_combo.currentData(), "library")
        dialog.title_edit.setText("Invalid CVSS sample")
        dialog.cvss_score.setText("not-a-number")
        dialog._save()
        self.assertNotEqual(dialog.result(), QDialog.DialogCode.Accepted)
        self.assertFalse(dialog.error_label.isHidden())
        self.assertEqual(dialog.title_edit.text(), "Invalid CVSS sample")
        self.assertEqual(self.controller.snapshot().findings, ())

    def test_finding_editor_can_start_from_approved_library_template(self) -> None:
        dialog = FindingEditorDialog(self.controller)
        dialog.source_mode_combo.setCurrentIndex(
            dialog.source_mode_combo.findData("library")
        )
        template_index = dialog.template_combo.findData("WPK-ACCESS-001")
        self.assertGreaterEqual(template_index, 0)
        dialog.template_combo.setCurrentIndex(template_index)
        self.assertEqual(dialog.title_edit.text(), "객체 수준 접근통제 미흡")
        self.assertIn("CWE-639", dialog.cwe_edit.text())
        self.assertTrue(dialog.summary_edit.toPlainText())
        dialog.title_edit.setText("Order API object authorization missing")
        dialog.url_edit.setText("https://portal.example.test/api/orders/2")
        dialog._save()

        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        finding = dialog.result_value
        self.assertIsNotNone(finding.template)
        self.assertEqual(finding.template.id, "WPK-ACCESS-001")
        self.assertEqual(finding.template.version, 1)
        self.assertEqual(finding.title, "Order API object authorization missing")

    def test_cvss_widget_calculates_vector_and_reports_legacy_mismatch(self) -> None:
        vector = "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:N"
        widget = CvssFieldWidget(9.1, vector)
        self.assertFalse(widget.message_label.isHidden())
        with self.assertRaises(KitError) as mismatch:
            widget.values()
        self.assertEqual(mismatch.exception.code, "CVSS_SCORE_VECTOR_MISMATCH")

        calculator = CvssCalculatorDialog(vector)
        self.assertEqual(calculator.score_label.text(), "8.1")
        calculator._save()
        self.assertEqual(calculator.result(), QDialog.DialogCode.Accepted)
        self.assertEqual(calculator.result_value.score, 8.1)
        widget.set_values(
            calculator.result_value.score,
            calculator.result_value.vector,
        )
        self.assertEqual(widget.values(), (8.1, vector))

    def test_new_finding_defers_evidence_until_the_whole_editor_is_saved(self) -> None:
        source = Path(self.temporary.name) / "deferred.png"
        source.write_bytes(b"deferred-response-image")
        before = len(self.controller.snapshot().findings)

        cancelled = FindingEditorDialog(self.controller)
        cancelled.procedure_editor._add_step()
        token = "draft:cancelled"
        cancelled.procedure_editor.evidence_links._drafts[token] = EvidenceDraft(
            source_path=str(source),
            title="Cancelled evidence",
            evidence_type="screenshot",
            classification="report-ready",
        )
        cancelled.procedure_editor.evidence_links.set_selected_ids({token})
        cancelled.reject()
        self.assertEqual(len(self.controller.snapshot().findings), before)

        dialog = FindingEditorDialog(self.controller)
        dialog.source_mode_combo.setCurrentIndex(
            dialog.source_mode_combo.findData("manual")
        )
        dialog.title_edit.setText("Deferred evidence workflow")
        dialog.url_edit.setText("https://portal.example.test/api/items/2")
        dialog.procedure_editor._add_step()
        dialog.procedure_editor.step_title_edit.setText("Send the request")
        dialog.procedure_editor.action_edit.setPlainText("Request another object.")
        token = "draft:saved"
        dialog.procedure_editor.evidence_links._drafts[token] = EvidenceDraft(
            source_path=str(source),
            title="Deferred response",
            evidence_type="screenshot",
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

    def test_template_edit_apply_and_direct_delete(self) -> None:
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
            self.assertEqual(window.knowledge_page.detail.delete_button.text(), "삭제")
            self.assertFalse(hasattr(window.knowledge_page.detail, "archive_button"))
            self.assertFalse(hasattr(window.knowledge_page, "batch_archive_button"))
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
                window.reports_page.tabs.tabText(
                    window.reports_page.tabs.indexOf(window.reports_page.settings_tab)
                ),
                "기본 정보",
            )
            window.reports_page.tabs.setCurrentWidget(window.reports_page.settings_tab)
            self.assertEqual(
                window.reports_page.tabs.currentWidget(),
                window.reports_page.settings_tab,
            )
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
            self.assertEqual(
                window.reports_page.tabs.currentWidget(),
                window.reports_page.settings_tab,
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
            self.assertIn("최근 산출물:", window.reports_page.output_path.text())
            self.assertEqual(window.reports_page.tabs.currentIndex(), 3)
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
            self.assertEqual(page.tabs.count(), 6)
            self.assertEqual(
                page.tabs.tabText(page.tabs.indexOf(window.presentation_output_page)),
                "PPT 생성·검토",
            )
            self.assertIn("언어: 영어", page.profile_label.text())
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
            self.assertFalse(page.fix_issue_button.isEnabled())
            page.issues.selectRow(0)
            self.assertTrue(page.fix_issue_button.isEnabled())
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
            self.assertFalse(
                page.tabs.isTabVisible(page.tabs.indexOf(page.advanced_export_tab))
            )
            self.assertEqual(
                page.tabs.currentWidget(), window.presentation_output_page
            )

            opened: list[str] = []
            page.open_output_requested.connect(opened.append)
            page.open_report_button.click()
            page.open_ppt_button.click()
            self.assertEqual(
                opened,
                [str(report_dir.resolve()), str(ppt_dir.resolve())],
            )
            self.assertEqual(
                page.tabs.tabText(page.tabs.indexOf(page.settings_tab)),
                "기본 정보",
            )
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

    def test_presentation_template_loads_existing_mapping_immediately(self) -> None:
        page = PresentationsPage()
        page.set_analysis(
            {
                "template": {
                    "slideCount": 1,
                    "slideSize": {"cx": 100, "cy": 50},
                    "sha256": "a" * 64,
                },
                "warnings": [],
                "slides": [
                    {
                        "number": 1,
                        "shapes": [
                            {"id": 7, "name": "Title", "kind": "text", "text": "보고서 제목"}
                        ],
                    }
                ],
            }
        )
        page.set_profile(
            {
                "formatVersion": 5,
                "id": "existing-template",
                "name": "Existing template",
                "templateHash": "a" * 64,
                "families": [{"id": "document", "name": "문서 시작"}],
                "storyRecipe": {
                    "document": [
                        {
                            "id": "cover",
                            "role": "cover",
                            "repeat": "once",
                            "when": "always",
                            "familyId": "document",
                            "enabled": True,
                        }
                    ],
                    "finding": [],
                    "appendix": [],
                },
                "layouts": [
                    {
                        "id": "cover-main",
                        "familyId": "document",
                        "role": "cover",
                        "sourceSlide": 1,
                        "composition": {"itemCapacity": 1, "itemEvidenceCapacity": [0]},
                        "variant": {
                            "kind": "primary",
                            "textDensity": "regular",
                            "priority": 0,
                            "conditions": {"minEvidence": 0, "requiredValues": []},
                        },
                        "bindings": {
                            "title": {"kind": "text", "shapeId": 7, "maxChars": 70}
                        },
                        "capacity": {"items": 1, "evidence": 0},
                    }
                ],
            }
        )

        self.assertEqual(page.layout_combo.currentData(), "cover-main")
        self.assertIn("표지", page.layout_combo.currentText())
        self.assertNotIn("cover-main", page.layout_combo.currentText())
        self.assertNotIn("primary", page.layout_combo.currentText())
        self.assertEqual(page.role_combo.currentData(), "cover")
        self.assertEqual(page.slide_combo.currentData(), 1)
        self.assertEqual(page._current_bindings[7][0], "title")
        self.assertEqual(page.layout_combo.count(), 1)
        self.assertEqual(page.workflow_step_labels[0].property("state"), "complete")
        self.assertEqual(page.workflow_step_labels[1].property("state"), "complete")
        self.assertTrue(bool(page.workflow_step_labels[0].property("active")))
        page.tabs.setCurrentIndex(1)
        self.assertFalse(bool(page.workflow_step_labels[0].property("active")))
        self.assertTrue(bool(page.workflow_step_labels[1].property("active")))
        self.assertIn("현재 화면", page.workflow_step_labels[1].accessibleName())
        page.tabs.setCurrentIndex(2)
        self.assertFalse(bool(page.workflow_step_labels[1].property("active")))
        self.assertTrue(bool(page.workflow_step_labels[2].property("active")))
        self.assertEqual(len(page.workflow_step_labels), 3)
        self.assertEqual(
            [button.text() for button in page.workflow_step_labels],
            ["1  파일 불러오기", "2  콘텐츠 연결", "3  순서 확인"],
        )
        self.assertNotEqual(page.workflow_status_label.text(), "")
        self.assertTrue(page.variant_kind_combo.isHidden())
        self.assertTrue(page.create_profile_button.isHidden())
        self.assertEqual(page.analyze_button.text(), "PPTX 다시 분석")

    def test_presentation_analysis_discovers_the_existing_mapping_file(self) -> None:
        window = MainWindow(controller=self.controller)
        try:
            page = window.presentations_page
            profile_path = Path(self.temporary.name) / "company.otter-profile.json"
            profile_path.write_text("{}", encoding="utf-8")
            page.set_path("template", str(Path(self.temporary.name) / "company.pptx"))
            page.set_path("profile", str(profile_path))
            profile = {
                "formatVersion": 1,
                "id": "existing",
                "name": "Existing",
                "templateHash": "a" * 64,
                "story": {"document": [], "finding": ["finding-detail"]},
                "layouts": [],
            }
            analysis = {
                "template": {
                    "slideCount": 1,
                    "slideSize": {"cx": 100, "cy": 50},
                    "sha256": "a" * 64,
                },
                "warnings": [],
                "slides": [{"number": 1, "shapes": []}],
            }
            with (
                mock.patch.object(
                    self.controller,
                    "load_presentation_profile",
                    return_value=profile,
                ),
                mock.patch.object(window, "_register_current_presentation_template"),
            ):
                window._presentation_analysis_finished(analysis, page)
            self.assertIsNotNone(page.profile_value())
            self.assertEqual(page.profile_value()["id"], "existing")
            self.assertEqual(page.tabs.currentIndex(), 1)
            self.assertIn("기존 콘텐츠 연결", window.toast.label.text())
        finally:
            window.close()

    def test_presentation_output_starts_with_one_clear_action_and_autosaves(self) -> None:
        page = PresentationsPage(mode="output")
        page.set_project_open(True)
        page.set_path("template", "template.pptx")
        page.set_path("profile", "template.otter-profile.json")
        page.set_path("plan", "presentation-plan.json")
        page.set_profile(
            {
                "formatVersion": 1,
                "id": "sample",
                "name": "Sample",
                "templateHash": "a" * 64,
                "story": {"document": [], "finding": ["finding-detail"]},
                "layouts": [],
            }
        )
        self.assertFalse(page.output_empty_card.isHidden())
        self.assertTrue(page.output_splitter.isHidden())
        self.assertTrue(page.plan_command_bar.isHidden())
        self.assertFalse(page.load_plan_button.isHidden())
        self.assertFalse(page.save_plan_button.isHidden())
        self.assertTrue(page.empty_plan_button.isEnabled())

        autosaved: list[tuple[dict, str]] = []
        page.autosave_plan_requested.connect(
            lambda value, path: autosaved.append((value, path))
        )
        page.set_plan(
            {
                "formatVersion": 1,
                "templateHash": "a" * 64,
                "reportIrHash": "b" * 64,
                "profileHash": "c" * 64,
                "pages": [
                    {
                        "id": "page-0001",
                        "semanticKey": "finding:W-01:procedure:STEP-001",
                        "role": "finding-detail",
                        "layoutId": "finding-detail-main",
                        "values": {"title": "Finding"},
                        "evidence": [],
                        "overrides": {},
                    }
                ],
            }
        )
        self.assertTrue(page.output_empty_card.isHidden())
        self.assertFalse(page.output_splitter.isHidden())
        self.assertIn("확인", page.draft_state_label.text())
        page.set_plan_status(
            {
                "state": "changed",
                "isCurrent": False,
                "changed": ["project"],
            }
        )
        self.assertIn("취약점·절차·증적 변경", page.draft_state_label.text())
        self.assertEqual(page.plan_button.text(), "변경사항 반영")
        self.assertEqual(page.plan_table.item(0, 2).text(), "취약점 W-01")
        page.set_plan_status(
            {"state": "current", "isCurrent": True, "changed": []}
        )
        self.assertIn("최신 상태", page.draft_state_label.text())
        page.plan_table.item(0, 0).setCheckState(Qt.CheckState.Unchecked)
        self.assertTrue(autosaved)
        self.assertEqual(autosaved[-1][1], "presentation-plan.json")
        self.assertFalse(autosaved[-1][0]["pages"][0]["included"])
        self.assertIn("자동 저장", page.output_status.text())

    def test_presentation_library_requires_an_explicit_selection(self) -> None:
        page = PresentationsPage(mode="studio")
        page.set_template_library(
            [
                {
                    "id": "ready",
                    "name": "Ready",
                    "status": "ready",
                    "layoutCount": 3,
                    "templatePath": "template.pptx",
                }
            ]
        )
        self.assertFalse(page.use_library_button.isEnabled())
        self.assertFalse(page.remove_library_button.isEnabled())
        page.library_table.selectRow(0)
        self.assertTrue(page.use_library_button.isEnabled())
        self.assertTrue(page.remove_library_button.isEnabled())

    def test_output_library_refresh_does_not_reload_the_active_template(self) -> None:
        page = PresentationsPage(mode="output")
        page.set_path("template", "template.pptx")
        page.set_path("profile", "template.otter-profile.json")
        page.set_profile(
            {
                "formatVersion": 1,
                "id": "sample",
                "name": "Sample",
                "templateHash": "a" * 64,
                "story": {"document": [], "finding": ["finding-detail"]},
                "layouts": [],
            }
        )
        requested: list[str] = []
        page.load_profile_requested.connect(requested.append)
        page.set_template_library(
            [
                {
                    "id": "ready",
                    "name": "Ready",
                    "status": "ready",
                    "layoutCount": 0,
                    "templatePath": "template.pptx",
                    "profilePath": "template.otter-profile.json",
                }
            ]
        )
        self.assertEqual(page.output_template_combo.currentIndex(), 1)
        self.assertEqual(requested, [])

    def test_presentations_page_maps_regular_shapes_to_semantic_slots(self) -> None:
        page = PresentationsPage()
        page.set_project_open(True)
        self.assertFalse(page.role_combo.isEditable())
        self.assertEqual(page.slot_combo.findData("anything"), -1)
        self.assertTrue(page.profile_path_widget.isHidden())
        page.set_analysis(
            {
                "template": {
                    "slideCount": 1,
                    "slideSize": {"cx": 100, "cy": 50},
                    "sha256": "b" * 64,
                },
                "warnings": ["OLE/embedded object: preserve-only"],
                "slides": [
                    {
                        "number": 1,
                        "shapes": [
                            {"id": 2, "name": "Title", "kind": "text", "text": "제목"},
                            {"id": 4, "name": "Evidence frame", "kind": "text", "text": "증적 사진"},
                        ],
                    }
                ],
            }
        )
        self.assertNotIn("OLE/embedded object", page.analysis_label.text())
        self.assertIn("OLE/embedded object", page.analysis_label.toolTip())
        page.set_profile(
            {
                "formatVersion": 1,
                "id": "sample",
                "name": "Sample",
                "templateHash": "a" * 64,
                "story": {"document": [], "finding": ["finding-detail"]},
                "layouts": [],
            }
        )
        page._update_template_change_state()
        page._update_template_change_state()
        self.assertEqual(
            page.analysis_label.text().count(
                "PPTX 파일이 콘텐츠 연결 저장 이후 변경되었습니다."
            ),
            1,
        )
        page.role_combo.setCurrentIndex(page.role_combo.findData("finding-result"))
        page.family_combo.setEditText("finding-flow")
        page.variant_kind_combo.setCurrentIndex(
            page.variant_kind_combo.findData("continuation")
        )
        page.text_density_combo.setCurrentIndex(
            page.text_density_combo.findData("long")
        )
        page.shape_table.selectRow(0)
        page.slot_combo.setCurrentIndex(page.slot_combo.findData("title"))
        page.bind_shape_button.click()
        page.shape_table.selectRow(1)
        page.slot_combo.setCurrentIndex(page.slot_combo.findData("evidence.0"))
        self.assertEqual(page.binding_kind_label.text(), "이미지")
        page.fit_combo.setCurrentIndex(page.fit_combo.findData("cover"))
        page.bind_shape_button.click()
        page.update_layout_button.click()
        profile = page.profile_value()
        self.assertIsNotNone(profile)
        layout = profile["layouts"][0]
        self.assertEqual(profile["formatVersion"], 5)
        self.assertEqual(layout["familyId"], "finding-flow")
        self.assertEqual(layout["variant"]["kind"], "continuation")
        self.assertEqual(layout["variant"]["textDensity"], "long")
        self.assertEqual(layout["sourceSlide"], 1)
        self.assertEqual(layout["capacity"]["evidence"], 1)
        self.assertEqual(layout["bindings"]["evidence.0"]["shapeId"], 4)
        self.assertIn(
            "finding-result",
            [node["role"] for node in profile["storyRecipe"]["finding"]],
        )
        page.set_plan(
            {
                "formatVersion": 1,
                "templateHash": "a" * 64,
                "reportIrHash": "b" * 64,
                "profileHash": "c" * 64,
                "pages": [
                    {
                        "id": "page-0001",
                        "role": "finding-result",
                        "layoutId": "finding-result-s1-primary-e1",
                        "values": {"title": "First"},
                        "evidence": [{"id": "A", "title": "Screenshot"}],
                        "overrides": {},
                    },
                    {
                        "id": "page-0002",
                        "role": "finding-result",
                        "layoutId": "finding-result-s1-primary-e1",
                        "values": {"title": "Second"},
                        "evidence": [],
                        "overrides": {},
                    },
                ],
                "warnings": [],
            }
        )
        self.assertFalse(page.slide_adjustment_button.isHidden())
        self.assertTrue(page.slide_adjustments.isHidden())
        page.slide_adjustment_button.click()
        self.assertFalse(page.slide_adjustments.isHidden())
        self.assertFalse(page.focus_row.isHidden())
        page.evidence_fit_combo.setCurrentIndex(
            page.evidence_fit_combo.findData("contain")
        )
        self.assertTrue(page.focus_row.isHidden())
        page.focal_x.setValue(0.25)
        page.focal_y.setValue(0.75)
        self.assertTrue(page.apply_evidence_button.isHidden())
        page.remove_page_button.click()
        self.assertFalse(page.plan_value()["pages"][0]["included"])
        page.include_page_button.click()
        self.assertTrue(page.plan_value()["pages"][0]["included"])
        page.move_down_button.click()
        plan = page.plan_value()
        self.assertEqual(plan["pages"][0]["values"]["title"], "Second")
        override = plan["pages"][1]["overrides"]["evidence.0"]
        self.assertEqual(override["fit"], "contain")
        self.assertEqual(override["focalPoint"], {"x": 0.25, "y": 0.75})

    def test_presentation_workspaces_keep_headers_and_detail_rows_readable(self) -> None:
        window = MainWindow(controller=self.controller)
        try:
            window.resize(1800, 1000)
            window.show()
            window.navigate("presentations")
            self.app.processEvents()

            library_header = window.presentations_page.library_table.horizontalHeader()
            self.assertEqual(
                library_header.sectionResizeMode(2),
                QHeaderView.ResizeMode.ResizeToContents,
            )
            self.assertGreaterEqual(
                library_header.sectionSize(2),
                library_header.sectionSizeHint(2),
            )

            window.navigate("reports")
            window.reports_page.show_presentation_output()
            self.app.processEvents()
            page = window.presentation_output_page
            page.set_path("template", "template.pptx")
            page.set_path("profile", "template.otter-profile.json")
            page.set_profile(
                {
                    "formatVersion": 1,
                    "id": "sample",
                    "name": "Sample",
                    "templateHash": "a" * 64,
                    "story": {"document": [], "finding": ["finding-detail"]},
                    "layouts": [
                        {
                            "id": "finding-detail-main",
                            "role": "finding-detail",
                            "sourceSlide": 1,
                            "bindings": {"evidence.0": {"shapeId": 1, "fit": "cover"}},
                            "capacity": {"items": 1, "evidence": 1},
                        },
                        {
                            "id": "finding-detail-alt",
                            "role": "finding-detail",
                            "sourceSlide": 2,
                            "bindings": {"evidence.0": {"shapeId": 1, "fit": "contain"}},
                            "capacity": {"items": 1, "evidence": 1},
                        },
                    ],
                }
            )
            page.set_plan(
                {
                    "formatVersion": 1,
                    "templateHash": "a" * 64,
                    "reportIrHash": "b" * 64,
                    "profileHash": "c" * 64,
                    "pages": [
                        {
                            "id": "page-0001",
                            "role": "finding-detail",
                            "layoutId": "finding-detail-main",
                            "values": {"title": "Finding"},
                            "evidence": [{"id": "A", "title": "Screenshot"}],
                            "overrides": {},
                        }
                    ],
                }
            )
            self.app.processEvents()
            detail_card = page.findChild(QFrame, "slideSettingsCard")
            detail_pane = page.findChild(QWidget, "slideSettingsPane")
            self.assertIsNotNone(detail_card)
            self.assertIsNotNone(detail_pane)
            self.assertEqual(page.output_splitter.handleWidth(), 16)
            self.assertFalse(page.output_splitter.childrenCollapsible())
            self.assertFalse(page.output_splitter.isCollapsible(0))
            self.assertFalse(page.output_splitter.isCollapsible(1))
            self.assertGreaterEqual(detail_pane.minimumWidth(), 400)
            self.assertLessEqual(detail_pane.width(), 500)
            self.assertEqual(page.layout().contentsMargins().left(), 0)
            self.assertEqual(page.layout().contentsMargins().top(), 0)
            self.assertTrue(page.slide_adjustments.isHidden())
            self.assertFalse(page.slide_adjustment_button.isHidden())
            page.slide_adjustment_button.click()
            self.app.processEvents()
            self.assertFalse(page.slide_adjustments.isHidden())
            row_positions = []
            for widget in (
                page.page_layout_combo,
                page.page_evidence_combo,
                page.focal_x,
            ):
                position = widget.mapTo(detail_card, QPoint(0, 0))
                row_positions.append(position.y())
                self.assertGreaterEqual(position.y(), 0)
                self.assertLessEqual(
                    position.y() + widget.height(),
                    detail_card.height(),
                )
            self.assertEqual(row_positions, sorted(set(row_positions)))
            self.assertGreaterEqual(page.focal_x.width(), 100)
            self.assertGreaterEqual(page.focal_y.width(), 100)
            preview_ratio = page.evidence_preview.width() / page.evidence_preview.height()
            self.assertGreaterEqual(preview_ratio, 1.7)
            self.assertLessEqual(preview_ratio, 2.35)
            preview_hint = page.evidence_preview.sizeHint()
            self.assertAlmostEqual(
                preview_hint.width() / preview_hint.height(),
                16 / 9,
                places=2,
            )

            window.navigate("presentations")
            window.presentations_page.tabs.setCurrentIndex(1)
            self.app.processEvents()
            studio = window.presentations_page
            self.assertEqual(studio.studio_splitter.handleWidth(), 16)
            self.assertFalse(studio.studio_splitter.childrenCollapsible())
            self.assertFalse(studio.studio_splitter.isCollapsible(0))
            self.assertFalse(studio.studio_splitter.isCollapsible(1))
            self.assertEqual(
                studio.mapping_editor_splitter.orientation(),
                Qt.Orientation.Vertical,
            )
            self.assertFalse(studio.mapping_editor_splitter.childrenCollapsible())
            self.assertGreaterEqual(studio.shape_table.minimumHeight(), 202)
            self.assertGreaterEqual(studio.binding_scroll.minimumHeight(), 132)
            self.assertGreaterEqual(
                studio.findChild(QFrame, "slidePreviewCard").minimumWidth(), 480
            )
            for card_name in (
                "slidePreviewCard",
                "shapeListCard",
                "shapeBindingCard",
                "mappedLayoutsCard",
            ):
                self.assertIsNotNone(studio.findChild(QFrame, card_name))

            stylesheet = build_stylesheet(LIGHT)
            group_title_style = stylesheet.split("QGroupBox::title", 1)[1].split(
                "}", 1
            )[0]
            self.assertIn(f"background: {LIGHT.surface};", group_title_style)

            window.navigate("reports")
            window.reports_page.show_presentation_output()
            window.resize(window.minimumSize())
            self.app.processEvents()
            self.assertGreaterEqual(page.output_splitter.sizes()[0], 560)
            self.assertGreaterEqual(page.output_splitter.sizes()[1], 400)
            for button in (
                page.split_group_button,
                page.merge_next_button,
                page.move_up_button,
                page.move_down_button,
                page.remove_page_button,
                page.include_page_button,
            ):
                self.assertGreaterEqual(button.width(), button.sizeHint().width())
        finally:
            window.close()

    def test_presentations_page_maps_multiple_procedure_content_regions(self) -> None:
        page = PresentationsPage()
        page.set_project_open(True)
        page.set_analysis(
            {
                "template": {
                    "slideCount": 1,
                    "slideSize": {"cx": 100, "cy": 50},
                    "sha256": "b" * 64,
                },
                "warnings": [],
                "slides": [
                    {
                        "number": 1,
                        "shapes": [
                            {"id": 2, "name": "Left step", "kind": "text", "text": "STEP 1"},
                            {"id": 4, "name": "Middle step", "kind": "text", "text": "STEP 2"},
                            {"id": 6, "name": "Right step", "kind": "text", "text": "STEP 3"},
                        ],
                    }
                ],
            }
        )
        page.set_profile(
            {
                "formatVersion": 4,
                "id": "two-up",
                "name": "Two up",
                "templateHash": "b" * 64,
                "families": [],
                "storyRecipe": {"document": [], "finding": [], "appendix": []},
                "layouts": [],
            }
        )
        page.role_combo.setCurrentIndex(page.role_combo.findData("finding-procedure"))
        self.assertFalse(page.item_capacity_spin.isHidden())
        page.item_capacity_spin.setValue(3)
        page.family_combo.setEditText("procedure")

        page.shape_table.selectRow(0)
        page.item_index_combo.setCurrentIndex(page.item_index_combo.findData(0))
        page.slot_combo.setCurrentIndex(page.slot_combo.findData("items.0.stepTitle"))
        page.bind_shape_button.click()

        page.shape_table.selectRow(1)
        page.item_index_combo.setCurrentIndex(page.item_index_combo.findData(1))
        page.slot_combo.setCurrentIndex(page.slot_combo.findData("items.1.stepTitle"))
        page.bind_shape_button.click()

        page.shape_table.selectRow(2)
        page.item_index_combo.setCurrentIndex(page.item_index_combo.findData(2))
        page.slot_combo.setCurrentIndex(page.slot_combo.findData("items.2.stepTitle"))
        page.bind_shape_button.click()
        page.update_layout_button.click()

        profile = page.profile_value()
        self.assertIsNotNone(profile)
        layout = profile["layouts"][0]
        self.assertEqual(layout["composition"]["itemCapacity"], 3)
        self.assertEqual(layout["capacity"]["items"], 3)
        self.assertEqual(layout["bindings"]["items.0.stepTitle"]["shapeId"], 2)
        self.assertEqual(layout["bindings"]["items.1.stepTitle"]["shapeId"], 4)
        self.assertEqual(layout["bindings"]["items.2.stepTitle"]["shapeId"], 6)

        single = {
            **layout,
            "id": "procedure-single",
            "composition": {"itemCapacity": 1},
            "capacity": {"items": 1, "evidence": 0},
            "bindings": {
                key: value
                for key, value in layout["bindings"].items()
                if key.startswith("items.0.")
            },
        }
        pair = {
            **layout,
            "id": "procedure-pair",
            "composition": {"itemCapacity": 2},
            "capacity": {"items": 2, "evidence": 0},
            "bindings": {
                key: value
                for key, value in layout["bindings"].items()
                if key.startswith(("items.0.", "items.1."))
            },
        }
        profile["layouts"].extend((single, pair))
        page.set_profile(profile)
        page.set_plan(
            {
                "formatVersion": 2,
                "templateHash": "b" * 64,
                "reportIrHash": "c" * 64,
                "profileHash": "d" * 64,
                "pages": [
                    {
                        "id": "group-page",
                        "semanticKey": "finding:WEB-01-001:procedure:group:1+2",
                        "role": "finding-procedure",
                        "layoutId": layout["id"],
                        "values": {"id": "WEB-01-001"},
                        "evidence": [],
                        "blocks": [
                            {"id": "STEP-001", "kind": "procedure-step", "values": {"stepTitle": "STEP 1"}, "evidence": []},
                            {"id": "STEP-002", "kind": "procedure-step", "values": {"stepTitle": "STEP 2"}, "evidence": []},
                            {"id": "STEP-003", "kind": "procedure-step", "values": {"stepTitle": "STEP 3"}, "evidence": []},
                        ],
                        "overrides": {},
                    }
                ],
            }
        )
        page.split_group_button.click()
        self.assertEqual(len(page.plan_value()["pages"]), 3)
        page.merge_next_button.click()
        self.assertEqual(len(page.plan_value()["pages"]), 2)
        self.assertEqual(len(page.plan_value()["pages"][0]["blocks"]), 2)

    def test_presentation_step_number_formatter_is_editable_and_repeated(self) -> None:
        page = PresentationsPage()
        page.set_project_open(True)
        page.set_analysis(
            {
                "template": {
                    "slideCount": 1,
                    "slideSize": {"cx": 100, "cy": 50},
                    "sha256": "b" * 64,
                },
                "warnings": [],
                "slides": [
                    {
                        "number": 1,
                        "shapes": [
                            {"id": 2, "name": "Step one", "kind": "text", "text": "1"},
                            {"id": 4, "name": "Step two", "kind": "text", "text": "2"},
                        ],
                    }
                ],
            }
        )
        page.set_profile(
            {
                "formatVersion": 4,
                "id": "formatter",
                "name": "Formatter",
                "templateHash": "b" * 64,
                "families": [],
                "storyRecipe": {"document": [], "finding": [], "appendix": []},
                "layouts": [],
            }
        )
        page.role_combo.setCurrentIndex(
            page.role_combo.findData("finding-procedure")
        )
        page.item_capacity_spin.setValue(2)
        page.family_combo.setEditText("procedure")

        page.shape_table.selectRow(0)
        page.item_index_combo.setCurrentIndex(page.item_index_combo.findData(0))
        page.slot_combo.setCurrentIndex(
            page.slot_combo.findData("items.0.stepNumber")
        )
        self.assertFalse(page.sequence_format_combo.isHidden())
        page.sequence_format_combo.setCurrentIndex(
            page.sequence_format_combo.findData("step-padded")
        )
        self.assertIn("STEP 01", page.sequence_preview.text())
        page.bind_shape_button.click()

        page.shape_table.selectRow(1)
        page.item_index_combo.setCurrentIndex(page.item_index_combo.findData(1))
        page.slot_combo.setCurrentIndex(
            page.slot_combo.findData("items.1.stepNumber")
        )
        self.assertEqual(page.sequence_format_combo.currentData(), "step-padded")
        page.bind_shape_button.click()
        page.update_layout_button.click()

        bindings = page.profile_value()["layouts"][0]["bindings"]
        self.assertEqual(
            bindings["items.0.stepNumber"]["formatter"],
            bindings["items.1.stepNumber"]["formatter"],
        )
        self.assertEqual(
            bindings["items.0.stepNumber"]["formatter"]["padding"], 2
        )

        page.sequence_format_combo.setCurrentIndex(
            page.sequence_format_combo.findData("custom")
        )
        page.sequence_custom_edit.setText("STEP {value}")
        self.assertFalse(page.bind_shape_button.isEnabled())
        page.sequence_custom_edit.setText("절차 {number}")
        self.assertTrue(page.bind_shape_button.isEnabled())
        self.assertIn("절차 1", page.sequence_preview.text())

    def test_presentation_scope_and_evidence_slot_labels_are_explicit(self) -> None:
        self.controller.create_target(
            "WEB-02",
            "Admin Portal",
            "https://admin.example.test",
            "Production",
        )
        self._create_finding("Scoped finding")
        snapshot = self.controller.snapshot()
        page = PresentationsPage(mode="output")
        page.set_project_open(True)
        page.set_project_data(snapshot, {})
        self.assertIn("대상 2개", page.scope_summary.text())
        self.assertEqual(page.scope_mode_label.text(), "전체 대상 2개 포함")
        self.assertEqual(page.scope_select_button.text(), "대상 변경")
        self.assertFalse(hasattr(page, "scope_combo"))
        page._scope_mode = "selected-targets"
        page._selected_target_ids = ["WEB-02"]
        page._update_scope_summary()
        self.assertEqual(
            page.presentation_scope(),
            {"mode": "selected-targets", "targetIds": ["WEB-02"]},
        )
        self.assertIn("대상 1개", page.scope_summary.text())
        self.assertEqual(page.scope_mode_label.text(), "선택 대상 1/2개 포함")

        studio = PresentationsPage(mode="studio")
        studio.role_combo.setCurrentIndex(
            studio.role_combo.findData("finding-procedure")
        )
        self.assertEqual(
            studio._slot_label("items.0.evidence.0"),
            "콘텐츠 1 · 증적 이미지 1",
        )
        self.assertEqual(
            studio._slot_label("items.1.evidence.3"),
            "콘텐츠 2 · 증적 이미지 4",
        )

    def test_management_tables_enable_multi_row_selection(self) -> None:
        self._create_finding("First")
        self._create_finding("Second")
        window = MainWindow(controller=self.controller)
        try:
            for table in (
                window.targets_page.table,
                window.findings_page.table,
                window.evidence_page.table,
                window.credentials_page.table,
                window.knowledge_page.table,
                window.archive_page.table,
                window.presentation_output_page.plan_table,
            ):
                self.assertEqual(
                    table.selectionMode(),
                    QAbstractItemView.SelectionMode.ExtendedSelection,
                )
            selection = window.findings_page.table.selectionModel()
            selection.select(
                window.findings_page.proxy.index(0, 0),
                QItemSelectionModel.SelectionFlag.Select
                | QItemSelectionModel.SelectionFlag.Rows,
            )
            selection.select(
                window.findings_page.proxy.index(1, 0),
                QItemSelectionModel.SelectionFlag.Select
                | QItemSelectionModel.SelectionFlag.Rows,
            )
            self.assertEqual(len(window.findings_page.selected_finding_ids()), 2)
            self.assertFalse(window.findings_page.open_button.isEnabled())
            self.assertTrue(window.findings_page.archive_selected_button.isEnabled())
        finally:
            window.close()

    def test_shared_library_workspace_has_explicit_selection_and_restores_project_header(self) -> None:
        window = MainWindow(controller=self.controller)
        try:
            project_title = window.project_label.text()
            project_meta = window.project_meta.text()
            window.navigate("knowledge")
            self.assertEqual(window.project_label.text(), "취약점 라이브러리")
            self.assertIn("모든 프로젝트", window.project_meta.text())
            self.assertEqual(window.knowledge_page.selected_template_ids(), [])
            self.assertFalse(window.knowledge_page.open_button.isEnabled())

            window.navigate("dashboard")
            self.assertEqual(window.project_label.text(), project_title)
            self.assertEqual(window.project_meta.text(), project_meta)
        finally:
            window.close()

    def test_deliverables_use_ordered_workflow_and_unchecked_metrics(self) -> None:
        window = MainWindow(controller=self.controller)
        try:
            page = window.reports_page
            self.assertEqual(
                [page.tabs.tabText(index) for index in range(page.tabs.count())],
                [
                    "준비 상태",
                    "기본 정보",
                    "문제 목록",
                    "문서·데이터",
                    "PPT 생성·검토",
                    "외부 연동",
                ],
            )
            self.assertEqual(page.error_card.value_label.text(), "—")
            self.assertEqual(page.warning_card.value_label.text(), "—")
            self.assertEqual(page.error_card.helper_label.text(), "검사 전")
            page.overview_documents_button.click()
            self.assertEqual(page.tabs.currentWidget(), page.documents_tab)
            page.overview_ppt_button.click()
            self.assertEqual(
                page.tabs.currentWidget(), window.presentation_output_page
            )
        finally:
            window.close()

    def test_evidence_table_uses_finding_scoped_reference(self) -> None:
        finding = self._create_finding("Scoped evidence reference")
        source = Path(self.temporary.name) / "scoped.png"
        source.write_bytes(b"scoped-evidence")
        evidence = self.controller.add_evidence(
            finding.id,
            source,
            "Scoped evidence",
            "screenshot",
            "Composite identifier test",
            "report-ready",
        )
        window = MainWindow(controller=self.controller)
        try:
            self.assertEqual(window.evidence_page.proxy.rowCount(), 1)
            self.assertEqual(
                window.evidence_page.proxy.index(0, 0).data(),
                f"{finding.id} / {evidence.id}",
            )
            self.assertEqual(
                window.evidence_page.proxy.headerData(
                    0,
                    Qt.Orientation.Horizontal,
                    Qt.ItemDataRole.DisplayRole,
                ),
                "증적 ID",
            )
            self.assertEqual(
                window.findings_page.proxy.headerData(
                    0,
                    Qt.Orientation.Horizontal,
                    Qt.ItemDataRole.DisplayRole,
                ),
                "ID",
            )
        finally:
            window.close()

    def test_template_studio_uses_one_navigation_and_collapses_order_editor(self) -> None:
        page = PresentationsPage(mode="studio")
        page.show()
        self.app.processEvents()
        try:
            self.assertTrue(page.tabs.tabBar().isHidden())
            self.assertTrue(page.recipe_controls_widget.isHidden())
            page.story_edit_button.click()
            self.assertFalse(page.recipe_controls_widget.isHidden())
            self.assertEqual(page.story_edit_button.text(), "편집 닫기")
            page.story_edit_button.click()
            self.assertTrue(page.recipe_controls_widget.isHidden())
        finally:
            page.close()

    def test_presentations_page_uses_english_language_pack(self) -> None:
        configure_localization("en-US")
        try:
            page = PresentationsPage()
            self.assertEqual(page.tabs.tabText(0), "Template management")
            self.assertEqual(page.tabs.tabText(1), "Content mapping")
            self.assertEqual(page.tabs.tabText(2), "Slide order")
            self.assertEqual(
                page.role_combo.itemText(page.role_combo.findData("finding-overview")),
                "Finding overview",
            )
            self.assertEqual(
                page.fit_combo.itemText(page.fit_combo.findData("contain")),
                "Fit entire image",
            )
        finally:
            configure_localization("ko-KR")


if __name__ == "__main__":
    unittest.main()
