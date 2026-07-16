"""Capture deterministic English screenshots for the public README.

Run ``python examples/create_sample.py --force`` first so every image is based
on the fictional ACME project rather than private assessment data.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from PySide6.QtCore import QSettings, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from webpentestkit.qt_gui.app import create_application  # noqa: E402
from webpentestkit.qt_gui.main_window import MainWindow  # noqa: E402


DEFAULT_SAMPLE = REPOSITORY_ROOT / "examples" / "generated" / "acme-shop"
DEFAULT_OUTPUT = REPOSITORY_ROOT / "docs" / "assets" / "screenshots"
WINDOW_WIDTH = 1440
WINDOW_HEIGHT = 900
OUTPUT_WIDTH = 1200
MAX_IMAGE_BYTES = 250 * 1024


def _capture(widget, output: Path) -> None:
    image = widget.grab().toImage().scaledToWidth(
        OUTPUT_WIDTH,
        Qt.TransformationMode.SmoothTransformation,
    )
    if not image.save(str(output), "PNG", 85):
        raise RuntimeError(f"Unable to save screenshot: {output}")
    if output.stat().st_size > MAX_IMAGE_BYTES:
        raise RuntimeError(
            f"Screenshot exceeds 250 KB ({output.stat().st_size} bytes): {output}"
        )


def _settle(app) -> None:
    app.processEvents()
    QTest.qWait(100)
    app.processEvents()


def capture(sample: Path, output: Path) -> tuple[Path, ...]:
    project = sample / "project"
    knowledge = sample / "knowledge.db"
    if not (project / "project.json").is_file() or not knowledge.is_file():
        raise RuntimeError(
            "The fictional sample is missing. Run: "
            "python examples/create_sample.py --force"
        )

    output.mkdir(parents=True, exist_ok=True)
    settings = QSettings("Otter", "Otter")
    locale_existed = settings.contains("appearance/uiLanguage")
    previous_locale = settings.value("appearance/uiLanguage")
    dark_mode_existed = settings.contains("appearance/darkMode")
    previous_dark_mode = settings.value("appearance/darkMode")
    settings.setValue("appearance/uiLanguage", "en-US")
    settings.setValue("appearance/darkMode", False)
    settings.sync()

    created: list[Path] = []
    window: MainWindow | None = None
    try:
        app = create_application([])
        window = MainWindow(project, knowledge)
        window.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        window.show()
        window.toast.hide()
        _settle(app)

        def save(filename: str, *, full_window: bool = False) -> None:
            _settle(app)
            destination = output / filename
            _capture(window if full_window else window.stack.currentWidget(), destination)
            created.append(destination)

        window.navigate("dashboard")
        window.toast.hide()
        save("otter-dashboard.png", full_window=True)

        window.navigate("findings")
        window.findings_page.select_finding("WEB-03-003")
        window.findings_page.detail.verticalScrollBar().setValue(0)
        save("otter-finding-workspace.png")

        window.findings_page.detail.verticalScrollBar().setValue(
            window.findings_page.detail.verticalScrollBar().maximum()
        )
        save("otter-retest-evidence.png")

        window.navigate("evidence")
        window.open_evidence_detail("WEB-03-003", "EVD-001")
        save("otter-evidence-traceability.png")

        window.navigate("knowledge")
        window.knowledge_page.open_template("WPK-DEMO-API-001")
        save("otter-finding-library.png")

        window.navigate("reports")
        issues = [
            {**item, "path": "project/project.json"}
            for item in window.controller.validate()
        ]
        window.reports_page.set_issues(issues)
        window.reports_page.output_path.setText(
            "Latest output: project/reports"
        )
        window.reports_page.tabs.setCurrentIndex(0)
        save("otter-validation-reports.png")

        window.open_project_protection_settings()
        save("otter-project-protection.png")
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
        settings.sync()
    return tuple(created)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Capture fictional English screenshots for README.md."
    )
    parser.add_argument("--sample", type=Path, default=DEFAULT_SAMPLE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    for path in capture(args.sample.resolve(), args.output.resolve()):
        print(f"Captured: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
