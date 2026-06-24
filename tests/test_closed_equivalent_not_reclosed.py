import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from linear_system_transfer import LinearSystemError, solve_linear_system
from tests.test_linear_equation_system_transfer import closed_equivalent_system


class ClosedEquivalentNotReclosedTests(unittest.TestCase):
    def test_closed_equivalent_kmod_cannot_be_reclosed_with_sense_path(self) -> None:
        system = closed_equivalent_system()
        system["coefficient_definitions"][0]["symbol"] = "Kmod"
        system["blocks"][0]["coefficient"] = "Kmod"
        system["blocks"][0]["feedback_paths_already_closed"] = ["sense_path"]
        system["active_equations"][0]["rhs"] = "Kmod*vc_hat - Kmod*Hsn*d_hat"
        system["coefficient_definitions"].append({
            "symbol": "Hsn",
            "expression": "Hsn",
            "from": "d_hat",
            "to": "vsense_hat",
            "input_semantics": "duty",
            "output_semantics": "voltage",
            "block_type": "open_block",
            "unit_signature": "V",
            "provenance": "protocol_derived_unverified",
            "feedback_path": "sense_path",
        })

        with self.assertRaisesRegex(LinearSystemError, "FAIL_DOUBLE_CLOSED_FEEDBACK_PATH|FAIL_CLOSED_EQUIVALENT_USED_AS_OPEN_BLOCK"):
            solve_linear_system(system)

    def test_closed_equivalent_valid_use_is_product_without_denominator(self) -> None:
        system = closed_equivalent_system()
        system["coefficient_definitions"][0]["symbol"] = "Kmod"
        system["blocks"][0]["coefficient"] = "Kmod"
        system["active_equations"][0]["rhs"] = "Kmod*vc_hat"

        derivation = solve_linear_system(system)

        self.assertEqual(derivation["generated_expression"], "Gvd*Kmod")
        self.assertEqual(derivation["denominator_provenance"], [])


if __name__ == "__main__":
    unittest.main()
