import unittest

from tests import test_power_stage_gvd_dimension as gvd_helpers


CANONICAL_GVD = "Vin*(1/(1/R + 1/(rC + 1/(s*C))))/(s*L + rL + 1/(1/R + 1/(rC + 1/(s*C))))"


class KmodDcGainSanityTests(unittest.TestCase):
    def run_compute(self, artifact: dict):
        return gvd_helpers.PowerStageGvdDimensionTests().run_compute(artifact)

    def test_closed_equivalent_rc_memory_kmod_dc_includes_d_factor(self) -> None:
        result, manifest = self.run_compute(gvd_helpers.derivation(CANONICAL_GVD))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertAlmostEqual(manifest["low_frequency_sanity"]["Kmod_dc_gain_abs"], 0.0752, delta=0.002)
        self.assertIn("Kmod_dc_gain_sign", manifest["low_frequency_sanity"])

    def test_missing_d_factor_fails_for_closed_equivalent_kmod(self) -> None:
        artifact = gvd_helpers.derivation(CANONICAL_GVD)
        artifact["linear_equation_system"]["coefficient_definitions"][1]["expression"] = "(1-p)/(sf*Ts) * (1 - p*exp(-s*Ts))/(1-p)"

        result, _manifest = self.run_compute(artifact)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FAIL_KMOD_DC_GAIN_MISSING_D_FACTOR", result.stderr)


if __name__ == "__main__":
    unittest.main()
