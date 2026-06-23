import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from linear_system_transfer import LinearSystemError, derive_linear_system_transfer


def open_loop_system() -> dict:
    return {
        "system_version": "0.4.5",
        "case_id": "linear-open-loop",
        "symbols": ["s", "Gvd", "Ke", "Hs"],
        "unknowns": ["d_hat", "vo_hat", "vsense_hat"],
        "inputs": ["vc_hat"],
        "diagnostic_outputs": [],
        "blocks": [
            {
                "id": "K_mod",
                "block_type": "open_block",
                "input_expression": "vc_hat-vsense_hat",
                "output": "d_hat",
            },
            {"id": "sense_path", "block_type": "primitive_equation"},
            {"id": "power_stage", "block_type": "primitive_equation"},
        ],
        "active_equations": [
            {"id": "eq_modulator", "block_id": "K_mod", "role": "active", "lhs": "d_hat", "rhs": "Ke*(vc_hat-vsense_hat)"},
            {"id": "eq_sense_path", "block_id": "sense_path", "role": "active", "lhs": "vsense_hat", "rhs": "Hs*d_hat"},
            {"id": "eq_power_stage", "block_id": "power_stage", "role": "active", "lhs": "vo_hat", "rhs": "Gvd*d_hat"},
        ],
        "diagnostic_equations": [],
        "target": {
            "name": "Gvc",
            "output": "vo_hat",
            "input": "vc_hat",
            "response_kind": "transfer_function",
        },
        "approximation_policy": {"declared": False, "items": [], "valid_frequency": "not_declared"},
    }


class LinearSystemTransferTests(unittest.TestCase):
    def assert_error(self, system: dict, code: str) -> None:
        with self.assertRaises(LinearSystemError) as context:
            derive_linear_system_transfer(system)
        self.assertEqual(context.exception.code, code)

    def test_open_modulator_and_sensing_path_are_eliminated_by_solver(self) -> None:
        derivation = derive_linear_system_transfer(open_loop_system())

        self.assertIn("Gvd", derivation["generated_expression"])
        self.assertIn("Ke", derivation["generated_expression"])
        self.assertIn("Hs", derivation["generated_expression"])
        self.assertEqual(derivation["target_transfer"], "Gvc")
        self.assertEqual(derivation["generated_by"], "linear_system_transfer.py")
        self.assertEqual(
            derivation["elimination_metadata"]["eliminated_variables"],
            ["d_hat", "vsense_hat"],
        )
        self.assertTrue(derivation["denominator_provenance"])
        self.assertTrue(derivation["denominator_provenance"][0]["generated_by_solver"])
        self.assertIn("eq_modulator", derivation["denominator_provenance"][0]["source_equations"])
        self.assertIn("eq_sense_path", derivation["denominator_provenance"][0]["source_equations"])

    def test_diagnostic_equations_do_not_affect_transfer_expression(self) -> None:
        base = open_loop_system()
        with_diagnostic = open_loop_system()
        with_diagnostic["diagnostic_equations"] = [
            {"id": "diag_vsense", "role": "diagnostic", "lhs": "vsense_hat", "rhs": "Hs*d_hat + injected_note"}
        ]

        self.assertEqual(
            derive_linear_system_transfer(base)["generated_expression"],
            derive_linear_system_transfer(with_diagnostic)["generated_expression"],
        )

    def test_eliminated_variable_is_allowed_only_as_diagnostic(self) -> None:
        system = open_loop_system()
        system["blocks"] = [
            {
                "id": "K_closed",
                "block_type": "closed_equivalent_block",
                "input": "vc_hat",
                "output": "d_hat",
                "eliminated_variables": ["vsense_hat"],
                "eliminated_equations": ["eq_sense_path"],
                "feedback_paths_already_closed": ["sense_path"],
            },
            {"id": "power_stage", "block_type": "primitive_equation"},
        ]
        system["unknowns"] = ["d_hat", "vo_hat"]
        system["diagnostic_outputs"] = ["vsense_hat"]
        system["active_equations"] = [
            {"id": "eq_closed_modulator", "block_id": "K_closed", "role": "active", "lhs": "d_hat", "rhs": "Kc*vc_hat"},
            {"id": "eq_power_stage", "block_id": "power_stage", "role": "active", "lhs": "vo_hat", "rhs": "Gvd*d_hat"},
        ]
        system["diagnostic_equations"] = [
            {"id": "diag_vsense", "role": "diagnostic", "lhs": "vsense_hat", "rhs": "Hs*d_hat"}
        ]
        derive_linear_system_transfer(system)

        system["active_equations"].append(
            {"id": "eq_sense_path", "block_id": "power_stage", "role": "active", "lhs": "vsense_hat", "rhs": "Hs*d_hat"}
        )
        self.assert_error(system, "FAIL_REINTRODUCED_ELIMINATED_INTERNAL_VARIABLE")

    def test_active_equation_requires_block_id(self) -> None:
        system = open_loop_system()
        del system["active_equations"][0]["block_id"]
        self.assert_error(system, "FAIL_ACTIVE_EQUATION_WITHOUT_BLOCK_ID")

    def test_linearity_is_checked_only_against_unknowns(self) -> None:
        allowed = open_loop_system()
        allowed["active_equations"][2]["rhs"] = "Gvd(s)*d_hat"
        derive_linear_system_transfer(allowed)

        nonlinear = open_loop_system()
        nonlinear["active_equations"][2]["rhs"] = "d_hat*vsense_hat"
        self.assert_error(nonlinear, "FAIL_NONLINEAR_IN_UNKNOWNS")

    def test_variable_role_and_target_declarations_are_strict(self) -> None:
        conflict = open_loop_system()
        conflict["unknowns"].append("vc_hat")
        self.assert_error(conflict, "FAIL_VARIABLE_ROLE_CONFLICT")

        missing_target = open_loop_system()
        missing_target["target"]["output"] = "missing_hat"
        self.assert_error(missing_target, "FAIL_TARGET_VARIABLE_NOT_DECLARED")

    def test_closed_equivalent_block_is_siso_only_in_v045(self) -> None:
        system = open_loop_system()
        system["blocks"] = [
            {
                "id": "K_closed",
                "block_type": "closed_equivalent_block",
                "input": "vc_hat",
                "output": "d_hat",
                "eliminated_variables": ["vsense_hat"],
                "eliminated_equations": ["eq_sense_path"],
                "feedback_paths_already_closed": ["sense_path"],
            },
            {"id": "power_stage", "block_type": "primitive_equation"},
        ]
        system["unknowns"] = ["d_hat", "vo_hat"]
        system["active_equations"] = [
            {"id": "eq_closed_modulator", "block_id": "K_closed", "role": "active", "lhs": "d_hat", "rhs": "K1*vc_hat + K2*vg_hat"},
            {"id": "eq_power_stage", "block_id": "power_stage", "role": "active", "lhs": "vo_hat", "rhs": "Gvd*d_hat"},
        ]
        system["inputs"] = ["vc_hat", "vg_hat"]
        self.assert_error(system, "FAIL_MIMO_CLOSED_EQUIVALENT_NOT_SUPPORTED_V045")

    def test_return_ratio_block_requires_loop_break(self) -> None:
        system = open_loop_system()
        system["blocks"][0] = {"id": "K_mod", "block_type": "return_ratio_block"}
        self.assert_error(system, "FAIL_RETURN_RATIO_LOOP_BREAK_REQUIRED")


if __name__ == "__main__":
    unittest.main()
