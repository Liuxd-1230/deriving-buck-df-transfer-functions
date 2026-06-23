import copy
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from artifact_workflow import WorkflowError, attach_workflow, verify_workflow
from build_proof_object import build_proof_object
from check_proof_object import check_proof_object
from df_model_classifier import classify_intake_status


def sampled_intake(control_family="C-COT", target="Tc"):
    sampled_variable = "vfb" if control_family.startswith("V-") else "is"
    slope_params = (
        {"m1": 4.0, "m2": 1.0, "D": 0.3, "mc": 0.0}
        if control_family in {"PCM", "PVM", "V-COT", "V-COFT"}
        else {"m1": 1.0, "m2": 4.0, "D": 0.3, "mc": 0.0}
    )
    artifact = {
        "intake_version": "0.4",
        "status": "COMPLETE",
        "missing": [],
        "action": "CONTINUE_TO_CLASSIFICATION",
        "normalized": {
            "case_id": f"{control_family.lower()}-{target.lower()}",
            "topology": "buck",
            "conduction_mode": "CCM",
            "phases": 1,
            "control_family": control_family,
            "target": target,
            "target_transfer": target,
            "sampling_event": "modulator input intersection",
            "switching_events": [{"name": "sample", "equation": "input-reference=0"}],
            "comparator_inputs": {"positive": sampled_variable, "negative": "reference"},
            "sampled_variable": sampled_variable,
            "fixed_interval": "Ton",
            "has_external_ramp": False,
            "has_internal_ramp": False,
            "has_delay": False,
            "has_rc_injection": False,
            "has_filter_in_sense_path": False,
            "parameters": {
                "Vin": 12.0, "Vo": 1.2, "fs": 100000.0, "Ts": 1e-5,
                "Ton": 3e-6, "T0": 3e-6, "L": 10e-6, "C": 100e-6,
                "R": 1.0, "rC": 0.01, **slope_params,
                "Hi": 0.1, "Hv": 0.2, "H": 0.1, "SumG": 0.05,
                "SidebandPulse": 0.05,
            },
        },
    }
    return attach_workflow(
        artifact, state="PREFLIGHT_INTAKE", intent="user-circuit-derivation"
    )


def build_chain(control_family="C-COT", target="Tc"):
    intake = sampled_intake(control_family, target)
    classification = classify_intake_status(intake)
    proof = build_proof_object(intake, classification)
    return intake, classification, proof


class SampledDerivationChainTests(unittest.TestCase):
    def test_registered_proof_binds_every_math_object(self):
        _, _, proof = build_chain("C-COT", "Tc")
        required = {
            "sampling", "Fm", "pulse_relation", "pulse_factor", "sideband",
            "GPWM", "Gid", "Ti", "Tc",
        }
        self.assertTrue(required.issubset(proof["formula_object_bindings"]))
        self.assertEqual(check_proof_object(proof)["status"], "PASS")

    def test_sideband_expression_cannot_be_replaced(self):
        _, _, proof = build_chain("C-COT", "Tc")
        proof["sideband"]["sum_expression"] = "999999"
        result = check_proof_object(proof)
        self.assertEqual(result["status"], "FAIL_FORMULA_CONSISTENCY")

    def test_sideband_full_sum_definition_cannot_be_rewritten(self):
        _, _, proof = build_chain("V-COT", "Tc")
        proof["sideband"]["summation_definition"] = "sum including n=0"
        result = check_proof_object(proof)
        self.assertEqual(result["status"], "FAIL_FORMULA_CONSISTENCY")

    def test_derivation_builds_current_loop_and_closed_loop(self):
        _, _, proof = build_chain("C-COT", "Tc")
        from sampled_derivation import derive_sampled_transfer

        derivation = derive_sampled_transfer(proof)
        verify_workflow(derivation, expected_state="DERIVATION", predecessor=proof)
        self.assertEqual(derivation["selected_loop"], "Ti")
        self.assertEqual(derivation["target_transfer"], "Tc")
        self.assertEqual(derivation["expressions"]["Tc"], "Ti/(1+Ti)")
        self.assertIn("Gid", derivation["expressions"])

    def test_truncated_sideband_numeric_target_substitutes_power_stage_sum(self):
        intake = sampled_intake("C-COT", "Tc")
        intake["normalized"]["sideband"] = {"mode": "TRUNCATED_SUM_M", "M": 1}
        intake = attach_workflow(
            {key: value for key, value in intake.items() if key != "workflow"},
            state="PREFLIGHT_INTAKE",
            intent="user-circuit-derivation",
        )
        classification = classify_intake_status(intake)
        proof = build_proof_object(intake, classification)
        from sampled_derivation import derive_sampled_transfer

        derivation = derive_sampled_transfer(proof)
        numeric_target = derivation["numeric_expanded_target_expression"]
        self.assertNotIn("SidebandPulse", numeric_target)
        self.assertNotIn("G(", numeric_target)
        self.assertIn("ws", numeric_target)
        self.assertIn("Vin", numeric_target)

    def test_derivation_checker_rejects_numeric_target_with_sideband_placeholder(self):
        intake = sampled_intake("C-COT", "Tc")
        intake["normalized"]["sideband"] = {"mode": "TRUNCATED_SUM_M", "M": 1}
        intake = attach_workflow(
            {key: value for key, value in intake.items() if key != "workflow"},
            state="PREFLIGHT_INTAKE",
            intent="user-circuit-derivation",
        )
        classification = classify_intake_status(intake)
        proof = build_proof_object(intake, classification)
        from sampled_derivation import derive_sampled_transfer
        from check_derivation import check_derivation_artifact

        derivation = derive_sampled_transfer(proof)
        derivation["numeric_expanded_target_expression"] = derivation["expanded_target_expression"]
        derivation = attach_workflow(
            derivation, state="DERIVATION", intent="user-circuit-derivation", predecessor=proof
        )
        result = check_derivation_artifact(derivation, proof)
        self.assertEqual(result["status"], "FAIL_DERIVATION_FORMULA_CONSISTENCY")
        self.assertTrue(any("sideband placeholder" in error for error in result["errors"]))

    def test_derivation_builds_voltage_loop_and_rejects_current_loop(self):
        _, _, proof = build_chain("V-COT", "Tc")
        from sampled_derivation import derive_sampled_transfer

        derivation = derive_sampled_transfer(proof)
        self.assertEqual(derivation["selected_loop"], "Tv")
        self.assertEqual(derivation["expressions"]["Tc"], "Tv/(1+Tv)")
        self.assertIn("Gvd", derivation["expressions"])
        self.assertNotIn("Gid", derivation["expressions"])

    def test_derivation_checker_rejects_changed_tc(self):
        _, _, proof = build_chain("C-COT", "Tc")
        from sampled_derivation import derive_sampled_transfer
        from check_derivation import check_derivation_artifact

        derivation = derive_sampled_transfer(proof)
        derivation["expressions"]["Tc"] = "Ti/(1-Ti)"
        derivation = attach_workflow(
            derivation, state="DERIVATION", intent="user-circuit-derivation", predecessor=proof
        )
        result = check_derivation_artifact(derivation, proof)
        self.assertEqual(result["status"], "FAIL_DERIVATION_FORMULA_CONSISTENCY")

    def test_unregistered_gvc_or_tloop_targets_do_not_enter_yan_registered_derivation(self):
        from build_proof_object import ProofBuildError

        for control_family, target in (("V-COT", "Gvc"), ("C-COT", "Tloop")):
            intake = sampled_intake(control_family, target)
            classification = classify_intake_status(intake)
            self.assertEqual(classification["path"], "UNSUPPORTED")
            with self.assertRaises(ProofBuildError):
                build_proof_object(intake, classification)

    def test_derivation_checker_emits_hash_linked_checker_artifact(self):
        _, _, proof = build_chain("V-COT", "Tc")
        from sampled_derivation import derive_sampled_transfer
        from check_derivation import build_checker_artifact

        derivation = derive_sampled_transfer(proof)
        checked = build_checker_artifact(derivation, proof)
        self.assertEqual(checked["status"], "PASS")
        verify_workflow(checked, expected_state="CHECKERS", predecessor=derivation)

    def test_checker_state_cannot_skip_derivation(self):
        _, _, proof = build_chain("C-COT", "Tc")
        with self.assertRaisesRegex(WorkflowError, "transition"):
            attach_workflow(
                {"status": "PASS"}, state="CHECKERS",
                intent="user-circuit-derivation", predecessor=proof,
            )

    def test_report_is_generated_from_checked_derivation_with_provenance(self):
        _, _, proof = build_chain("C-COT", "Tc")
        from sampled_derivation import derive_sampled_transfer
        from check_derivation import build_checker_artifact
        from render_derivation_report import build_report_artifacts

        derivation = derive_sampled_transfer(proof)
        checker = build_checker_artifact(derivation, proof)
        manifest, markdown = build_report_artifacts(derivation, checker)
        verify_workflow(manifest, expected_state="REPORT", predecessor=checker)
        self.assertIn("Dirichlet", markdown)
        self.assertIn("Gid", markdown)
        self.assertIn("Ti/(1+Ti)", markdown)
        self.assertIn("Approximation", markdown)
        self.assertIn("formula_id", markdown)

    def test_direct_gm_report_uses_gpwm_registered_expression(self):
        _, _, proof = build_chain("C-COT", "Gm")
        from sampled_derivation import derive_sampled_transfer
        from check_derivation import build_checker_artifact
        from render_derivation_report import build_report_artifacts

        derivation = derive_sampled_transfer(proof)
        checker = build_checker_artifact(derivation, proof)
        _, markdown = build_report_artifacts(derivation, checker)
        self.assertIn(derivation["expressions"]["GPWM"], markdown)

    def test_report_renders_twelve_step_yan_reasoning_and_dual_verification(self):
        _, _, proof = build_chain("V-COT", "Tc")
        from sampled_derivation import derive_sampled_transfer
        from check_derivation import build_checker_artifact
        from render_derivation_report import build_report_artifacts

        derivation = derive_sampled_transfer(proof)
        checker = build_checker_artifact(derivation, proof)
        _, markdown = build_report_artifacts(derivation, checker)
        self.assertIn("12-step Yan sampled-data reasoning", markdown)
        self.assertIn("Independent derivation path", markdown)
        self.assertIn("Registry formula path", markdown)
        self.assertIn("Tc=Tv/(1+Tv)", markdown)


if __name__ == "__main__":
    unittest.main()
