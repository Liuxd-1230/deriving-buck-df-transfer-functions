import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts" / "check_formula_consistency.py"


class FormulaConsistencyTests(unittest.TestCase):
    def test_registry_self_check_passes(self):
        result = subprocess.run(
            [sys.executable, str(CHECKER), "--all"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "PASS")

    def test_registry_contains_canonical_q2_and_required_metadata(self):
        registry_path = ROOT / "registries" / "formula_registry.yaml"
        self.assertTrue(registry_path.is_file())
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        q2 = registry["formulas"]["li-lee-2009.q2"]
        self.assertEqual(q2["canonical_sympy_expr"], "Tsw/(pi*(rC*C-Ton/2))")
        for key in (
            "source_model_id", "interface", "supported_targets", "parameters",
            "dimension_signature", "numeric_probe_values", "source_equation", "approximation",
        ):
            self.assertIn(key, q2)


if __name__ == "__main__":
    unittest.main()
