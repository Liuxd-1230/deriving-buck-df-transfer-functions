import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "df_buck_sympy.py"


class PlotBodeTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(CLI), *args], cwd=ROOT,
                              text=True, capture_output=True, timeout=60)

    def make_registered_case(self, root: Path) -> Path:
        params = root / "params.json"
        case = root / "case.json"
        params.write_text(json.dumps({
            "Vin": 36, "Vo": 3.3, "fs": 188034.18803418803,
            "L": 3.3e-6, "C": 2040e-6, "R": 0.094286,
            "rC": 2.23e-3, "Ri": 1 / 30,
        }), encoding="utf-8")
        made = self.run_cli("make-case", "--model", "cot-cm-li-lee-2010",
                            "--params", str(params), "--approximation", "pade",
                            "--out", str(case))
        self.assertEqual(made.returncode, 0, made.stderr)
        return case

    def test_plot_bode_generates_registered_targets_with_fs_half_boundary(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            case = self.make_registered_case(root)
            out = root / "plots"
            result = self.run_cli("plot-bode", "--case", str(case),
                                  "--targets", "Gvc,Gvg,Zout", "--out", str(out))
            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads((out / "bode_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(set(summary["targets"]), {"Gvc", "Gvg", "Zout"})
            self.assertAlmostEqual(summary["fs_hz"], 188034.18803418803)
            self.assertAlmostEqual(summary["valid_frequency_limit_hz"], summary["fs_half_hz"])
            for target in ("Gvc", "Gvg", "Zout"):
                self.assertTrue((out / f"{target}_bode.png").is_file())
                csv_path = out / f"{target}_bode.csv"
                self.assertTrue(csv_path.is_file())
                with csv_path.open(newline="", encoding="utf-8") as handle:
                    header = next(csv.reader(handle))
                self.assertEqual(header, ["frequency_hz", "magnitude_db", "phase_deg"])
                self.assertIn("fs/2", summary["results"][target]["plot_markers"])

    def test_tloop_crossing_above_valid_limit_is_marked_extrapolated(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            case = self.make_registered_case(root)
            data = json.loads(case.read_text(encoding="utf-8"))
            data["targets"] = ["Gvc", "Tloop"]
            data["feedback"] = {
                "Gc": "1",
                "H": "1",
                "loop_break": {
                    "enabled": True,
                    "mode": "TLOOP_SIMPLE_NEGATIVE_FEEDBACK",
                    "injection_point": "EA input",
                    "return_point": "feedback return",
                    "measured_quantity": "loop_gain",
                    "sign_convention": "negative_feedback",
                    "forward_path": ["compensator", "modulator", "power_stage"],
                    "feedback_path": ["divider"],
                    "H": "1",
                },
            }
            data["valid_frequency"] = {"max_hz": 1000}
            case.write_text(json.dumps(data), encoding="utf-8")
            out = root / "plots"
            result = self.run_cli("plot-bode", "--case", str(case),
                                  "--targets", "Tloop", "--out", str(out))
            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads((out / "bode_summary.json").read_text(encoding="utf-8"))
            self.assertGreater(
                summary["results"]["Tloop"]["zero_db_crossing_hz"],
                summary["valid_frequency_limit_hz"],
            )
            self.assertEqual(
                summary["results"]["Tloop"]["validity"],
                "EXTRAPOLATED_BEYOND_VALID_RANGE",
            )


if __name__ == "__main__":
    unittest.main()
