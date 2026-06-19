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
            for target in ("Gm", "GPWM"):
                self.assertIsNone(summary["results"][target]["phase_margin_deg"])
                self.assertIsNone(summary["results"][target]["gain_margin_db"])
                self.assertEqual(
                    summary["results"][target]["stability_margins_status"],
                    "NOT_APPLICABLE_NON_RETURN_RATIO",
                )
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

    def test_return_ratio_ti_allows_margin_calculation(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            case = root / "ti.json"
            case.write_text(json.dumps({
                "case_version": "0.4-sampled-data",
                "parameters": {"fs": 100000.0, "wp": 10000.0, "K": 10.0},
                "transfer_functions": {"Ti": "K/(1+s/wp)"},
                "response_kinds": {"Ti": "return_ratio"},
                "sideband": {"mode": "PAPER_SIMPLIFIED_FORM", "expression": "K/(1+s/wp)"},
            }), encoding="utf-8")
            result = self.run_cli("plot-bode", "--case", str(case), "--targets", "Ti", "--out", str(root / "plots"))
            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads((root / "plots" / "bode_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["results"]["Ti"]["stability_margins_status"], "APPLICABLE_RETURN_RATIO")

    def test_sampled_gvc_and_tloop_have_distinct_margin_semantics(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            case = root / "gvc_tloop.json"
            case.write_text(json.dumps({
                "case_version": "0.4-sampled-data",
                "parameters": {"fs": 100000.0, "wp": 10000.0, "K": 10.0},
                "valid_frequency": {"max_hz": 50000.0},
                "transfer_functions": {
                    "Gvc": "K/(1+s/wp)",
                    "Tloop": "K/(1+s/wp)"
                },
                "response_kinds": {
                    "Gvc": "transfer_function",
                    "Tloop": "return_ratio"
                },
                "sideband": {"mode": "PAPER_SIMPLIFIED_FORM", "expression": "K/(1+s/wp)"},
            }), encoding="utf-8")
            result = self.run_cli("plot-bode", "--case", str(case), "--targets", "Gvc,Tloop", "--out", str(root / "plots"))
            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads((root / "plots" / "bode_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["results"]["Gvc"]["stability_margins_status"], "NOT_APPLICABLE_NON_RETURN_RATIO")
            self.assertIsNone(summary["results"]["Gvc"]["phase_margin_deg"])
            self.assertEqual(summary["results"]["Tloop"]["stability_margins_status"], "APPLICABLE_RETURN_RATIO")
            self.assertTrue((root / "plots" / "Gvc_bode.csv").is_file())
            self.assertTrue((root / "plots" / "Tloop_bode.png").is_file())


if __name__ == "__main__":
    unittest.main()
