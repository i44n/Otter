"""Open the generated ACME sample with its dedicated knowledge database."""

from __future__ import annotations

import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from webpentestkit.qt_gui.app import run  # noqa: E402


def main() -> int:
    sample = Path(__file__).resolve().parent / "generated" / "acme-shop"
    project = sample / "project"
    knowledge = sample / "knowledge.db"
    if not (project / "project.json").is_file() or not knowledge.is_file():
        raise SystemExit(
            "Sample data is missing. Run: python examples/create_sample.py --force"
        )
    return run(project, knowledge)


if __name__ == "__main__":
    raise SystemExit(main())
