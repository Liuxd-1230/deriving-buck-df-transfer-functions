import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = ROOT / "scripts" / "preflight_intake.py"
DF_CLI = ROOT / "scripts" / "df_buck_sympy.py"


class ForwardPromptTests(unittest.TestCase):
    def test_valley_voltage_cot_stops_before_derivation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            status_path = root / "intake_status.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(PREFLIGHT),
                    "--text",
                    str(ROOT / "tests" / "fixtures" / "forward_valley_vcot.txt"),
                    "--out",
                    str(status_path),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                timeout=30,
            )
            self.assertTrue(status_path.is_file(), result.stderr)
            status = json.loads(status_path.read_text(encoding="utf-8"))

            self.assertEqual(result.returncode, 2)
            self.assertEqual(status["action"], "ASK_USER_ONLY")
            self.assertNotIn("transfer_function", status)
            self.assertNotIn("proof_object", status)
            self.assertEqual(list(root.glob("*.png")), [])

    def test_engineering_valley_cm_cot_case_keeps_tloop_and_validity_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = json.loads(
                (ROOT / "examples" / "intake_valley_cm_cot_tloop.json").read_text(encoding="utf-8")
            )
            missing = dict(fixture)
            missing.pop("loop_break")
            missing_path = root / "missing.json"
            missing_status = root / "missing_status.json"
            missing_path.write_text(json.dumps(missing), encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable, str(PREFLIGHT), "--intake", str(missing_path),
                    "--out", str(missing_status),
                ],
                cwd=ROOT, text=True, capture_output=True, timeout=30,
            )
            self.assertEqual(result.returncode, 2)
            self.assertEqual(
                json.loads(missing_status.read_text(encoding="utf-8"))["status"],
                "INCOMPLETE_TLOOP_INTAKE",
            )

            params = root / "params.json"
            case = root / "case.json"
            plots = root / "plots"
            params.write_text(json.dumps(fixture["parameters"]), encoding="utf-8")
            made = subprocess.run(
                [
                    sys.executable, str(DF_CLI), "make-case", "--model", "cot-cm-li-lee-2010",
                    "--params", str(params), "--approximation", "pade", "--out", str(case),
                ],
                cwd=ROOT, text=True, capture_output=True, timeout=30,
            )
            self.assertEqual(made.returncode, 0, made.stderr)
            data = json.loads(case.read_text(encoding="utf-8"))
            data["targets"] = ["Gvc", "Tloop"]
            data["feedback"] = {
                "Gc": "8000*(s+1*4000)/((s+1*50)*(s+1*400000))",
                "H": "1",
                "loop_break": fixture["loop_break"],
                "formula_origin": "compensator-template:SIMPLIS_LAPLACE",
            }
            case.write_text(json.dumps(data), encoding="utf-8")
            plotted = subprocess.run(
                [
                    sys.executable, str(DF_CLI), "plot-bode", "--case", str(case),
                    "--targets", "Gvc,Tloop", "--out", str(plots),
                ],
                cwd=ROOT, text=True, capture_output=True, timeout=60,
            )
            self.assertEqual(plotted.returncode, 0, plotted.stderr)
            summary = json.loads((plots / "bode_summary.json").read_text(encoding="utf-8"))
            self.assertAlmostEqual(summary["fs_half_hz"], fixture["parameters"]["fs"] / 2)
            self.assertEqual(summary["loop_break"]["sign_convention"], "negative_feedback")
            self.assertIn("fs/2", summary["results"]["Tloop"]["plot_markers"])
            crossing = summary["results"]["Tloop"]["zero_db_crossing_hz"]
            if crossing is not None and crossing > summary["valid_frequency_limit_hz"]:
                self.assertEqual(
                    summary["results"]["Tloop"]["validity"],
                    "EXTRAPOLATED_BEYOND_VALID_RANGE",
                )


if __name__ == "__main__":
    unittest.main()
