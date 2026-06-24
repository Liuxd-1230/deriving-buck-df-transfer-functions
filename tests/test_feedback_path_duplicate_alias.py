import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from check_feedback_path_uniqueness import check_feedback_path_uniqueness
from linear_system_transfer import LinearSystemError, solve_linear_system
from tests.test_linear_equation_system_transfer import open_modulator_system


class FeedbackPathDuplicateAliasTests(unittest.TestCase):
    def duplicate_alias_system(self) -> dict:
        system = open_modulator_system()
        system["coefficient_definitions"][1]["symbol"] = "Hsn"
        system["blocks"][1]["coefficient"] = "Hsn"
        system["active_equations"][1]["rhs"] = "Hsn*d_hat"
        system["coefficient_definitions"].append({
            "symbol": "Gvsw_d",
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
        system["blocks"].append({"id": "blk_sense_alias", "type": "open_block", "from": "d_hat", "to": "vsense_hat", "coefficient": "Gvsw_d", "feedback_path": "sense_path"})
        system["active_equations"].append({"id": "eq_sense_alias", "block_id": "blk_sense_alias", "role": "active", "lhs": "vsense_hat", "rhs": "Gvsw_d*d_hat"})
        return system

    def test_duplicate_sensing_aliases_cannot_both_enter_active_denominator(self) -> None:
        with self.assertRaisesRegex(LinearSystemError, "FAIL_DUPLICATE_SENSING_PATH_ALIAS"):
            solve_linear_system(self.duplicate_alias_system())

    def test_duplicate_alias_is_allowed_when_diagnostic_only(self) -> None:
        system = self.duplicate_alias_system()
        system["active_equations"] = [eq for eq in system["active_equations"] if eq["id"] != "eq_sense_alias"]
        system["blocks"] = [block for block in system["blocks"] if block["id"] != "blk_sense_alias"]
        system["diagnostic_equations"].append({"id": "diag_alias", "role": "diagnostic", "lhs": "Gvsw_d", "rhs": "Hsn"})

        derivation = solve_linear_system(system)

        self.assertEqual(derivation["denominator_provenance"][0]["feedback_path"], "sense_path")

    def test_denominator_provenance_references_each_path_once(self) -> None:
        result = check_feedback_path_uniqueness({
            "denominator_provenance": [
                {"feedback_path": "sense_path", "source_equations": ["eq1"]},
                {"feedback_path": "sense_path", "source_equations": ["eq2"]},
            ]
        })

        self.assertEqual(result["status"], "FAIL")
        self.assertIn("FAIL_DOUBLE_CLOSED_FEEDBACK_PATH", result["errors"])


if __name__ == "__main__":
    unittest.main()
