import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = ROOT / "scripts" / "preflight_intake.py"
CLI = ROOT / "scripts" / "df_buck_sympy.py"


def engineering_case_intake(include_loop_break=False):
    intake = {
        "topology": "buck", "conduction_mode": "CCM", "phases": 1,
        "control_family": "current-mode COT valley comparison",
        "target_transfer": ["Gvc", "Tloop"],
        "control_timing": {"fixed": "Ton", "variable": "Toff/Tsw"},
        "switching_events": [{"name": "valley", "fixed_or_movable": "movable",
                              "equation": "Ri*iL-vcomp=0"}],
        "comparator_inputs": {"positive": "compensated EA output", "negative": "Ri*iL"},
        "parameters": {
            "Vin": 36, "Vo": 3.3, "Ton": 487e-9, "fs": 188034.18803418803,
            "L": 3.3e-6, "C": 2040e-6, "R": 0.094286, "rC": 2.23e-3, "Ri": 1 / 30,
        },
        "model_id": "cot-cm-li-lee-2010",
        "compensator": {
            "type": "SIMPLIS_LAPLACE", "KPZ": 8000, "wz1": 4000,
            "wp1": 50, "wp2": 400000, "frequency_scale_factor": 1,
            "form": "simplicis_s_plus_w",
        },
    }
    if include_loop_break:
        intake["loop_break"] = {
            "enabled": True,
            "mode": "TLOOP_SIMPLE_NEGATIVE_FEEDBACK",
            "injection_point": "EA input summing node",
            "return_point": "feedback divider return",
            "measured_quantity": "loop_gain",
            "sign_convention": "negative_feedback",
            "forward_path": ["compensator", "modulator", "power_stage"],
            "feedback_path": ["divider"],
            "H": "1",
            "notes": "Default negative feedback convention, not a SIMPLIS probe claim.",
        }
    return intake


class TloopLoopBreakTests(unittest.TestCase):
    def run_preflight(self, intake):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "intake.json"
            output = root / "intake_status.json"
            source.write_text(json.dumps(intake), encoding="utf-8")
            result = subprocess.run([sys.executable, str(PREFLIGHT), "--intake", str(source), "--out", str(output)],
                                    cwd=ROOT, text=True, capture_output=True, timeout=30)
            status = json.loads(output.read_text(encoding="utf-8"))
        return result, status

    def test_tloop_requires_loop_break_but_gvc_alone_does_not(self):
        result, status = self.run_preflight(engineering_case_intake(include_loop_break=False))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(status["status"], "INCOMPLETE_TLOOP_INTAKE")
        self.assertEqual(status["action"], "ASK_USER_ONLY")
        self.assertIn("loop_break", status["missing"])
        gvc_only = engineering_case_intake(include_loop_break=False)
        gvc_only["target_transfer"] = "Gvc"
        result, status = self.run_preflight(gvc_only)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(status["status"], "COMPLETE")

    def test_tloop_with_default_negative_feedback_can_plot_and_records_sign(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            params = root / "params.json"
            case = root / "case.json"
            plots = root / "plots"
            params.write_text(json.dumps(engineering_case_intake(True)["parameters"]), encoding="utf-8")
            made = subprocess.run([sys.executable, str(CLI), "make-case", "--model", "cot-cm-li-lee-2010",
                                   "--params", str(params), "--approximation", "pade", "--out", str(case)],
                                  cwd=ROOT, text=True, capture_output=True, timeout=30)
            self.assertEqual(made.returncode, 0, made.stderr)
            data = json.loads(case.read_text(encoding="utf-8"))
            data["targets"] = ["Gvc", "Tloop"]
            data["feedback"] = {
                "Gc": "8000*(s+4000)/((s+50)*(s+400000))",
                "H": "1",
                "loop_break": engineering_case_intake(True)["loop_break"],
                "formula_origin": "compensator-template:SIMPLIS_LAPLACE",
            }
            case.write_text(json.dumps(data), encoding="utf-8")
            plotted = subprocess.run([sys.executable, str(CLI), "plot-bode", "--case", str(case),
                                      "--targets", "Tloop", "--out", str(plots)],
                                     cwd=ROOT, text=True, capture_output=True, timeout=60)
            self.assertEqual(plotted.returncode, 0, plotted.stderr)
            summary = json.loads((plots / "bode_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["loop_break"]["sign_convention"], "negative_feedback")
            self.assertIn(summary["results"]["Tloop"]["validity"],
                          {"WITHIN_DECLARED_RANGE", "EXTRAPOLATED_BEYOND_VALID_RANGE"})


if __name__ == "__main__":
    unittest.main()
