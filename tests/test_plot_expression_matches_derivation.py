import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.test_plot_derivation_binding import derivation_with_coefficients


ROOT = Path(__file__).resolve().parents[1]
COMPUTE_GVC = ROOT / "scripts" / "compute_gvc.py"


class PlotExpressionMatchesDerivationTests(unittest.TestCase):
    def run_compute(self, derivation: dict):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "derivation.json"
            out = root / "plots"
            source.write_text(json.dumps(derivation), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(COMPUTE_GVC), "--derivation", str(source), "--out-dir", str(out)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                timeout=60,
            )
            manifest = out / "plot_manifest.json"
            return result, json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else None

    def test_manifest_declares_plot_matches_derivation(self) -> None:
        result, manifest = self.run_compute(derivation_with_coefficients())

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(manifest["matches_derivation"])
        self.assertEqual(manifest["source_derivation"], "derivation.json")
        self.assertIn("generated_expression_sha256", manifest)
        self.assertIn("coefficient_expression_sha256", manifest)
        self.assertIn("plot_expression_sha256", manifest)

    def test_plot_expression_mismatch_fails(self) -> None:
        result, _manifest = self.run_compute(derivation_with_coefficients(plot_expression="Gvd*Kmod/(1+Kmod*Hsn)"))

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FAIL_PLOT_EXPRESSION_MISMATCH", result.stderr)


if __name__ == "__main__":
    unittest.main()
