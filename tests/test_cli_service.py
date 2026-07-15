from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from webpentestkit.cli import main


class CliServiceIntegrationTest(unittest.TestCase):
    def run_cli(self, *arguments: str) -> tuple[int, str]:
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            result = main(list(arguments))
        return result, output.getvalue()

    def test_cli_uses_service_layer_for_complete_record(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            code, _ = self.run_cli(
                "init",
                "--project-id",
                "CLI-SERVICE",
                "--name",
                "CLI Service Test",
                "--path",
                str(project),
            )
            self.assertEqual(code, 0)
            code, _ = self.run_cli(
                "target",
                "add",
                "--project",
                str(project),
                "--id",
                "WEB-01",
                "--name",
                "Portal",
                "--url",
                "https://portal.example.test",
            )
            self.assertEqual(code, 0)
            code, _ = self.run_cli(
                "finding",
                "add",
                "--project",
                str(project),
                "--target",
                "WEB-01",
                "--title",
                "Object authorization missing",
                "--severity",
                "High",
                "--category",
                "Access Control",
            )
            self.assertEqual(code, 0)
            code, _ = self.run_cli(
                "finding",
                "update",
                "--project",
                str(project),
                "--id",
                "WEB-01-001",
                "--cwe",
                "CWE-639",
                "--tester",
                "CLI Tester",
                "--discovered-at",
                "2026-07-15",
                "--summary",
                "Another user's object can be retrieved.",
                "--impact",
                "Private data can be disclosed.",
                "--remediation",
                "Authorize access to each requested object.",
                "--template-id",
                "WPK-ACCESS-001",
                "--template-version",
                "2",
            )
            self.assertEqual(code, 0)
            code, _ = self.run_cli(
                "finding",
                "status",
                "--project",
                str(project),
                "--id",
                "WEB-01-001",
                "--status",
                "Confirmed",
            )
            self.assertEqual(code, 0)

            finding_path = next(project.glob("targets/*/findings/*/finding.json"))
            finding = json.loads(finding_path.read_text(encoding="utf-8"))
            self.assertEqual(finding["tester"], "CLI Tester")
            self.assertEqual(finding["status"], "Confirmed")
            self.assertEqual(
                finding["template"], {"id": "WPK-ACCESS-001", "version": 2}
            )

            code, validation = self.run_cli("validate", "--project", str(project))
            self.assertEqual(code, 0)
            self.assertIn("Errors: 0", validation)


if __name__ == "__main__":
    unittest.main()
