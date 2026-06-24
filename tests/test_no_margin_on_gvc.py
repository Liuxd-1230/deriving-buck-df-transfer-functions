import unittest

from tests import test_power_stage_gvd_dimension as gvd_helpers


CANONICAL_GVD = "Vin*(1/(1/R + 1/(rC + 1/(s*C))))/(s*L + rL + 1/(1/R + 1/(rC + 1/(s*C))))"


class NoMarginOnGvcTests(unittest.TestCase):
    def run_compute(self, artifact: dict):
        return gvd_helpers.PowerStageGvdDimensionTests().run_compute(artifact)

    def test_gvc_manifest_does_not_report_stability_margins(self) -> None:
        result, manifest = self.run_compute(gvd_helpers.derivation(CANONICAL_GVD))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(manifest["stability_margins_status"], "NOT_APPLICABLE_NON_RETURN_RATIO")
        self.assertNotIn("phase_margin_deg", manifest)
        self.assertNotIn("gain_margin_db", manifest)
        self.assertEqual(manifest["magnitude_crossing_note"], "not a loop stability margin")

    def test_margin_fields_on_gvc_fail(self) -> None:
        artifact = gvd_helpers.derivation(CANONICAL_GVD)
        artifact["plot_metrics"] = {"phase_margin_deg": 45.0}

        result, _manifest = self.run_compute(artifact)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("FAIL_MARGIN_ON_NON_RETURN_RATIO", result.stderr)


if __name__ == "__main__":
    unittest.main()
