import copy
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from check_proof_object import check_proof_object


def valid_sampled_proof():
    from tests.test_sampled_derivation_chain import build_chain

    return build_chain("PCM", "Gm")[2]


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
