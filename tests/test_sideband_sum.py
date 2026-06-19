import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from sideband_sum import build_sideband


class SidebandSumTests(unittest.TestCase):
    def test_symbolic_full_sum_is_not_numeric(self):
        result = build_sideband({"mode": "SYMBOLIC_FULL_SUM", "base_expression": "Gid(s+j*n*ws)"})
        self.assertEqual(result["mode"], "SYMBOLIC_FULL_SUM")
        self.assertFalse(result["numeric_evaluable"])
        self.assertIn("sum", result["sum_expression"])

    def test_truncated_sum_records_m_and_terms(self):
        result = build_sideband({"mode": "TRUNCATED_SUM_M", "base_expression": "1/(s+j*n*ws)", "M": 2})
        self.assertEqual(result["mode"], "TRUNCATED_SUM_M")
        self.assertTrue(result["numeric_evaluable"])
        self.assertEqual(result["M"], 2)
        self.assertEqual(result["indices"], [-2, -1, 1, 2])
        self.assertNotIn(0, result["indices"])
        self.assertIn("nonzero", result["approximation"])

    def test_symbolic_index_substitution_does_not_corrupt_identifiers(self):
        result = build_sideband({
            "mode": "TRUNCATED_SUM_M",
            "base_expression": "Vin/(sin(theta)+den+n*ws)",
            "M": 1,
        })
        expression = result["numeric_expression"]
        self.assertIn("Vin", expression)
        self.assertIn("sin", expression)
        self.assertIn("den", expression)
        self.assertNotIn("Vi(-1)", expression)

    def test_truncated_sum_requires_positive_integer_m(self):
        for bad in (0, -1, 1.5):
            with self.subTest(M=bad), self.assertRaises(ValueError):
                build_sideband({"mode": "TRUNCATED_SUM_M", "base_expression": "n", "M": bad})

    def test_paper_simplified_form_is_numeric_evaluable(self):
        result = build_sideband({"mode": "PAPER_SIMPLIFIED_FORM", "expression": "Fm*(1-exp(-s*Ton))"})
        self.assertEqual(result["mode"], "PAPER_SIMPLIFIED_FORM")
        self.assertTrue(result["numeric_evaluable"])
        self.assertEqual(result["numeric_expression"], "Fm*(1-exp(-s*Ton))")


if __name__ == "__main__":
    unittest.main()
