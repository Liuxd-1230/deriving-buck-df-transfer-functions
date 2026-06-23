import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validation_policy import (
    check_reference_claims,
    normalization_decision,
    validate_power_stage_claim,
)


class ValidationPolicyTests(unittest.TestCase):
    def test_double_ri_uses_metadata_and_voltage_control_semantics(self) -> None:
        result = normalization_decision(
            formula_metadata={"Fc": {"includes_1_over_Ri": True}},
            target_semantics={"input": "voltage_control"},
        )

        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["composition"], "NO_EXTRA_RI_DIVISION")

    def test_ambiguous_normalization_is_not_rewritten(self) -> None:
        result = normalization_decision(
            formula_metadata={"Fc": {"includes_1_over_Ri": True}},
            target_semantics={"input": "unknown"},
        )

        self.assertEqual(result["status"], "NORMALIZATION_AMBIGUOUS")
        self.assertTrue(result["blocking"])

    def test_low_order_power_stage_must_be_declared(self) -> None:
        result = validate_power_stage_claim(
            {
                "diagnosis": "LOW_ORDER_POWER_STAGE",
                "approximation_declared": False,
                "claims": ["FULL_POWER_STAGE_GVC"],
            }
        )

        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(result["blocking"])

    def test_unclear_reference_semantics_blocks_figure_reproduced(self) -> None:
        result = check_reference_claims(
            {
                "final_classification": "REFERENCE_TARGET_SEMANTICS_UNCLEAR",
                "curve_closeness": "CLOSE",
                "claims": ["FIGURE_REPRODUCED"],
            }
        )

        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(result["blocking"])


if __name__ == "__main__":
    unittest.main()
