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
            root = Path(td)
            path = root / "intake_status.json"
            output = root / "classification.json"
            path.write_text(json.dumps({
                "intake_version": "0.3.1", "status": "COMPLETE", "missing": [],
                "action": "CONTINUE_TO_CLASSIFICATION", "normalized": protocol_intake(),
            }), encoding="utf-8")
            result = self.run_cli("classify", "--intake-status", str(path), "--out", str(output))
            written = json.loads(output.read_text(encoding="utf-8")) if output.is_file() else {}
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["path"], "PROTOCOL_DERIVED_NEW")
        self.assertEqual(written["path"], "PROTOCOL_DERIVED_NEW")

    def test_make_and_derive_protocol_case(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            intake = root / "intake.json"
            case = root / "case.json"
            report = root / "report.md"
            intake.write_text(json.dumps(protocol_intake()), encoding="utf-8")
            made = self.run_cli("make-protocol-case", "--intake", str(intake), "--out", str(case))
            self.assertEqual(made.returncode, 0, made.stderr)
            derived = self.run_cli("derive", "--proof-object", str(case), "--out", str(report))
            self.assertEqual(derived.returncode, 0, derived.stderr)
            self.assertEqual(json.loads(case.read_text(encoding="utf-8"))["proof_version"], "0.3.1")
            self.assertIn("## Structured evidence", report.read_text(encoding="utf-8"))

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
        self.assertIn("ASK_USER_ONLY", result.stderr)

    def test_legacy_case_cannot_render_final_report_without_proof_object(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            params = root / "params.json"
            case = root / "case.json"
            report = root / "report.md"
            params.write_text(json.dumps({
                "Vin": 12, "Vo": 1.2, "fs": 300000, "L": 3e-7,
                "C": 560e-6, "R": 0.1, "rC": 0.006,
            }), encoding="utf-8")
            made = self.run_cli("make-case", "--model", "v2-cot-li-lee-2009",
                                "--params", str(params), "--approximation", "pade",
                                "--out", str(case))
            self.assertEqual(made.returncode, 0, made.stderr)
            derived = self.run_cli("derive", "--case", str(case), "--out", str(report))
            report_exists = report.exists()
        self.assertEqual(derived.returncode, 2)
        self.assertIn("proof object", derived.stderr.lower())
        self.assertFalse(report_exists)


if __name__ == "__main__":
    unittest.main()
