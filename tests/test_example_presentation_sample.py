from __future__ import annotations

import json
import unittest
from pathlib import Path

from examples.manual_w_sample_data import FINDINGS, iter_step_evidence_specs


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class ExamplePresentationSampleTests(unittest.TestCase):
    def test_every_procedure_and_result_has_evidence(self) -> None:
        procedure_counts = [
            sum(1 for _ in iter_step_evidence_specs(step))
            for finding in FINDINGS
            for step in finding["steps"]
        ]

        self.assertTrue(procedure_counts)
        self.assertTrue(all(count >= 1 for count in procedure_counts))
        self.assertTrue(all(finding.get("result") for finding in FINDINGS))

    def test_sample_uses_approved_w_library_records(self) -> None:
        catalog = json.loads(
            (REPOSITORY_ROOT / "otter-knowledge-complete.json").read_text(
                encoding="utf-8"
            )
        )
        approved = {
            item["id"]: item
            for item in catalog["templates"]
            if item.get("status") == "Approved"
        }
        for finding in FINDINGS:
            record = approved[finding["library_id"]]
            self.assertRegex(finding["library_id"], r"^W-\d+$")
            self.assertEqual(record["name"], finding["library_name"])


if __name__ == "__main__":
    unittest.main()
