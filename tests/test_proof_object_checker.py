import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts" / "check_proof_object.py"
FORMULA_CHECKER = ROOT / "scripts" / "check_formula_consistency.py"
BUILDER = ROOT / "scripts" / "build_proof_object.py"
VALID = ROOT / "tests" / "fixtures" / "valid_li_lee_2009_direct.json"


class ProofObjectCheckerTests(unittest.TestCase):
    def run_checker(self, script, proof):
        return subprocess.run(
            [sys.executable, str(script), "--proof", str(proof)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=60,
        )

    def test_incomplete_intake_is_rejected(self):
        proof = json.loads(VALID.read_text(encoding="utf-8"))
        proof["intake"]["status"] = "INCOMPLETE"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "proof.json"
            path.write_text(json.dumps(proof), encoding="utf-8")
            result = self.run_checker(CHECKER, path)
        self.assertTrue(result.stdout, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "FAIL_INCOMPLETE_INTAKE")

    def test_unregistered_direct_target_is_rejected(self):
        proof = json.loads(VALID.read_text(encoding="utf-8"))
        proof["transfer"]["target_transfer"] = "Gvg"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "proof.json"
            path.write_text(json.dumps(proof), encoding="utf-8")
            result = self.run_checker(CHECKER, path)
        self.assertTrue(result.stdout, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "FAIL_REGISTERED_TARGET")

    def test_direct_transfer_expression_must_match_its_binding(self):
        proof = json.loads(VALID.read_text(encoding="utf-8"))
        proof["transfer"]["expression"] = "1"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "proof.json"
            path.write_text(json.dumps(proof), encoding="utf-8")
            result = self.run_checker(CHECKER, path)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["status"], "FAIL_FORMULA_CONSISTENCY")

    def test_changed_q2_fails_formula_consistency(self):
        proof = json.loads(VALID.read_text(encoding="utf-8"))
        proof["formula_bindings"][0]["expression"] = "Tsw/(pi*(rC*C+Ton/2))"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "proof.json"
            path.write_text(json.dumps(proof), encoding="utf-8")
            result = self.run_checker(FORMULA_CHECKER, path)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["status"], "FAIL")

    def test_changed_bound_direct_formula_fails_consistency(self):
        proof = json.loads(VALID.read_text(encoding="utf-8"))
        proof["formula_bindings"][1]["expression"] = "1+s*rC*C"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "proof.json"
            path.write_text(json.dumps(proof), encoding="utf-8")
            result = self.run_checker(FORMULA_CHECKER, path)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["status"], "FAIL")

    def test_builder_creates_registry_bound_direct_proof(self):
        complete_intake = {
            "intake_version": "0.3.1",
            "status": "COMPLETE",
            "missing": [],
            "action": "CONTINUE_TO_CLASSIFICATION",
            "normalized": {
                "model_id": "v2-cot-li-lee-2009", "target": "Gvc",
                "target_transfer": "Gvc", "topology": "buck",
                "conduction_mode": "CCM", "phases": 1, "control_family": "V-COT",
                "switching_events": [{"name": "valley", "equation": "F_event=vfb-vc=0"}],
                "comparator_inputs": {"positive": "vfb", "negative": "vc"},
                "parameters": {"Vin": 12, "Vo": 1.2, "fs": 300000, "L": 3e-7,
                               "C": 560e-6, "R": 0.1, "rC": 0.006}
            }
        }
        classification = {"path": "DF_REGISTERED_DIRECT", "model_id": "v2-cot-li-lee-2009"}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            intake_path = root / "intake_status.json"
            class_path = root / "classification.json"
            proof_path = root / "proof.json"
            intake_path.write_text(json.dumps(complete_intake), encoding="utf-8")
            class_path.write_text(json.dumps(classification), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(BUILDER), "--intake-status", str(intake_path),
                 "--classification", str(class_path), "--out", str(proof_path)],
                cwd=ROOT, text=True, capture_output=True, timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            proof = json.loads(proof_path.read_text(encoding="utf-8"))
        self.assertEqual(proof["modulator"], {"model_type": "direct-transfer"})
        self.assertEqual(proof["transfer"]["target_transfer"], "Gvc")
        self.assertNotIn("coefficients", proof["modulator"])

    def test_builder_creates_four_registry_bound_multiport_coefficients(self):
        complete_intake = {
            "intake_version": "0.3.1", "status": "COMPLETE", "missing": [],
            "action": "CONTINUE_TO_CLASSIFICATION",
            "normalized": {
                "model_id": "cot-cm-external-ramp-tian-2015", "target": "Gvc",
                "target_transfer": "Gvc", "topology": "buck", "conduction_mode": "CCM",
                "phases": 1, "control_family": "C-COT",
                "switching_events": [{"name": "off", "equation": "F_event=Ri*iL+vramp-vc=0"}],
                "comparator_inputs": {"positive": "Ri*iL+vramp", "negative": "vc"},
                "parameters": {"Vin": 12, "Vo": 1.2, "fs": 300000, "L": 3e-7,
                               "C": 0.00448, "R": 0.1, "rC": 0.00075,
                               "Ri": 0.01, "se_ratio": 1}
            }
        }
        classification = {"path": "DF_REGISTERED_MULTIPORT", "model_id": "cot-cm-external-ramp-tian-2015"}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            intake_path, class_path, proof_path = root / "intake.json", root / "class.json", root / "proof.json"
            intake_path.write_text(json.dumps(complete_intake), encoding="utf-8")
            class_path.write_text(json.dumps(classification), encoding="utf-8")
            built = subprocess.run(
                [sys.executable, str(BUILDER), "--intake-status", str(intake_path),
                 "--classification", str(class_path), "--out", str(proof_path)],
                cwd=ROOT, text=True, capture_output=True, timeout=60,
            )
            self.assertEqual(built.returncode, 0, built.stderr)
            proof = json.loads(proof_path.read_text(encoding="utf-8"))
            checked = self.run_checker(CHECKER, proof_path)
        self.assertEqual(set(proof["modulator"]["coefficients"]), {"a_c", "a_g", "a_o", "a_i"})
        self.assertTrue(all(item["formula_id"] for item in proof["modulator"]["coefficients"].values()))
        self.assertIn("origin", proof["transfer"])
        self.assertEqual(proof["transfer"]["origin"], "registered-buck-sympy-elimination")
        self.assertNotIn("pending", proof["transfer"]["expression"])
        self.assertEqual(json.loads(checked.stdout)["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
