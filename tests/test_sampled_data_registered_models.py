import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from artifact_workflow import attach_workflow


ROOT = Path(__file__).resolve().parents[1]
CLASSIFIER = ROOT / "scripts" / "df_buck_sympy.py"
BUILDER = ROOT / "scripts" / "build_proof_object.py"
CHECKER = ROOT / "scripts" / "check_proof_object.py"


def ccot_intake():
    artifact = {
        "intake_version": "0.4",
        "status": "COMPLETE",
        "missing": [],
        "action": "CONTINUE_TO_CLASSIFICATION",
        "normalized": {
            "case_id": "yan-ccot-zero-ramp",
            "topology": "buck",
            "conduction_mode": "CCM",
            "phases": 1,
            "control_family": "C-COT",
            "target": "Gm",
            "target_transfer": "Gm",
            "sampling_event": "intersection(is,iref)",
            "switching_events": [{"name": "valley", "equation": "is-iref=0"}],
            "comparator_inputs": {"positive": "is", "negative": "iref"},
            "sampled_variable": "is",
            "fixed_interval": "Ton",
            "has_external_ramp": False,
            "parameters": {
                "Vin": 12, "Vo": 1.2, "fs": 500000, "Ts": 2e-6,
                "Ton": 2e-7, "L": 300e-9, "C": 560e-6, "R": 0.1,
                "rC": 0.006, "m1": 1.0, "m2": -2.0,
            },
        },
    }
    return attach_workflow(
        artifact,
        state="PREFLIGHT_INTAKE",
        intent="user-circuit-derivation",
    )


class SampledDataRegisteredModelsTests(unittest.TestCase):
    def test_ccot_zero_ramp_classifies_and_builds_sampled_data_proof(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            intake_path = root / "intake_status.json"
            classification_path = root / "classification.json"
            proof_path = root / "proof.json"
            intake_path.write_text(json.dumps(ccot_intake()), encoding="utf-8")
            classified = subprocess.run(
                [sys.executable, str(CLASSIFIER), "classify", "--intake-status", str(intake_path), "--out", str(classification_path)],
                cwd=ROOT, text=True, capture_output=True, timeout=60,
            )
            self.assertEqual(classified.returncode, 0, classified.stderr)
            classification = json.loads(classification_path.read_text(encoding="utf-8"))
            self.assertEqual(classification["path"], "SAMPLED_DATA_REGISTERED")
            self.assertEqual(classification["part_family"], "SAMPLED_DATA_REGISTERED_PART_II_CCOT_CCOFT")

            built = subprocess.run(
                [sys.executable, str(BUILDER), "--intake-status", str(intake_path), "--classification", str(classification_path), "--out", str(proof_path)],
                cwd=ROOT, text=True, capture_output=True, timeout=60,
            )
            self.assertEqual(built.returncode, 0, built.stderr)
            proof = json.loads(proof_path.read_text(encoding="utf-8"))
            self.assertEqual(proof["proof_version"], "0.4")
            self.assertEqual(proof["pulse_structure"]["type"], "COT_TWO_PULSE_TRAINS")
            self.assertEqual(proof["pulse_structure"]["frequency_factor"], "1-exp(-s*T0)")
            self.assertEqual(proof["target_mapping"]["mapping_status"], "REGISTERED_DIRECT")
            checked = subprocess.run([sys.executable, str(CHECKER), "--proof", str(proof_path)],
                                     cwd=ROOT, text=True, capture_output=True, timeout=60)
            self.assertEqual(json.loads(checked.stdout)["status"], "PASS")

    def test_external_ramp_ccot_does_not_enter_sampled_registered_path(self):
        intake = ccot_intake()["normalized"]
        intake["has_external_ramp"] = True
        result = subprocess.run(
            [sys.executable, "-c", "import json,sys; sys.path.insert(0,'scripts'); from df_model_classifier import classify_intake; print(json.dumps(classify_intake(json.load(sys.stdin)), ensure_ascii=False))"],
            cwd=ROOT, input=json.dumps(intake), text=True, capture_output=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        classification = json.loads(result.stdout)
        self.assertEqual(classification["path"], "UNSUPPORTED")
        self.assertIn("REJECT_DYNAMIC_FM_REQUIRED_V05", classification["unsupported_effects"])

    def test_sampled_data_model_id_does_not_enter_df_registered_path(self):
        intake = ccot_intake()["normalized"]
        intake["model_id"] = "yan-2022-part-ii-ccot-buck-zero-ramp"
        result = subprocess.run(
            [sys.executable, "-c", "import json,sys; sys.path.insert(0,'scripts'); from df_model_classifier import classify_intake; print(json.dumps(classify_intake(json.load(sys.stdin)), ensure_ascii=False))"],
            cwd=ROOT, input=json.dumps(intake), text=True, capture_output=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        classification = json.loads(result.stdout)
        self.assertEqual(classification["path"], "SAMPLED_DATA_REGISTERED")
        self.assertEqual(classification["part_family"], "SAMPLED_DATA_REGISTERED_PART_II_CCOT_CCOFT")


if __name__ == "__main__":
    unittest.main()
