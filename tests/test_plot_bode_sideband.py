import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "df_buck_sympy.py"


class PlotBodeSidebandTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(CLI), *args], cwd=ROOT,
                              text=True, capture_output=True, timeout=60)

    def test_sampled_data_case_supports_exp_and_truncated_sideband(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            case = root / "sampled_case.json"
            out = root / "plots"
            case.write_text(json.dumps({
                "case_version": "0.4-sampled-data",
                "name": "sampled-exp-sideband",
                "parameters": {"fs": 100000.0, "T0": 2e-6, "K": 3.0},
                "valid_frequency": {"max_hz": 50000.0},
                "transfer_functions": {
                    "Gm": "K*(1-exp(-s*T0))",
                    "GPWM": "K*(1-exp(-s*T0))/(1+0.1*(1/(s+j*ws)+1/(s-j*ws)))"
                },
                "sideband": {"mode": "TRUNCATED_SUM_M", "M": 1},
            }), encoding="utf-8")
            result = self.run_cli("plot-bode", "--case", str(case), "--targets", "Gm,GPWM", "--out", str(out))
            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads((out / "bode_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["evaluator"], "sampled-data-numeric")
            self.assertEqual(summary["sideband"]["mode"], "TRUNCATED_SUM_M")
            self.assertTrue((out / "Gm_bode.csv").is_file())
            self.assertTrue((out / "GPWM_bode.png").is_file())

    def test_symbolic_full_sum_is_rejected_for_numeric_bode(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            case = root / "symbolic_full_sum.json"
            case.write_text(json.dumps({
                "case_version": "0.4-sampled-data",
                "parameters": {"fs": 100000.0, "T0": 2e-6, "K": 3.0},
                "transfer_functions": {"Gm": "K*(1-exp(-s*T0))"},
                "sideband": {"mode": "SYMBOLIC_FULL_SUM"},
            }), encoding="utf-8")
            result = self.run_cli("plot-bode", "--case", str(case), "--targets", "Gm", "--out", str(root / "plots"))
            self.assertEqual(result.returncode, 2)
            self.assertIn("SYMBOLIC_FULL_SUM", result.stderr)


if __name__ == "__main__":
    unittest.main()
