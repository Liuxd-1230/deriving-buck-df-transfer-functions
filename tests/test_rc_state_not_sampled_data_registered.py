import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from df_model_classifier import classify_intake
from tests.test_sensing_layer_ontology import complete_user_intake


class RcStateNotSampledDataRegisteredTests(unittest.TestCase):
    def test_switch_node_rc_cot_does_not_enter_yan_zero_ramp_registered_path(self) -> None:
        intake = complete_user_intake() | {
            "control_family": "C-COT",
            "target": "Tc",
            "target_transfer": "Tc",
            "comparator_input_origin": "switch_node_rc",
            "sensing_layer": {
                "type": "custom_sensing_network",
                "input_variable": "switch_node",
                "output_variable": "comparator_negative",
                "network_type": "RC_lowpass",
                "validation": "user_supplied",
            },
        }

        result = classify_intake(intake)

        self.assertNotEqual(result["path"], "SAMPLED_DATA_REGISTERED")
        self.assertNotEqual(result["model_match"].get("model_id"), "yan-2022-part-ii-ccot-buck-zero-ramp")
        self.assertIn(result["validation_level"], {"PROTOCOL_DERIVED_UNVERIFIED", "REJECTED_UNSUPPORTED", "AUDIT_REQUIRED"})


if __name__ == "__main__":
    unittest.main()
