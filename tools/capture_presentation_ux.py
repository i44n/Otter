"""Capture the PowerPoint template and project-output workflows for visual QA."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from webpentestkit.qt_gui.app import create_application  # noqa: E402
from webpentestkit.qt_gui.main_window import MainWindow  # noqa: E402


DEFAULT_SAMPLE = (
    REPOSITORY_ROOT
    / "examples"
    / "generated"
    / "w-library-e2e"
)


def _settle(app) -> None:
    app.processEvents()
    QTest.qWait(100)
    app.processEvents()


def _save(window: MainWindow, output: Path) -> None:
    image = window.grab().toImage()
    if not image.save(str(output), "PNG"):
        raise RuntimeError(f"Unable to save screenshot: {output}")


def capture(sample: Path, output: Path) -> tuple[Path, ...]:
    project = sample / "project"
    knowledge = sample / "knowledge.db"
    presentation = sample / "presentation"
    template = presentation / "northstar-w-library-template.pptx"
    profile = presentation / "northstar-w-library-profile.json"
    plan = presentation / "full-scope-render-plan.json"
    required = (project / "project.json", knowledge, template, profile, plan)
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError("Missing presentation sample files: " + ", ".join(missing))

    output.mkdir(parents=True, exist_ok=True)
    settings = QSettings("Otter", "Otter")
    locale_existed = settings.contains("appearance/uiLanguage")
    previous_locale = settings.value("appearance/uiLanguage")
    dark_mode_existed = settings.contains("appearance/darkMode")
    previous_dark_mode = settings.value("appearance/darkMode")
    splitter_existed = settings.contains("presentations/mappingEditorSplitterStateV2")
    previous_splitter = settings.value("presentations/mappingEditorSplitterStateV2")
    settings.setValue("appearance/uiLanguage", "ko-KR")
    settings.setValue("appearance/darkMode", False)
    settings.remove("presentations/mappingEditorSplitterStateV2")
    settings.sync()

    created: list[Path] = []
    window: MainWindow | None = None
    try:
        app = create_application([])
        window = MainWindow(project, knowledge)
        window.resize(1800, 1000)
        window.show()
        window.toast.hide()
        _settle(app)

        analysis = window.controller.analyze_presentation_template(template)
        profile_value = window.controller.load_presentation_profile(profile)
        entry = {
            "id": "w-library-e2e",
            "name": "Northstar W 라이브러리 다양성 E2E",
            "status": "ready",
            "layoutCount": len(profile_value.get("layouts", [])),
            "templatePath": str(template.resolve()),
            "profilePath": str(profile.resolve()),
        }

        studio = window.presentations_page
        studio.set_template_library([entry])
        studio.set_path("template", str(template.resolve()))
        studio.set_analysis(analysis)
        studio.set_path("profile", str(profile.resolve()))
        studio.set_profile(profile_value)
        studio.library_table.selectRow(0)
        window.navigate("presentations")
        studio.tabs.setCurrentIndex(0)
        _settle(app)
        destination = output / "01-template-library.png"
        _save(window, destination)
        created.append(destination)

        studio.tabs.setCurrentIndex(1)
        _settle(app)
        destination = output / "02-content-mapping.png"
        _save(window, destination)
        created.append(destination)

        formatter_layout = next(
            (
                layout
                for layout in profile_value.get("layouts", [])
                if any(
                    str(slot).endswith(".stepNumber") or slot == "stepNumber"
                    for slot in layout.get("bindings", {})
                )
            ),
            None,
        )
        if formatter_layout is not None:
            layout_index = studio.layout_combo.findData(formatter_layout["id"])
            if layout_index >= 0:
                studio.layout_combo.setCurrentIndex(layout_index)
                step_slot, step_binding = next(
                    (
                        (slot, binding)
                        for slot, binding in formatter_layout["bindings"].items()
                        if str(slot).endswith(".stepNumber") or slot == "stepNumber"
                    )
                )
                studio._select_shape_by_id(int(step_binding["shapeId"]))
                studio.slot_combo.setCurrentIndex(
                    studio.slot_combo.findData(str(step_slot))
                )
                studio.sequence_format_combo.setCurrentIndex(
                    studio.sequence_format_combo.findData("step-padded")
                )
                _settle(app)
                studio.binding_scroll.ensureWidgetVisible(
                    studio.sequence_preview, 0, 24
                )
                _settle(app)
                destination = output / "02b-step-number-format.png"
                _save(window, destination)
                created.append(destination)

        studio.tabs.setCurrentIndex(2)
        _settle(app)
        destination = output / "03-slide-order.png"
        _save(window, destination)
        created.append(destination)

        window.navigate("reports")
        window.reports_page.show_presentation_output()
        output_page = window.presentation_output_page
        output_page.set_template_library([entry])
        output_page.output_template_combo.blockSignals(True)
        output_page.output_template_combo.setCurrentIndex(1)
        output_page.output_template_combo.blockSignals(False)
        output_page.set_path("template", str(template.resolve()))
        output_page.set_analysis(analysis)
        output_page.set_path("profile", str(profile.resolve()))
        output_page.set_profile(profile_value)
        _settle(app)
        destination = output / "04-project-draft-empty.png"
        _save(window, destination)
        created.append(destination)

        output_page._scope_mode = "selected-targets"
        output_page._selected_target_ids = [
            item["id"] for item in output_page._scope_targets[:2]
        ]
        output_page._update_scope_summary()
        output_page._update_preflight()
        _settle(app)
        destination = output / "04b-project-selected-scope.png"
        _save(window, destination)
        created.append(destination)

        output_page.set_path("plan", str(plan.resolve()))
        output_page.set_plan(window.controller.load_presentation_plan(plan))
        output_page.set_plan_status(
            {"state": "current", "isCurrent": True, "changed": []}
        )
        _settle(app)
        destination = output / "05-project-draft-review.png"
        _save(window, destination)
        created.append(destination)

        for row in range(output_page.plan_table.rowCount()):
            output_page.plan_table.selectRow(row)
            _settle(app)
            if not output_page.slide_adjustment_button.isHidden():
                break
        if not output_page.slide_adjustment_button.isHidden():
            output_page.slide_adjustment_button.click()
            _settle(app)
            destination = output / "06-slide-fine-tuning.png"
            _save(window, destination)
            created.append(destination)

        output_page.slide_adjustment_button.setChecked(False)
        window.resize(1440, 810)
        _settle(app)
        destination = output / "07-minimum-window.png"
        _save(window, destination)
        created.append(destination)

        window.resize(1800, 1000)
        window.set_dark_mode(True)
        window.navigate("presentations")
        studio.tabs.setCurrentIndex(1)
        _settle(app)
        destination = output / "08-dark-content-mapping.png"
        _save(window, destination)
        created.append(destination)

        window.navigate("reports")
        window.reports_page.show_presentation_output()
        _settle(app)
        destination = output / "09-dark-project-output.png"
        _save(window, destination)
        created.append(destination)
    finally:
        if window is not None:
            window.close()
        if locale_existed:
            settings.setValue("appearance/uiLanguage", previous_locale)
        else:
            settings.remove("appearance/uiLanguage")
        if dark_mode_existed:
            settings.setValue("appearance/darkMode", previous_dark_mode)
        else:
            settings.remove("appearance/darkMode")
        if splitter_existed:
            settings.setValue(
                "presentations/mappingEditorSplitterStateV2", previous_splitter
            )
        else:
            settings.remove("presentations/mappingEditorSplitterStateV2")
        settings.sync()
    return tuple(created)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", type=Path, default=DEFAULT_SAMPLE)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    for path in capture(args.sample.resolve(), args.output.resolve()):
        print(f"Captured: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
