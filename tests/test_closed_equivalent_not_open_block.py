import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from linear_system_transfer import LinearSystemError, solve_linear_system
from tests.test_linear_equation_system_transfer import closed_equivalent_system


class ClosedEquivalentNotOpenBlockTests(unittest.TestCase):
    def test_closed_equivalent_coefficient_used_as_open_error_gain_fails(self) -> None:
        system = closed_equivalent_system()
        system["variables"].append({"name": "vsense_hat", "role": "unknown", "quantity": "voltage", "unit_signature": "V"})
        system["unknowns"].insert(1, "vsense_hat")
        system["blocks"][0]["type"] = "open_block"
        system["blocks"][0]["from"] = "vc_hat_minus_vsense_hat"
        system["active_equations"][0]["rhs"] = "Kmem*(vc_hat-vsense_hat)"

        with self.assertRaisesRegex(LinearSystemError, "FAIL_CLOSED_EQUIVALENT_USED_AS_OPEN_BLOCK"):
            solve_linear_system(system)

    def test_eliminated_internal_variable_cannot_be_reintroduced(self) -> None:
        system = closed_equivalent_system()
        system["variables"].append({"name": "vsense_hat", "role": "unknown", "quantity": "voltage", "unit_signature": "V"})
        system["unknowns"].insert(1, "vsense_hat")
        system["blocks"].insert(1, {"id": "blk_sense", "type": "open_block", "from": "d_hat", "to": "vsense_hat", "coefficient": "Hs", "feedback_path": "sense_path"})
        system["coefficient_definitions"].insert(1, {
            "symbol": "Hs",
            "expression": "Hs",
            "from": "d_hat",
            "to": "vsense_hat",
            "input_semantics": "duty",
            "output_semantics": "voltage",
            "block_type": "open_block",
            "unit_signature": "V",
            "provenance": "protocol_derived_unverified",
        })
        system["active_equations"].insert(1, {"id": "eq_sense_path", "block_id": "blk_sense", "role": "active", "lhs": "vsense_hat", "rhs": "Hs*d_hat"})

        with self.assertRaisesRegex(LinearSystemError, "FAIL_REINTRODUCED_ELIMINATED_INTERNAL_VARIABLE"):
            solve_linear_system(system)


if __name__ == "__main__":
    unittest.main()
