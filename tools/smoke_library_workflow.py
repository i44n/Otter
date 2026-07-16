from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication

from webpentestkit.errors import KitError
from webpentestkit.gui.controller import GuiController
from webpentestkit.models import VulnerabilityTemplateInput
from webpentestkit.qt_gui.models import TemplateTableModel
from webpentestkit.qt_gui.pages import KnowledgePage


TEMPLATE_ID = "WPK-SMOKE-001"


def _visible_template_ids(page: KnowledgePage) -> list[str]:
    result: list[str] = []
    for row in range(page.proxy.rowCount()):
        index = page.proxy.index(row, 0)
        template = page.proxy.data(index, TemplateTableModel.TemplateRole)
        if template is not None:
            result.append(template.id)
    return result


def main() -> int:
    app = QApplication.instance() or QApplication([])
    summary: dict[str, object] = {"workflow": []}

    temporary_root: Path | None = None
    with tempfile.TemporaryDirectory(prefix="otter-library-smoke-") as temporary:
        root = Path(temporary)
        temporary_root = root
        database = root / "knowledge.db"
        project = root / "project"
        controller = GuiController(database)
        controller.create_project(
            project,
            "SMOKE-001",
            "Library workflow smoke test",
            "Dummy Customer",
        )
        controller.create_target(
            "WEB-01",
            "Dummy Portal",
            "https://dummy.example.test",
            "Test",
        )
        created = controller.add_template_version(
            VulnerabilityTemplateInput(
                id=TEMPLATE_ID,
                name="Dummy object authorization issue",
                english_name="Dummy object authorization issue",
                title="Dummy object authorization issue",
                category="Access Control",
                default_severity="High",
                summary="Another user's object can be requested.",
                impact="Dummy customer data may be exposed.",
                remediation="Check object ownership.",
                cwes=("CWE-639",),
                tags=("Smoke", "IDOR"),
                status="Approved",
            )
        )
        summary["workflow"].append("created template")

        updated = controller.update_template(
            TEMPLATE_ID,
            remediation="Check ownership for every object request.",
            tags=("Smoke", "IDOR", "Updated"),
        )
        assert updated.version == created.version
        assert updated.remediation == "Check ownership for every object request."
        stored_versions = [
            item
            for item in controller.knowledge.repository.list_versions()
            if item.id == TEMPLATE_ID
        ]
        assert len(stored_versions) == 1
        summary["workflow"].append("updated in place without duplicate version")

        finding = controller.create_finding_from_template(
            TEMPLATE_ID,
            "WEB-01",
            title="Dummy profile IDOR",
            status="Confirmed",
            url="https://dummy.example.test/api/profiles/2",
            method="GET",
            parameter="id",
            role="Authenticated user",
            tester="Smoke Tester",
        )
        assert finding.presentation.remediation == updated.remediation
        assert list(project.rglob("finding.json"))
        summary["workflow"].append("created project finding from template")

        controller.close_project()
        reopened = GuiController(database)
        reopened.open_project(project)
        assert reopened.get_template(TEMPLATE_ID).remediation == updated.remediation
        assert reopened.get_finding(finding.id).title == "Dummy profile IDOR"
        summary["workflow"].append("reopened SQLite database and project")

        archived = reopened.archive_template(TEMPLATE_ID)
        assert archived.status == "Deprecated"
        page = KnowledgePage()
        page.set_templates(reopened.search_templates())
        assert TEMPLATE_ID not in _visible_template_ids(page)
        archived_index = page.status_filter.findData("Deprecated")
        assert archived_index >= 0
        page.status_filter.setCurrentIndex(archived_index)
        app.processEvents()
        assert TEMPLATE_ID in _visible_template_ids(page)
        summary["workflow"].append("archived and found through archived filter")

        restored = reopened.restore_template(TEMPLATE_ID)
        assert restored.status == "Approved"
        page.status_filter.setCurrentIndex(0)
        page.set_templates(reopened.search_templates())
        page.open_template(TEMPLATE_ID)
        assert page.detail.template_id == TEMPLATE_ID
        assert page.detail.edit_button.text() == "Edit"
        assert page.detail.apply_button.text() == "Add finding from this template"
        assert page.detail.archive_button.text() == "Archive"
        assert page.detail.delete_button.text() == "Delete"
        summary["workflow"].append("restored original status and opened detail actions")
        page.close()

        reopened.delete_template(TEMPLATE_ID)
        try:
            reopened.get_template(TEMPLATE_ID)
        except KitError as error:
            assert error.code == "TEMPLATE_NOT_FOUND"
        else:
            raise AssertionError("deleted template is still available")
        persisted_finding = reopened.get_finding(finding.id)
        assert persisted_finding.presentation.remediation == updated.remediation
        summary["workflow"].append("deleted template while project finding remained")

        summary.update(
            {
                "database_bytes": database.stat().st_size,
                "project_json_files": len(list(project.rglob("*.json"))),
                "finding_id": finding.id,
                "template_version": updated.version,
                "result": "PASS",
            }
        )

    assert temporary_root is not None and not temporary_root.exists()
    summary["temporary_data_cleaned"] = True
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
