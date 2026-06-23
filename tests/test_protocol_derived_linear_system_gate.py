import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from artifact_workflow import attach_workflow
from build_proof_object import ProofBuildError, build_proof_object
from check_proof_object import check_proof_object
from tests.test_linear_system_transfer import open_loop_system


def v04_intake(linear_system: dict | None = None, *, raw_transfer: bool = False) -> dict:
    normalized = {
        "case_id": "protocol-linear-gate",
        "intent": "user-circuit-derivation",
        "target": "Gvc",
        "target_transfer": "Gvc",
        "topology": "buck",
        "conduction_mode": "CCM",
        "phases": 1,
        "control_family": "COT",
        "switching_events": [{"name": "valley", "equation": "Vsense-Vc=0"}],
        "comparator_inputs": {"positive": "Vc", "negative": "Vsense"},
        "sensing_layer": {"type": "custom_sensing_network", "validation": "user_supplied"},
        "parameters": {"Vin": 12, "Vo": 1.2, "fs": 495e3, "L": 300e-9, "C": 400e-6, "R": 0.1, "rC": 1.5e-3},
    }
    if linear_system is not None:
        normalized["linear_equation_system"] = linear_system
    if raw_transfer:
        normalized["transfer_function"] = "Gvd*K/(1+K*H)"
    artifact = {
        "intake_version": "0.4",
        "status": "COMPLETE",
        "missing": [],
        "action": "CONTINUE_TO_CLASSIFICATION",
        "normalized": normalized,
    }
    return attach_workflow(artifact, state="PREFLIGHT_INTAKE", intent="user-circuit-derivation")


def classification() -> dict:
    artifact = {
        "classification_version": "0.4",
        "path": "NEAR_MODEL",
        "validation_level": "PROTOCOL_DERIVED_UNVERIFIED",
        "model_match": {"known_model": False, "model_id": None, "confidence": "low"},
    }
    return artifact


class ProtocolDerivedLinearSystemGateTests(unittest.TestCase):
    def test_v04_protocol_derived_requires_linear_equation_system(self) -> None:
        intake = v04_intake(raw_transfer=True)
        cls = attach_workflow(classification(), state="MODEL_CLASSIFY", intent="user-circuit-derivation", predecessor=intake)

        with self.assertRaisesRegex(ProofBuildError, "linear_equation_system"):
            build_proof_object(intake, cls)

    def test_v04_protocol_derived_proof_defers_transfer_to_solver(self) -> None:
        intake = v04_intake(open_loop_system(), raw_transfer=True)
        cls = attach_workflow(classification(), state="MODEL_CLASSIFY", intent="user-circuit-derivation", predecessor=intake)

        proof = build_proof_object(intake, cls)

        self.assertEqual(proof["classification"]["path"], "PROTOCOL_DERIVED_NEW")
        self.assertEqual(proof["transfer"]["origin"], "linear-system-pending")
        self.assertNotEqual(proof["transfer"].get("expression"), "Gvd*K/(1+K*H)")
        self.assertIn("linear_equation_system", proof)
        self.assertEqual(check_proof_object(proof)["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
