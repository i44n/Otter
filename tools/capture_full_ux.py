"""Capture the primary Otter workflows for repeatable visual UX review."""

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


DEFAULT_SAMPLE = REPOSITORY_ROOT / "examples" / "generated" / "w-library-e2e"


def _settle(app) -> None:
    app.processEvents()
    QTest.qWait(80)
    app.processEvents()


def _capture(window: MainWindow, app, output: Path, name: str) -> Path:
    _settle(app)
    destination = output / f"{name}.png"
    if not window.grab().toImage().save(str(destination), "PNG"):
        raise RuntimeError(f"Unable to save screenshot: {destination}")
    return destination


def _presentation_entry(window: MainWindow, sample: Path) -> tuple[dict, dict, dict]:
    presentation = sample / "presentation"
    template = presentation / "northstar-w-library-template.pptx"
    profile_path = presentation / "northstar-w-library-profile.json"
    plan_path = presentation / "full-scope-render-plan.json"
    analysis = window.controller.analyze_presentation_template(template)
    profile = window.controller.load_presentation_profile(profile_path)
    plan = window.controller.load_presentation_plan(plan_path)
    return (
        {
            "id": "manual-w-e2e",
            "name": "Northstar W 라이브러리 다양성 E2E",
            "status": "ready",
            "layoutCount": len(profile.get("layouts", [])),
            "templatePath": str(template.resolve()),
            "profilePath": str(profile_path.resolve()),
        },
        {"analysis": analysis, "profile": profile, "template": template, "profilePath": profile_path},
        plan,
    )


def _load_presentation(page, entry: dict, values: dict, plan: dict | None = None) -> None:
    page.set_template_library([entry])
    if hasattr(page, "library_table") and page.library_table.rowCount():
        page.library_table.selectRow(0)
    page.set_path("template", str(values["template"].resolve()))
    page.set_analysis(values["analysis"])
    page.set_path("profile", str(values["profilePath"].resolve()))
    page.set_profile(values["profile"])
    if plan is not None:
        page.set_plan(plan)
        page.set_plan_status({"state": "current", "isCurrent": True, "changed": []})


def capture(sample: Path, output: Path) -> tuple[Path, ...]:
    project = sample / "project"
    knowledge = sample / "knowledge.db"
    required = (
        project / "project.json",
        knowledge,
        sample / "presentation" / "full-scope-render-plan.json",
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError("Missing sample files: " + ", ".join(missing))

    output.mkdir(parents=True, exist_ok=True)
    settings = QSettings("Otter", "Otter")
    locale_existed = settings.contains("appearance/uiLanguage")
    previous_locale = settings.value("appearance/uiLanguage")
    dark_existed = settings.contains("appearance/darkMode")
    previous_dark = settings.value("appearance/darkMode")
    settings.setValue("appearance/uiLanguage", "ko-KR")
    settings.setValue("appearance/darkMode", False)
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
        entry, presentation, plan = _presentation_entry(window, sample)
        _load_presentation(window.presentations_page, entry, presentation)
        _load_presentation(window.presentation_output_page, entry, presentation, plan)

        for index, key in enumerate(("dashboard", "targets", "findings", "evidence"), start=1):
            if key == "findings":
                window.findings_page.show_list()
            if key == "evidence":
                window.evidence_page.show_list()
            window.navigate(key)
            created.append(_capture(window, app, output, f"{index:02d}-{key}-list"))

        if window.snapshot and window.snapshot.findings:
            window.navigate("findings")
            window.findings_page.select_finding(window.snapshot.findings[0].id)
            created.append(_capture(window, app, output, "05-finding-detail"))

        evidence_groups = window.evidence_page.entries_by_finding()
        first_entry = next((items[0] for items in evidence_groups.values() if items), None)
        if first_entry is not None:
            window.open_evidence_detail(
                first_entry.evidence.finding_id,
                first_entry.evidence.id,
            )
            created.append(_capture(window, app, output, "06-evidence-detail"))

        window.navigate("credentials")
        created.append(_capture(window, app, output, "07-credentials"))

        window.navigate("knowledge")
        window.knowledge_page.show_list()
        created.append(_capture(window, app, output, "08-knowledge-list"))
        if window.knowledge_page.proxy.rowCount():
            window.knowledge_page.table.selectRow(0)
            window.knowledge_page._open_selected()
            created.append(_capture(window, app, output, "09-knowledge-detail"))

        window.reports_page.set_issues(window.controller.validate())
        window.navigate("reports")
        for tab_index in range(window.reports_page.tabs.count()):
            window.reports_page.tabs.setCurrentIndex(tab_index)
            created.append(
                _capture(window, app, output, f"{10 + tab_index:02d}-reports-{tab_index + 1}")
            )

        window.navigate("presentations")
        for tab_index in range(window.presentations_page.tabs.count()):
            if not window.presentations_page.tabs.isTabVisible(tab_index):
                continue
            window.presentations_page.tabs.setCurrentIndex(tab_index)
            created.append(
                _capture(window, app, output, f"{16 + tab_index:02d}-templates-{tab_index + 1}")
            )

        window.navigate("archive")
        created.append(_capture(window, app, output, "19-archive"))

        window.navigate("settings")
        for tab_index in range(window.settings_page.tabs.count()):
            window.settings_page.tabs.setCurrentIndex(tab_index)
            created.append(
                _capture(window, app, output, f"{20 + tab_index:02d}-settings-{tab_index + 1}")
            )

        window.resize(1440, 810)
        window.navigate("dashboard")
        created.append(_capture(window, app, output, "22-minimum-dashboard"))
        window.set_dark_mode(True)
        created.append(_capture(window, app, output, "23-dark-dashboard"))
    finally:
        if window is not None:
            window.close()
        if locale_existed:
            settings.setValue("appearance/uiLanguage", previous_locale)
        else:
            settings.remove("appearance/uiLanguage")
        if dark_existed:
            settings.setValue("appearance/darkMode", previous_dark)
        else:
            settings.remove("appearance/darkMode")
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
