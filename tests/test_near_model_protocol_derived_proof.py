import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_proof_object import ProofBuildError, build_proof_object


def near_model_intake(*, with_relation: bool) -> dict:
    normalized = {
        "case_id": "near-model-rc-proof",
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
    if with_relation:
        normalized["df_relation"] = {
            "form": "d_hat = Kmod_s_memory * (v_c_hat - v_sense_hat)",
            "origin": "protocol_derived",
            "validation": "PROTOCOL_DERIVED_UNVERIFIED",
        }
    return {
        "intake_version": "0.3.1",
        "status": "COMPLETE",
        "missing": [],
        "action": "CONTINUE_TO_CLASSIFICATION",
        "normalized": normalized,
    }


class NearModelProtocolDerivedProofTests(unittest.TestCase):
    def test_near_model_without_proof_evidence_stops_at_audit(self) -> None:
        with self.assertRaisesRegex(ProofBuildError, "df_relation.form"):
            build_proof_object(
                near_model_intake(with_relation=False),
                {"path": "NEAR_MODEL", "validation_level": "PROTOCOL_DERIVED_UNVERIFIED"},
            )

    def test_near_model_with_df_relation_builds_protocol_unverified_proof(self) -> None:
        proof = build_proof_object(
            near_model_intake(with_relation=True),
            {"path": "NEAR_MODEL", "validation_level": "PROTOCOL_DERIVED_UNVERIFIED"},
        )

        self.assertEqual(proof["classification"]["path"], "PROTOCOL_DERIVED_NEW")
        self.assertEqual(proof["classification"]["source_path"], "NEAR_MODEL")
        self.assertEqual(proof["validation"]["level"], "PROTOCOL_DERIVED_UNVERIFIED")
        self.assertEqual(proof["formula_bindings"], [])
        self.assertEqual(proof["formula_origin"]["origin"], "protocol_derived")
        self.assertEqual(proof["formula_origin"]["validation"], "PROTOCOL_DERIVED_UNVERIFIED")


if __name__ == "__main__":
    unittest.main()
