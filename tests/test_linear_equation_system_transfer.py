import sys
import unittest
from pathlib import Path

import sympy as sp


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from linear_system_transfer import LinearSystemError, solve_linear_system


def open_modulator_system() -> dict:
    return {
        "schema_version": "0.4.5",
        "case_id": "open-modulator",
        "path": "PROTOCOL_DERIVED_UNVERIFIED",
        "symbols": ["s"],
        "variables": [
            {"name": "vc_hat", "role": "input", "quantity": "voltage", "unit_signature": "V"},
            {"name": "d_hat", "role": "unknown", "quantity": "duty", "unit_signature": "1"},
            {"name": "vsense_hat", "role": "unknown", "quantity": "voltage", "unit_signature": "V"},
            {"name": "vo_hat", "role": "unknown", "quantity": "voltage", "unit_signature": "V"},
        ],
        "unknowns": ["d_hat", "vsense_hat", "vo_hat"],
        "inputs": ["vc_hat"],
        "diagnostic_outputs": [],
        "target": {
            "name": "Gvc",
            "output": "vo_hat",
            "input": "vc_hat",
            "response_kind": "transfer_function",
        },
        "coefficient_definitions": [
            {
                "symbol": "K0",
                "expression": "K0",
                "from": "vc_hat_minus_vsense_hat",
                "to": "d_hat",
                "input_semantics": "error_signal",
                "output_semantics": "duty",
                "block_type": "open_block",
                "feedback_paths_already_closed": [],
                "unit_signature": "1/V",
                "provenance": "protocol_derived_unverified",
            },
            {
                "symbol": "Hs",
                "expression": "Hs",
                "from": "d_hat",
                "to": "vsense_hat",
                "input_semantics": "duty",
                "output_semantics": "voltage",
                "block_type": "open_block",
                "unit_signature": "V",
                "provenance": "protocol_derived_unverified",
            },
            {
                "symbol": "Gvd",
                "expression": "Gvd",
                "from": "d_hat",
                "to": "vo_hat",
                "input_semantics": "duty",
                "output_semantics": "voltage",
                "block_type": "open_block",
                "unit_signature": "V",
                "provenance": "registered_power_stage",
            },
        ],
        "blocks": [
            {
                "id": "blk_modulator",
                "type": "open_block",
                "from": "vc_hat_minus_vsense_hat",
                "to": "d_hat",
                "coefficient": "K0",
                "feedback_path": "sense_path",
            },
            {"id": "blk_sense", "type": "open_block", "from": "d_hat", "to": "vsense_hat", "coefficient": "Hs", "feedback_path": "sense_path"},
            {"id": "blk_power", "type": "open_block", "from": "d_hat", "to": "vo_hat", "coefficient": "Gvd"},
        ],
        "active_equations": [
            {"id": "eq_modulator", "block_id": "blk_modulator", "role": "active", "lhs": "d_hat", "rhs": "K0*(vc_hat-vsense_hat)"},
            {"id": "eq_sense_path", "block_id": "blk_sense", "role": "active", "lhs": "vsense_hat", "rhs": "Hs*d_hat"},
            {"id": "eq_power_stage", "block_id": "blk_power", "role": "active", "lhs": "vo_hat", "rhs": "Gvd*d_hat"},
        ],
        "diagnostic_equations": [],
        "feedback_paths": [{"id": "sense_path", "source_equations": ["eq_modulator", "eq_sense_path"]}],
        "approximation_policy": {"level": "protocol_derived_unverified", "notes": []},
    }


def closed_equivalent_system() -> dict:
    system = open_modulator_system()
    system["case_id"] = "closed-equivalent"
    system["variables"] = [item for item in system["variables"] if item["name"] != "vsense_hat"]
    system["unknowns"] = ["d_hat", "vo_hat"]
    system["coefficient_definitions"] = [
        {
            "symbol": "Kmem",
            "expression": "Kmem",
            "from": "vc_hat",
            "to": "d_hat",
            "input_semantics": "control_signal",
            "output_semantics": "duty",
            "block_type": "closed_equivalent_block",
            "eliminated_variables": ["vsense_hat", "rc_state", "edge_time"],
            "eliminated_equations": ["comparator_event", "rc_state_map"],
            "feedback_paths_already_closed": ["sense_path"],
            "unit_signature": "1/V",
            "provenance": "protocol_derived_unverified",
        },
        {
            "symbol": "Gvd",
            "expression": "Gvd",
            "from": "d_hat",
            "to": "vo_hat",
            "input_semantics": "duty",
            "output_semantics": "voltage",
            "block_type": "open_block",
            "unit_signature": "V",
            "provenance": "registered_power_stage",
        },
    ]
    system["blocks"] = [
        {"id": "blk_modulator_closed", "type": "closed_equivalent_block", "from": "vc_hat", "to": "d_hat", "coefficient": "Kmem"},
        {"id": "blk_power", "type": "open_block", "from": "d_hat", "to": "vo_hat", "coefficient": "Gvd"},
    ]
    system["active_equations"] = [
        {"id": "eq_modulator_closed", "block_id": "blk_modulator_closed", "role": "active", "lhs": "d_hat", "rhs": "Kmem*vc_hat"},
        {"id": "eq_power_stage", "block_id": "blk_power", "role": "active", "lhs": "vo_hat", "rhs": "Gvd*d_hat"},
    ]
    system["feedback_paths"] = []
    return system


class LinearEquationSystemTransferTests(unittest.TestCase):
    def assert_equivalent(self, actual: str, expected: str) -> None:
        symbols = sp.symbols("Gvd K0 Hs Kmem")
        names = {symbol.name: symbol for symbol in symbols}
        self.assertEqual(sp.simplify(sp.sympify(actual, locals=names) - sp.sympify(expected, locals=names)), 0)

    def test_open_modulator_and_sensing_path_generates_feedback_denominator(self) -> None:
        derivation = solve_linear_system(open_modulator_system())

        self.assert_equivalent(derivation["generated_expression"], "Gvd*K0/(1+K0*Hs)")
        self.assertEqual(derivation["target"]["name"], "Gvc")
        self.assertEqual(len(derivation["denominator_provenance"]), 1)
        denominator = derivation["denominator_provenance"][0]
        self.assertEqual(denominator["source_equations"], ["eq_modulator", "eq_sense_path"])
        self.assertEqual(denominator["feedback_path"], "sense_path")
        self.assertIs(denominator["generated_by_solver"], True)
        self.assertIn("display_latex", denominator)
        self.assertEqual(derivation["elimination_metadata"]["diagnostic_equations_used"], [])

    def test_closed_equivalent_system_generates_product_without_new_denominator(self) -> None:
        derivation = solve_linear_system(closed_equivalent_system())

        self.assert_equivalent(derivation["generated_expression"], "Gvd*Kmem")
        self.assertEqual(derivation["denominator_provenance"], [])

    def test_nonlinear_unknown_product_fails(self) -> None:
        system = open_modulator_system()
        system["active_equations"][2]["rhs"] = "d_hat*vsense_hat"

        with self.assertRaisesRegex(LinearSystemError, "FAIL_NONLINEAR_IN_UNKNOWNS"):
            solve_linear_system(system)

    def test_target_role_conflict_fails(self) -> None:
        system = closed_equivalent_system()
        system["unknowns"].append("vc_hat")

        with self.assertRaisesRegex(LinearSystemError, "FAIL_VARIABLE_ROLE_CONFLICT"):
            solve_linear_system(system)

    def test_target_variable_not_declared_fails(self) -> None:
        system = closed_equivalent_system()
        system["target"]["output"] = "missing_hat"

        with self.assertRaisesRegex(LinearSystemError, "FAIL_TARGET_VARIABLE_NOT_DECLARED"):
            solve_linear_system(system)


if __name__ == "__main__":
    unittest.main()
