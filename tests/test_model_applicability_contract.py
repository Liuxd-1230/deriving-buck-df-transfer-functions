import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from df_model_classifier import classify_intake
from formula_registry import model_specs
from model_applicability import check_model_applicability


def registered_intake(model_id: str, sensing_type: str) -> dict:
    return {
        "case_id": "applicability-case",
        "intent": "user-circuit-derivation",
        "topology": "buck",
        "conduction_mode": "CCM",
        "phases": 1,
        "model_id": model_id,
        "control_family": "current-mode COT",
        "target": "Gvc",
        "target_transfer": "Gvc",
        "switching_events": [{"name": "valley", "equation": "is-iref=0"}],
        "comparator_inputs": {"positive": "isense", "negative": "iref"},
        "sampled_variable": "iL",
        "fixed_interval": "Ton",
        "movable_interval": "Toff",
        "sensing_layer": {
            "type": sensing_type,
            "input_variable": "iL" if sensing_type == "direct_current_sense" else "vout",
            "output_variable": "comparator_positive",
            "validation": "registered",
        },
        "parameters": {"Vin": 12, "Vo": 1.2, "L": 3e-7, "C": 4e-4, "R": 0.1, "rC": 0.002, "fs": 5e5},
    }


class ModelApplicabilityContractTests(unittest.TestCase):
    def test_current_mode_registered_model_rejects_output_ripple_sensing(self) -> None:
        intake = registered_intake("cot-cm-li-lee-2010", "output_ripple")

        result = classify_intake(intake)

        self.assertNotEqual(result["path"], "DF_REGISTERED_MULTIPORT")
        self.assertIn(result["validation_level"], {"PROTOCOL_DERIVED_UNVERIFIED", "AUDIT_REQUIRED", "REJECTED_UNSUPPORTED"})
        self.assertNotEqual(result.get("validation_level"), "PAPER_GROUNDED_PARTIAL")

    def test_v2_registered_model_rejects_direct_current_sense(self) -> None:
        intake = registered_intake("v2-cot-li-lee-2009", "direct_current_sense") | {
            "control_family": "V2-COT"
        }

        result = classify_intake(intake)

        self.assertNotEqual(result["path"], "DF_REGISTERED_DIRECT")
        self.assertNotEqual(result.get("validation_level"), "PAPER_GROUNDED_PARTIAL")

    def test_yan_zero_ramp_rejects_switch_node_rc_sensing(self) -> None:
        intake = registered_intake("cot-cm-li-lee-2010", "switch_node_rc") | {
            "model_id": None,
            "control_family": "C-COT",
            "target": "Tc",
            "target_transfer": "Tc",
            "comparator_input_origin": "switch_node_rc",
            "has_filter_in_sense_path": True,
        }

        result = classify_intake(intake)

        self.assertNotEqual(result["path"], "SAMPLED_DATA_REGISTERED")
        self.assertNotEqual(result.get("model_id"), "yan-2022-part-ii-ccot-buck-zero-ramp")

    def test_matching_registered_current_sense_passes_applicability(self) -> None:
        intake = registered_intake("cot-cm-li-lee-2010", "direct_current_sense")

        result = check_model_applicability(intake, model_specs()["cot-cm-li-lee-2010"])

        self.assertEqual(result["status"], "PASS")
        self.assertIn("sensing_layer.type", result["matched_fields"])


if __name__ == "__main__":
    unittest.main()
