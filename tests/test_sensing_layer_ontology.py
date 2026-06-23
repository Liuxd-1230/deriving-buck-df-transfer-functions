import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from df_model_classifier import classify_intake
from preflight_intake import build_intake_status, IntakeGateError


def complete_user_intake() -> dict:
    return {
        "case_id": "missing-sensing-user-case",
        "intent": "user-circuit-derivation",
        "topology": "buck",
        "conduction_mode": "CCM",
        "phases": 1,
        "control_family": "C-COT",
        "target": "Gm",
        "target_transfer": "Gm",
        "sampling_event": "intersection(is,iref)",
        "switching_events": [{"name": "sample", "equation": "is-iref=0"}],
        "comparator_inputs": {"positive": "is", "negative": "iref"},
        "sampled_variable": "is",
        "fixed_interval": "Ton",
        "parameters": {
            "Vin": 12,
            "Vo": 1.2,
            "fs": 500000,
            "Ton": 2e-7,
            "L": 300e-9,
            "C": 560e-6,
            "R": 0.1,
            "rC": 0.006,
        },
    }


class SensingLayerOntologyTests(unittest.TestCase):
    def test_user_circuit_missing_sensing_layer_asks_user_only(self) -> None:
        status = build_intake_status(intake=complete_user_intake())

        self.assertEqual(status["status"], "INCOMPLETE")
        self.assertEqual(status["action"], "ASK_USER_ONLY")
        self.assertIn("sensing_layer", status["missing"])
        with self.assertRaisesRegex(IntakeGateError, "ASK_USER_ONLY"):
            from df_model_classifier import classify_intake_status

            classify_intake_status(status)

    def test_unknown_sensing_layer_does_not_route_to_sampled_registered(self) -> None:
        intake = complete_user_intake() | {
            "sensing_layer": {
                "type": "unknown",
                "input_variable": "unknown",
                "output_variable": "unknown",
                "gain": "unknown",
                "time_constants": [],
                "validation": "unverified",
            }
        }

        result = classify_intake(intake)

        self.assertNotEqual(result["path"], "SAMPLED_DATA_REGISTERED")
        self.assertEqual(result["path"], "NEAR_MODEL")
        self.assertIn("AUDIT_REQUIRED", result["validation_flags"])

    def test_custom_sensing_layer_is_near_model_not_paper_grounded(self) -> None:
        intake = complete_user_intake() | {
            "target": "Gvc",
            "target_transfer": "Gvc",
            "control_family": "current-mode COT",
            "sensing_layer": {
                "type": "custom_sensing_network",
                "input_variable": "mixed",
                "output_variable": "comparator_input",
                "gain": "user_supplied",
                "time_constants": ["tau1"],
                "validation": "user_supplied",
            },
        }

        result = classify_intake(intake)

        self.assertEqual(result["path"], "NEAR_MODEL")
        self.assertEqual(result["validation_level"], "PROTOCOL_DERIVED_UNVERIFIED")
        self.assertNotEqual(result.get("validation_level"), "PAPER_GROUNDED_PARTIAL")
        self.assertEqual(result["model_match"]["known_model"], False)


if __name__ == "__main__":
    unittest.main()
