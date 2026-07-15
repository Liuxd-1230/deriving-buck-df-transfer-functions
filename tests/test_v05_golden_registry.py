import sys
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from tests.v05_runtime import golden_core
from registry_crosscheck import RegistryCrosscheckError, _validate_parameter_match
from v05_golden_cases import build_golden_case


class V05GoldenRegistryTests(unittest.TestCase):
    def test_golden_catalog_declares_four_families_and_thresholds(self):
        catalog = json.loads((ROOT / "examples" / "v05-golden-cases.json").read_text(encoding="utf-8"))
        self.assertEqual({item["family"] for item in catalog["goldens"]}, {
            "v2-cot", "current-mode-cot", "external-ramp-cot", "esr-ripple-rbcot",
        })
        self.assertTrue(all((ROOT / "examples" / item["schematic"]).is_file() for item in catalog["goldens"]))
        self.assertEqual(catalog["acceptance"]["sideband_max_M"], 64)
        forward = json.loads((ROOT / "examples" / "v05-forward-tests.json").read_text(encoding="utf-8"))
        self.assertEqual({item["expected_result"] for item in forward["cases"]}, {
            "TOPOLOGY_CONFIRMED_AFTER_USER_CHECK", "ASK_USER_ONLY",
        })
        self.assertIn("ambiguous-wire-crossing", forward["coverage"])
        for item in catalog["goldens"]:
            image = ROOT / "examples" / item["schematic"]
            intake, circuit, _ = build_golden_case(item["family"], image_path=image)
            self.assertEqual(intake["source_image"]["filename"], "schematic.svg")
            self.assertEqual(circuit["source_image"], intake["source_image"])

    def test_four_control_families_pass_internal_and_registry_gates(self):
        families = (
            "v2-cot", "current-mode-cot", "external-ramp-cot", "esr-ripple-rbcot",
        )
        for family in families:
            with self.subTest(family=family):
                artifacts = golden_core(family)
                self.assertEqual(artifacts["physics_checker_result"]["status"], "PASS")
                self.assertEqual(artifacts["registry_crosscheck"]["status"], "PASS")
                parameter_match = artifacts["registry_crosscheck"]["provenance"]["parameter_match"]
                self.assertEqual(parameter_match["status"], "MATCH")
                self.assertEqual(
                    set(parameter_match["checked_parameters"]),
                    {"Vin", "Vo", "fs", "L", "C", "R", "rC", "rL"},
                )
                check = artifacts["registry_crosscheck"]["checks"][0]
                self.assertLessEqual(check["max_magnitude_error_db"], 3.0)
                self.assertLessEqual(check["max_phase_error_deg"], 15.0)

    def test_registry_never_replaces_or_promotes_the_physical_model(self):
        artifact = golden_core("v2-cot")["registry_crosscheck"]
        self.assertFalse(artifact["provenance"]["may_replace_physics_model"])
        self.assertEqual(artifact["validation_status"], "PHYSICS_DERIVED_INTERNAL_VALIDATED")
        self.assertIn("never replace", artifact["authority_statement"])

    def test_registry_working_point_mismatch_is_rejected(self):
        artifacts = golden_core("v2-cot")
        parameters = dict(artifacts["physics_spec"]["registry_crosscheck"]["parameters"])
        parameters["Vin"] = 13.0
        with self.assertRaisesRegex(RegistryCrosscheckError, "working point does not match"):
            _validate_parameter_match(
                parameters,
                artifacts["hybrid_linearization"]["physical_provenance"],
                artifacts["physics_spec"],
                artifacts["periodic_orbit"],
            )

    def test_external_ramp_and_rbcot_trend_normalisation_is_explicit(self):
        for family in ("external-ramp-cot", "esr-ripple-rbcot"):
            check = golden_core(family)["registry_crosscheck"]["checks"][0]
            self.assertEqual(check["comparison_kind"], "normalised-trend")
            self.assertIsNotNone(check["normalization"])

    def test_external_ramp_reset_is_applied_in_named_physical_state(self):
        artifacts = golden_core("external-ramp-cot")
        mode = artifacts["mode_dae"]
        orbit = artifacts["periodic_orbit"]
        ramp_index = mode["variables"].index("x_RAMP_0")
        on_to_off = orbit["events"][0]
        off_to_on = orbit["events"][1]
        self.assertAlmostEqual(on_to_off["right_limit"][ramp_index], 0.0, places=12)
        self.assertGreater(off_to_on["left_limit"][ramp_index], 0.0)


if __name__ == "__main__":
    unittest.main()
