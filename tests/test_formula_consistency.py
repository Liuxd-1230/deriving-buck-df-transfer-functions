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

    def test_registry_contains_sampled_data_formula_fragments(self):
        registry_path = ROOT / "registries" / "formula_registry.yaml"
        model_registry_path = ROOT / "registries" / "model_registry.yaml"
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        model_registry = json.loads(model_registry_path.read_text(encoding="utf-8"))
        self.assertEqual(registry["registry_version"], "0.4")
        for model_id in (
            "yan-2022-part-i-pcm-buck",
            "yan-2022-part-ii-ccot-buck-zero-ramp",
            "yan-2022-part-ii-vcot-buck-zero-ramp",
        ):
            self.assertIn(model_id, model_registry["models"])
            self.assertEqual(model_registry["models"][model_id]["method"], "sampled-data")
        ccot = registry["formulas"]["yan-2022-part-ii.ccot-gpwm-pulse-factor"]
        self.assertEqual(ccot["canonical_sympy_expr"], "Fm*(1-exp(-s*T0))")
        self.assertEqual(ccot["interface"], "sampled-data-modulator")


if __name__ == "__main__":
    unittest.main()
