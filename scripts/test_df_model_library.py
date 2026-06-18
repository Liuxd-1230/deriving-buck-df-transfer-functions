#!/usr/bin/env python3
"""Tests for the paper-grounded Buck DF model registry."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

import sympy as sp


MODULE_PATH = Path(__file__).with_name("df_model_library.py")
SPEC = importlib.util.spec_from_file_location("df_model_library", MODULE_PATH)
assert SPEC and SPEC.loader
models = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = models
SPEC.loader.exec_module(models)

BUCK_MODULE_PATH = Path(__file__).with_name("df_buck_sympy.py")
BUCK_SPEC = importlib.util.spec_from_file_location("df_buck_sympy_for_models", BUCK_MODULE_PATH)
assert BUCK_SPEC and BUCK_SPEC.loader
buck = importlib.util.module_from_spec(BUCK_SPEC)
sys.modules[BUCK_SPEC.name] = buck
BUCK_SPEC.loader.exec_module(buck)


class ModelRegistryTests(unittest.TestCase):
    def test_registry_contains_only_supported_df_models(self) -> None:
        expected = {
            "cot-cm-li-lee-2010",
            "cot-cm-external-ramp-tian-2015",
            "rbcot-esr-lu-2023",
            "v2-cot-li-lee-2009",
        }
        self.assertEqual(set(models.list_models()), expected)

    def test_huang_average_model_is_explicitly_excluded(self) -> None:
        with self.assertRaisesRegex(models.ModelError, "average model"):
            models.generate_case("rbcot-internal-ramp-huang-2025", {})

    def test_unknown_model_reports_supported_ids(self) -> None:
        with self.assertRaises(models.ModelError) as caught:
            models.generate_case("not-a-model", {})
        message = str(caught.exception)
        self.assertIn("cot-cm-li-lee-2010", message)
        self.assertIn("rbcot-esr-lu-2023", message)


class CurrentSourceAdapterTests(unittest.TestCase):
    def test_adapter_recovers_the_original_three_input_current_relation(self) -> None:
        s, L, rL, Vg, D = sp.symbols("s L rL Vg D", nonzero=True)
        Fc, Fg, Fo = sp.symbols("Fc Fg Fo")
        uc, vg, vo = sp.symbols("uc vg vo")
        coefficients = models.current_source_to_duty_coefficients(
            Fc="Fc", Fg="Fg", Fo="Fo"
        )
        local = {name: value for name, value in locals().items() if isinstance(value, sp.Basic)}
        ac = sp.sympify(coefficients["a_c"], locals=local)
        ag = sp.sympify(coefficients["a_g"], locals=local)
        ao = sp.sympify(coefficients["a_o"], locals=local)
        ai = sp.sympify(coefficients["a_i"], locals=local)
        duty = ac * uc + ag * vg + ao * vo + ai * sp.Symbol("iL")
        recovered = sp.simplify((D * vg + Vg * duty - vo) / (s * L + rL))
        expected = Fc * uc + Fg * vg + Fo * vo
        self.assertEqual(sp.simplify(recovered - expected), 0)
        self.assertEqual(coefficients["coefficient_origin"], "derived-adapter")


def cot_parameters() -> dict[str, float]:
    return {
        "Vin": 12.0,
        "Vo": 1.2,
        "fs": 300e3,
        "L": 300e-9,
        "C": 4480e-6,
        "R": 0.1,
        "rL": 0.0,
        "rC": 0.75e-3,
        "Ri": 10e-3,
    }


class LiLee2010Tests(unittest.TestCase):
    def test_exact_model_generates_coefficients_from_physical_parameters(self) -> None:
        case = models.generate_case("cot-cm-li-lee-2010", cot_parameters(), "exact")
        self.assertEqual(set(case["modulator"]), {"a_c", "a_g", "a_o", "a_i"})
        self.assertEqual(case["coefficient_origin"], "derived-adapter")
        self.assertEqual(case["method"], "describing-function")
        self.assertIn("exp(-s*Ton)", case["paper_model"]["Fc"])

    def test_exact_current_df_has_inverse_sense_gain_dc_limit(self) -> None:
        case = models.generate_case("cot-cm-li-lee-2010", cot_parameters(), "exact")
        p = case["parameters"]
        s = sp.Symbol("s")
        table = {name: sp.Symbol(name) for name in p}
        table.update({"s": s, "exp": sp.exp, "pi": sp.pi})
        expression = sp.sympify(case["paper_model"]["Fc"], locals=table)
        substitutions = {table[name]: value for name, value in p.items()}
        dc = sp.limit(expression.subs(substitutions), s, 0)
        self.assertAlmostEqual(float(dc), 1 / cot_parameters()["Ri"], places=9)

    def test_pade_model_contains_paper_double_pole(self) -> None:
        case = models.generate_case("cot-cm-li-lee-2010", cot_parameters(), "pade")
        self.assertEqual(case["parameters"]["Q1"], str(2 / sp.pi))
        self.assertIn("s**2/w1**2", case["paper_model"]["Fc"])
        self.assertEqual(case["valid_frequency"]["basis"], "Li-Lee-2010-Eq10")


class TianExternalRampTests(unittest.TestCase):
    def test_exact_model_generates_four_coefficients_and_paper_paths(self) -> None:
        parameters = cot_parameters() | {"se_ratio": 1.0}
        case = models.generate_case(
            "cot-cm-external-ramp-tian-2015", parameters, "exact"
        )
        self.assertEqual(set(case["modulator"]), {"a_c", "a_g", "a_o", "a_i"})
        self.assertIn("exp(-s*Ton)", case["paper_model"]["Fc"])
        self.assertIn("exp(s*Tsw)", case["paper_model"]["Fg"])
        self.assertIn("Fc_low_order", case["paper_model"])

    def test_no_external_ramp_low_order_path_is_inverse_sense_gain(self) -> None:
        parameters = cot_parameters() | {"se_ratio": 0.0}
        case = models.generate_case(
            "cot-cm-external-ramp-tian-2015", parameters, "exact"
        )
        p = case["parameters"]
        s = sp.Symbol("s")
        table = {name: sp.Symbol(name) for name in p}
        table.update({"s": s, "exp": sp.exp, "pi": sp.pi})
        expression = sp.sympify(case["paper_model"]["Fc_low_order"], locals=table)
        substitutions = {table[name]: value for name, value in p.items()}
        reduced = sp.simplify(expression.subs(substitutions) - 1 / p["Ri"])
        self.assertEqual(reduced, 0)

    def test_external_ramp_pole_zero_and_frequency_limit_follow_paper(self) -> None:
        parameters = cot_parameters() | {"se_ratio": 1.0}
        case = models.generate_case(
            "cot-cm-external-ramp-tian-2015", parameters, "exact"
        )
        self.assertAlmostEqual(
            case["features_hz"]["moving_pole"], 300e3 / (3 * float(sp.pi))
        )
        self.assertAlmostEqual(case["features_hz"]["stationary_zero"], 300e3 / float(sp.pi))
        self.assertEqual(case["valid_frequency"]["max_hz"], 150e3)
        self.assertEqual(case["valid_frequency"]["basis"], "Tian-2015-Eq8-and-validation")


class Lu2023RbcotTests(unittest.TestCase):
    def test_model_generates_direct_control_and_output_ripple_paths(self) -> None:
        parameters = cot_parameters() | {"rC": 3.2e-3, "fs": 400e3}
        case = models.generate_case("rbcot-esr-lu-2023", parameters, "exact")
        self.assertEqual(case["modulator"]["a_c"], case["paper_model"]["Fdx"])
        self.assertEqual(case["modulator"]["a_o"], f"-({case['paper_model']['Fox']})")
        self.assertIn("exp(-s*Tsw)", case["paper_model"]["Fodx"])
        self.assertIn("1+Fox*Fp", case["paper_model"]["Floop_structure"])

    def test_output_perturbation_df_uses_the_plus_sign_from_lu_equation_8(self) -> None:
        parameters = cot_parameters() | {"rC": 3.2e-3, "fs": 400e3}
        case = models.generate_case("rbcot-esr-lu-2023", parameters, "exact")
        self.assertIn("+(rC/L+1/(R*C))/s", case["paper_model"]["Fodx"])

    def test_paper_power_stage_matches_buck_plant(self) -> None:
        parameters = cot_parameters() | {"rC": 3.2e-3, "fs": 400e3}
        case = models.generate_case("rbcot-esr-lu-2023", parameters, "exact")
        model = buck.derive_model(case)
        fp = buck.parse_expr(case["paper_model"]["Fp"], model["table"])
        ideal_inductor_plant = model["expressions"]["Gvd"].subs(model["symbols"]["rL"], 0)
        self.assertEqual(sp.simplify(fp - ideal_inductor_plant), 0)

    def test_feedback_sign_reproduces_lu_equation_11_structure(self) -> None:
        Fdx, Fox, Fp = sp.symbols("Fdx Fox Fp")
        generic = Fdx * Fp / (1 - (-Fox) * Fp)
        paper = Fdx * Fp / (1 + Fox * Fp)
        self.assertEqual(sp.simplify(generic - paper), 0)


class LiLee2009V2Tests(unittest.TestCase):
    def test_v2_model_is_exposed_as_direct_paper_transfer_not_fake_coefficients(self) -> None:
        parameters = cot_parameters() | {"C": 560e-6, "rC": 6e-3}
        case = models.generate_case("v2-cot-li-lee-2009", parameters, "pade")
        self.assertEqual(case["interface"], "direct-transfer-function")
        self.assertNotIn("modulator", case)
        self.assertIn("Gvc", case["paper_model"])
        self.assertIn("1+s*rC*C", case["paper_model"]["Gvc"])

    def test_oscon_case_passes_paper_stability_boundary(self) -> None:
        parameters = cot_parameters() | {"C": 560e-6, "rC": 6e-3}
        case = models.generate_case("v2-cot-li-lee-2009", parameters, "pade")
        self.assertTrue(case["stability"]["stable_by_paper_boundary"])
        self.assertGreater(case["stability"]["margin_seconds"], 0)

    def test_ceramic_case_fails_paper_stability_boundary(self) -> None:
        parameters = cot_parameters() | {"C": 100e-6, "rC": 1.4e-3}
        case = models.generate_case("v2-cot-li-lee-2009", parameters, "pade")
        self.assertFalse(case["stability"]["stable_by_paper_boundary"])
        self.assertLess(case["stability"]["margin_seconds"], 0)


class ModelBoundaryTests(unittest.TestCase):
    def test_missing_physical_parameter_fails_with_its_name(self) -> None:
        parameters = cot_parameters()
        del parameters["L"]
        with self.assertRaisesRegex(models.ModelError, "L"):
            models.generate_case("cot-cm-li-lee-2010", parameters, "exact")

    def test_multiphase_parameters_are_rejected(self) -> None:
        with self.assertRaisesRegex(models.ModelError, "single-phase"):
            models.generate_case(
                "cot-cm-li-lee-2010", cot_parameters() | {"phases": 2}, "exact"
            )

    def test_dcm_and_pulse_skipping_are_rejected(self) -> None:
        with self.assertRaisesRegex(models.ModelError, "CCM"):
            models.generate_case(
                "cot-cm-li-lee-2010", cot_parameters() | {"operating_mode": "DCM"}, "exact"
            )
        with self.assertRaisesRegex(models.ModelError, "pulse skipping"):
            models.generate_case(
                "cot-cm-li-lee-2010", cot_parameters() | {"pulse_skipping": True}, "exact"
            )


if __name__ == "__main__":
    unittest.main()
