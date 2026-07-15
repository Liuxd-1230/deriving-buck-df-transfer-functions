import json
import csv
import sys
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from schema_validation import validate_artifact
from physics_checker import load_external_validation, run_physics_checkers
from tests.v05_runtime import full_v2


class V05HybridPhysicsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.artifacts = full_v2()
        cls.mode = cls.artifacts["mode_dae"]
        cls.orbit = cls.artifacts["periodic_orbit"]
        cls.linear = cls.artifacts["hybrid_linearization"]
        cls.checker = cls.artifacts["physics_checker_result"]

    def test_mode_dae_keeps_descriptor_and_algebraic_equations(self):
        self.assertEqual(len(self.mode["modes"]), 2)
        for mode in self.mode["modes"]:
            self.assertEqual(mode["rank"]["dynamic"], 2)
            self.assertGreater(mode["rank"]["algebraic"], 0)
            kinds = {item["kind"] for item in mode["equations"]}
            self.assertIn("KCL", kinds)
            self.assertIn("KVL", kinds)
            self.assertIn("switch_constraint", kinds)
        self.assertTrue(self.mode["physical_explanation"]["no_handwritten_active_equations"])

    def test_periodic_orbit_meets_all_physics_residuals_and_ccm(self):
        self.assertLessEqual(self.orbit["fixed_point"]["scaled_residual"], 1e-7)
        self.assertLessEqual(self.orbit["balances"]["scaled_kcl_kvl_residual"], 1e-7)
        self.assertLessEqual(self.orbit["balances"]["power_balance_scaled_residual"], 1e-7)
        self.assertGreater(self.orbit["balances"]["minimum_inductor_current"], 0.0)
        self.assertTrue(all(item["status"] == "PASS" for item in self.orbit["checks"]))

    def test_saltation_and_poincare_projection_are_both_preserved(self):
        guard = next(item for item in self.linear["event_linearization"] if item["type"] == "guard")
        self.assertIn("Xi", guard)
        self.assertIn("Pi", guard)
        self.assertFalse(np.allclose(np.asarray(guard["Xi"]), np.asarray(guard["Pi"])))
        self.assertIn("saltation_monodromy", self.linear)

    def test_analytic_poincare_matches_independent_switching_finite_difference(self):
        independent = self.checker["independent_poincare"]
        self.assertLessEqual(independent["Ad_relative_error"], 1e-3)
        self.assertLessEqual(independent["Bd_relative_error"], 1e-3)
        self.assertTrue(independent["does_not_reuse_affine_flow_or_guard_root"])

    def test_z_response_continuous_baseband_and_sidebands_are_distinct(self):
        self.assertEqual(self.linear["target"]["authoritative_domain"], "z")
        self.assertTrue(self.linear["sampled_frequency_response"])
        self.assertTrue(self.linear["continuous_baseband_response"])
        self.assertTrue(self.linear["within_cycle_response"]["converged"])
        self.assertLessEqual(self.linear["within_cycle_response"]["selected_max_M"], 64)
        self.assertTrue(all(item["selected_M"] >= 3 for item in self.linear["within_cycle_response"]["probes"]))

    def test_modal_residues_participation_and_parameter_sensitivities_are_reported(self):
        self.assertEqual(self.linear["modal_interpretation"]["status"], "AVAILABLE")
        self.assertTrue(self.linear["modal_interpretation"]["modes"])
        statuses = {item["status"] for item in self.linear["parameter_sensitivities"]}
        self.assertTrue(statuses <= {"PASS", "NOT_APPLICABLE_ZERO_NOMINAL"})
        categories = {item["category"] for item in self.linear["parameter_sensitivities"]}
        self.assertTrue({"inductance", "capacitance", "ESR", "load", "Ton"} <= categories)

    def test_every_v05_artifact_validates_against_its_schema(self):
        mapping = {
            "mode_dae": "mode_dae.schema.json",
            "periodic_orbit": "periodic_orbit.schema.json",
            "hybrid_linearization": "hybrid_linearization.schema.json",
            "physics_checker_result": "physics_checker_result.schema.json",
            "registry_crosscheck": "registry_crosscheck.schema.json",
            "report_manifest": "physics_report_manifest.schema.json",
        }
        for key, schema in mapping.items():
            with self.subTest(key=key):
                validate_artifact(self.artifacts[key], schema)

    def test_report_expands_the_full_physics_argument(self):
        report = (self.artifacts["output_dir"] / "report.md").read_text(encoding="utf-8")
        for heading in (
            "电路识别与原图证据", "模式电流路径、储能与 MNA/DAE", "周期稳态轨道",
            "事件梯度与 Saltation", "Poincaré 离散状态空间", "周期内连续响应与边带",
            "Floquet 模态、参与因子与残量", "参数灵敏度", "Registry 独立交叉检查",
            "截面采样频响", "周期内连续基波", "边带 Fourier 系数", "逐频点差异",
        ):
            self.assertIn(heading, report)
        manifest = self.artifacts["report_manifest"]
        self.assertEqual(manifest["validation_status"], "PHYSICS_DERIVED_INTERNAL_VALIDATED")

    def test_user_supplied_switching_data_can_upgrade_external_evidence(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            csv_path = Path(td) / "external.csv"
            metadata_path = Path(td) / "metadata.json"
            with csv_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["frequency_hz", "magnitude_db", "phase_deg"])
                writer.writeheader()
                writer.writerows({key: row[key] for key in writer.fieldnames} for row in self.linear["continuous_baseband_response"])
            target = self.artifacts["physics_spec"]["target"]
            metadata_path.write_text(json.dumps({
                "target": target["name"], "input_port": target["input"], "output_port": target["output"],
                "sign_convention": "matches confirmed Circuit IR", "operating_point": self.artifacts["physics_spec"]["inputs"],
                "source": "independent switching fixture",
            }), encoding="utf-8")
            dataset = load_external_validation(csv_path, metadata_path, self.artifacts["physics_spec"])
            checked = run_physics_checkers(
                self.mode, self.orbit, self.linear, self.artifacts["physics_spec"],
                external_dataset=dataset,
            )
        self.assertEqual(checked["validation_status"], "PHYSICS_DERIVED_EXTERNAL_CROSSCHECKED")


if __name__ == "__main__":
    unittest.main()
