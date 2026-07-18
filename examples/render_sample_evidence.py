"""Render deterministic W-series evidence screenshots from the local fixture page.

The page makes no network requests and contains only fictional, sanitized data.
By default screenshots are written inside the canonical W-library E2E sample.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from urllib.parse import urlencode


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from examples.manual_w_sample_data import iter_evidence_specs  # noqa: E402


SOURCE_PAGE = REPOSITORY_ROOT / "examples" / "sample_evidence_site" / "index.html"
DEFAULT_OUTPUT = (
    REPOSITORY_ROOT
    / "examples"
    / "generated"
    / "w-library-e2e"
    / "evidence-source"
)


def _query(spec: dict) -> str:
    return urlencode(
        {
            "id": spec["library_id"],
            "library": spec["library_name"],
            "finding": spec["finding_title"],
            "title": spec["title"],
            "kind": spec["kind"],
            "mode": spec.get("mode", "api"),
            "severity": spec["severity"],
            "status": spec["status"],
            "step": spec["step_number"],
            "steps": spec["step_count"],
            "actor": spec["actor"],
            "endpoint": spec.get("endpoint", "-"),
            "request": spec.get("request", "-"),
            "response": spec.get("response", "-"),
            "expected": spec.get("expected", "-"),
            "observed": spec.get("observed", spec.get("caption", "-")),
        }
    )


def render(output: Path, *, force: bool = False) -> list[Path]:
    if not SOURCE_PAGE.is_file():
        raise SystemExit(f"Evidence source page not found: {SOURCE_PAGE}")

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault(
        "QTWEBENGINE_CHROMIUM_FLAGS",
        "--disable-gpu --disable-software-rasterizer --no-sandbox",
    )
    os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")

    from PySide6.QtCore import QTimer, QUrl
    from PySide6.QtWidgets import QApplication
    from PySide6.QtWebEngineWidgets import QWebEngineView

    output.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication(sys.argv[:1])
    view = QWebEngineView()
    view.resize(1600, 900)
    view.show()

    pending = list(iter_evidence_specs())
    rendered: list[Path] = []
    failures: list[str] = []

    def load_next() -> None:
        if not pending:
            app.quit()
            return
        spec = pending.pop(0)
        name = str(spec["slug"])
        destination = output / f"{name}.png"
        if destination.exists() and not force:
            rendered.append(destination)
            QTimer.singleShot(0, load_next)
            return
        view.setProperty("evidenceName", name)
        view.setProperty("evidenceDestination", str(destination))
        url = QUrl.fromLocalFile(str(SOURCE_PAGE))
        url.setQuery(_query(spec))
        view.load(url)

    def capture(ok: bool) -> None:
        name = str(view.property("evidenceName") or "")
        if not name:
            return
        destination = Path(str(view.property("evidenceDestination")))
        if not ok:
            failures.append(name)
            QTimer.singleShot(0, load_next)
            return

        def save_frame() -> None:
            image = view.grab()
            if image.width() != 1600 or image.height() != 900:
                failures.append(f"{name}:unexpected-size-{image.width()}x{image.height()}")
            elif not image.save(str(destination), "PNG"):
                failures.append(name)
            else:
                rendered.append(destination)
            QTimer.singleShot(0, load_next)

        QTimer.singleShot(250, save_frame)

    view.loadFinished.connect(capture)
    QTimer.singleShot(0, load_next)
    app.exec()
    view.close()

    if failures:
        raise SystemExit("Failed to render evidence views: " + ", ".join(failures))
    return rendered


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    files = render(args.output.expanduser().resolve(), force=args.force)
    print(f"Rendered {len(files)} W-series evidence screenshots to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
