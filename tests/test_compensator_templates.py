import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from compensator_templates import CompensatorTemplateError, build_compensator


class CompensatorTemplateTests(unittest.TestCase):
    def test_simplis_laplace_uses_s_plus_w_form_and_dc_gain(self):
        comp = build_compensator({
            "type": "SIMPLIS_LAPLACE",
            "KPZ": 8000,
            "wz1": 4000,
            "wp1": 50,
            "wp2": 400000,
            "frequency_scale_factor": 1,
            "form": "simplicis_s_plus_w",
        })
        self.assertEqual(comp["canonical_sympy_expr"], "KPZ*(s+F*wz1)/((s+F*wp1)*(s+F*wp2))")
        self.assertAlmostEqual(comp["dc_gain"], 8000 * 4000 / (50 * 400000))
        self.assertEqual(comp["formula_origin"], "compensator-template:SIMPLIS_LAPLACE")

    def test_ota_gm_ro_does_not_add_missing_capacitor(self):
        comp = build_compensator({"type": "OTA_GM_RO", "gm": "50e-6", "Ro": "160e6", "Cea": None})
        self.assertEqual(comp["canonical_sympy_expr"], "gm*Ro")
        self.assertNotIn("Cea", comp["parameters"])

    def test_type_ii_requires_frequency_units(self):
        with self.assertRaisesRegex(CompensatorTemplateError, "frequency_units"):
            build_compensator({"type": "TYPE_II", "K": 1, "wz1": 1000, "wp1": 100000})

    def test_type_iii_outputs_canonical_expression(self):
        comp = build_compensator({
            "type": "TYPE_III", "K": 2, "wz1": 1000, "wz2": 2000,
            "wp1": 100000, "wp2": 200000, "frequency_units": "rad_per_s",
        })
        self.assertEqual(
            comp["canonical_sympy_expr"],
            "K*(1+s/wz1)*(1+s/wz2)/(s*(1+s/wp1)*(1+s/wp2))",
        )


if __name__ == "__main__":
    unittest.main()
