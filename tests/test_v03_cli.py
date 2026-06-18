import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "df_buck_sympy.py"


def protocol_intake():
    return {
        "topology": "buck", "conduction_mode": "CCM", "phases": 1,
        "control_family": "custom-cot", "target": "Gvc",
        "control_timing": {"fixed": "Ton", "variable": "Toff/Tsw"},
        "switching_events": [{"name": "off_edge", "fixed_or_movable": "movable",
            "equation": "F_off=Ri*iL+vramp-vc=0", "edge_slope": "Fdot_0=dF/dt",
            "delta_edge": "delta_t=-delta_F/Fdot_0"}],
        "comparator_inputs": {"positive": "vc", "negative": "Ri*iL+vramp"},
        "parameters": {"Vin": 12, "Vo": 1.2, "fs": 300000, "L": 3e-7,
                       "C": 470e-6, "R": 0.1, "rC": 0.001},
        "state_variables": ["iL", "vo"],
        "switching_state_equations": {"on": "L*diL/dt=vg-vo", "off": "L*diL/dt=-vo"},
        "steady_state_trajectory": "CCM piecewise trajectory",
        "perturbation_paths": {"uc_hat": "enters event", "iL_hat": "enters event"},
        "df_relation": {"form": "d_hat=a_c*uc_hat+a_i*iL_hat", "a_c": "A_c(s)",
                        "a_i": "A_i(s)", "origin": "paper-inspired-new-derivation",
                        "duty_caveat": "equivalent switching-function perturbation"},
        "sanity_checks": ["symbolic", "dc-limit"]
    }


class V03CliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-S", str(CLI), *args], cwd=ROOT,
                              text=True, capture_output=True, timeout=30)

    def test_classify_prints_structured_result(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "intake.json"
            path.write_text(json.dumps(protocol_intake()), encoding="utf-8")
            result = self.run_cli("classify", "--intake", str(path))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["path"], "NEW_MODEL")

    def test_make_and_derive_protocol_case(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            intake = root / "intake.json"
            case = root / "case.json"
            report = root / "report.md"
            intake.write_text(json.dumps(protocol_intake()), encoding="utf-8")
            made = self.run_cli("make-protocol-case", "--intake", str(intake), "--out", str(case))
            self.assertEqual(made.returncode, 0, made.stderr)
            derived = self.run_cli("derive", "--case", str(case), "--out", str(report))
            self.assertEqual(derived.returncode, 0, derived.stderr)
            self.assertEqual(json.loads(case.read_text(encoding="utf-8"))["case_version"], "0.3")
            self.assertIn("## Switching event equation", report.read_text(encoding="utf-8"))

    def test_missing_event_cannot_make_protocol_case(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            data = protocol_intake()
            del data["switching_events"]
            intake = root / "intake.json"
            intake.write_text(json.dumps(data), encoding="utf-8")
            result = self.run_cli("make-protocol-case", "--intake", str(intake),
                                  "--out", str(root / "case.json"))
        self.assertEqual(result.returncode, 2)
        self.assertIn("switching_events", result.stderr)


if __name__ == "__main__":
    unittest.main()
