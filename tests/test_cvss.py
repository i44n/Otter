from __future__ import annotations

import unittest

from webpentestkit.cvss import (
    build_cvss31_vector,
    calculate_cvss31,
    cvss31_scores_match,
    parse_cvss31_vector,
)
from webpentestkit.errors import KitError


class Cvss31Test(unittest.TestCase):
    def test_calculates_known_base_vectors(self) -> None:
        vectors = {
            "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H": 9.8,
            "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:N": 8.1,
            "CVSS:3.1/AV:N/AC:L/PR:L/UI:R/S:C/C:H/I:H/A:N": 8.7,
            "CVSS:3.1/AV:P/AC:H/PR:H/UI:R/S:U/C:N/I:N/A:N": 0.0,
        }
        for vector, expected in vectors.items():
            with self.subTest(vector=vector):
                result = calculate_cvss31(vector)
                self.assertEqual(result.score, expected)
                self.assertEqual(result.vector, vector)

    def test_parses_any_metric_order_and_builds_canonical_vector(self) -> None:
        raw = "CVSS:3.1/A:N/I:H/C:L/S:U/UI:N/PR:L/AC:H/AV:A"
        metrics = parse_cvss31_vector(raw)
        self.assertEqual(metrics["AV"], "A")
        self.assertEqual(
            build_cvss31_vector(metrics),
            "CVSS:3.1/AV:A/AC:H/PR:L/UI:N/S:U/C:L/I:H/A:N",
        )

    def test_rejects_missing_unknown_and_duplicate_metrics(self) -> None:
        invalid = (
            "CVSS:3.0/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
            "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H",
            "CVSS:3.1/AV:N/AV:A/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
            "CVSS:3.1/AV:X/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
        )
        for vector in invalid:
            with self.subTest(vector=vector):
                with self.assertRaises(KitError):
                    calculate_cvss31(vector)

    def test_detects_score_vector_mismatch_without_breaking_empty_legacy_values(self) -> None:
        vector = "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:N"
        self.assertTrue(cvss31_scores_match(vector, 8.1))
        self.assertFalse(cvss31_scores_match(vector, 9.1))
        self.assertTrue(cvss31_scores_match("", 9.1))


if __name__ == "__main__":
    unittest.main()
