import copy
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from check_proof_object import check_proof_object


def valid_sampled_proof():
    return {
        "proof_version": "0.4",
        "case_id": "valid-sampled-dirichlet",
        "intake": {"status": "COMPLETE", "normalized": {"target_transfer": "Gm"}},
        "classification": {
            "path": "SAMPLED_DATA_REGISTERED",
            "part_family": "SAMPLED_DATA_REGISTERED_PART_I_PCM_VCM_PVM_VVM",
            "model_id": "yan-2022-part-i-pcm-buck",
        },
        "formula_bindings": [{
            "formula_id": "yan-2022-part-i.pcm-fm-zero-ramp",
            "source_model_id": "yan-2022-part-i-pcm-buck",
            "interface": "sampled-data-modulator",
            "dimension_signature": "1/slope_time",
            "expression": "1/((m2-m1)*Ts/2)",
        }],
        "sampling": {
            "sampling_instant": "intersection(is,iref)",
            "sampled_variable": "is",
            "left_limit": "is(k-)",
            "right_limit": "is(k+)",
            "dirichlet_value": "(is(k-)+is(k+))/2",
            "dirichlet_required": True,
        },
        "Fm": {
            "type": "constant",
            "expression": "1/((m2-m1)*Ts/2)",
            "origin": "sampled_data_derivation",
            "depends_on": ["m1", "m2", "Ts"],
            "dirichlet_reference": "sampling.dirichlet_value",
            "derivation_steps": ["uses sampling.dirichlet_value to define sampled is(k)"],
        },
        "sideband": {"mode": "SYMBOLIC_FULL_SUM", "sum_expression": "sum(Gid(s+j*n*ws))"},
        "modulator_io": {
            "input": "is",
            "output": "d",
            "definition": "Gm=-d_hat/is_hat",
            "sign_convention": "negative",
        },
        "target_mapping": {
            "available_registered_outputs": ["Gm"],
            "requested_target": "Gm",
            "mapping_rule": "direct sampled-data modulator output",
            "mapping_status": "REGISTERED_DIRECT",
        },
        "modulator": {"model_type": "Gm", "expression": "Fm", "origin": "sampled_data_registered"},
        "transfer": {"target_transfer": "Gm", "expression": "Fm"},
        "validation": {
            "level": "SAMPLED_DATA_REGISTERED_PARTIAL",
            "completed": ["sampled-data-contract"],
            "missing": ["paper-figure-reproduction"],
        },
    }


class SampledDataDirichletTests(unittest.TestCase):
    def test_sampled_data_proof_requires_dirichlet_fields(self):
        proof = valid_sampled_proof()
        del proof["sampling"]["left_limit"]
        result = check_proof_object(proof)
        self.assertEqual(result["status"], "FAIL_DIRICHLET_INCOMPLETE")

    def test_fm_must_reference_dirichlet_value(self):
        proof = valid_sampled_proof()
        proof["Fm"].pop("dirichlet_reference")
        proof["Fm"]["derivation_steps"] = ["uses sampled current"]
        result = check_proof_object(proof)
        self.assertEqual(result["status"], "FAIL_FM_WITHOUT_DIRICHLET_REFERENCE")

    def test_valid_dirichlet_sampled_data_proof_passes_contract(self):
        result = check_proof_object(valid_sampled_proof())
        self.assertEqual(result["status"], "PASS")

    def test_sampled_data_registered_proof_requires_formula_binding(self):
        proof = valid_sampled_proof()
        proof["formula_bindings"] = []
        result = check_proof_object(proof)
        self.assertEqual(result["status"], "FAIL_FORMULA_CONSISTENCY")

    def test_unsupported_sampled_data_target_mapping_fails(self):
        proof = valid_sampled_proof()
        proof["target_mapping"]["requested_target"] = "Gvc"
        proof["target_mapping"]["mapping_status"] = "UNSUPPORTED"
        result = check_proof_object(proof)
        self.assertEqual(result["status"], "FAIL_TARGET_MAPPING")


if __name__ == "__main__":
    unittest.main()
