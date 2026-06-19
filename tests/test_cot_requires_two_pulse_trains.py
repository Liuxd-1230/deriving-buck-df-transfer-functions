import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from df_model_classifier import classify_intake
from check_proof_object import check_proof_object


class CotTwoPulseTrainBoundaryTests(unittest.TestCase):
    def test_two_pulse_train_cot_is_not_silently_claimed_in_v031(self):
        result = classify_intake({
            "topology": "buck",
            "conduction_mode": "CCM",
            "phases": 1,
            "control_family": "custom-cot",
            "target": "Gvc",
            "requires_two_pulse_trains": True,
        })
        self.assertEqual(result["path"], "UNSUPPORTED")
        self.assertIn("cot-two-pulse-train", result["unsupported_effects"])

    def test_part_ii_sampled_data_proof_requires_two_pulse_trains(self):
        proof = {
            "proof_version": "0.4",
            "case_id": "bad-ccot-pulse",
            "intake": {"status": "COMPLETE", "normalized": {"target_transfer": "Gm"}},
            "classification": {
                "path": "SAMPLED_DATA_REGISTERED",
                "part_family": "SAMPLED_DATA_REGISTERED_PART_II_CCOT_CCOFT",
                "model_id": "yan-2022-part-ii-ccot-buck-zero-ramp",
            },
            "formula_bindings": [{
                "formula_id": "yan-2022-part-ii.ccot-gpwm-pulse-factor",
                "source_model_id": "yan-2022-part-ii-ccot-buck-zero-ramp",
                "interface": "sampled-data-modulator",
                "dimension_signature": "duty/input",
                "expression": "Fm*(1-exp(-s*T0))",
            }],
            "sampling": {
                "sampling_instant": "intersection(is,iref)",
                "sampled_variable": "is",
                "left_limit": "is(k-)",
                "right_limit": "is(k+)",
                "dirichlet_value": "(is(k-)+is(k+))/2",
                "dirichlet_required": True,
            },
            "pulse_structure": {
                "type": "SINGLE_PULSE_TRAIN",
                "frequency_factor": "1",
            },
            "Fm": {
                "type": "constant",
                "expression": "1/((m2-m1)*Ts/2)",
                "origin": "sampled_data_derivation",
                "dirichlet_reference": "sampling.dirichlet_value",
            },
            "sideband": {"mode": "SYMBOLIC_FULL_SUM", "sum_expression": "sum(Gid(s+j*n*ws))"},
            "modulator_io": {"input": "is", "output": "dsum", "definition": "Gm=-dsum_hat/is_hat", "sign_convention": "negative"},
            "target_mapping": {"available_registered_outputs": ["Gm"], "requested_target": "Gm", "mapping_rule": "direct", "mapping_status": "REGISTERED_DIRECT"},
            "modulator": {"model_type": "Gm", "expression": "Fm*(1-exp(-s*Ton))", "origin": "sampled_data_registered"},
            "transfer": {"target_transfer": "Gm", "expression": "Fm*(1-exp(-s*Ton))"},
            "validation": {"level": "SAMPLED_DATA_REGISTERED_PARTIAL", "completed": [], "missing": []},
        }
        result = check_proof_object(proof)
        self.assertEqual(result["status"], "FAIL_COT_TWO_PULSE_TRAINS")


if __name__ == "__main__":
    unittest.main()
