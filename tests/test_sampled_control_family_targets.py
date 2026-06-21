import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_proof_object import ProofBuildError, build_proof_object
from df_model_classifier import classify_intake_status
from tests.test_sampled_derivation_chain import sampled_intake


class SampledControlFamilyTargetTests(unittest.TestCase):
    def test_current_cot_rejects_voltage_loop_target(self):
        intake = sampled_intake("C-COT", "Tv")
        with self.assertRaisesRegex(ProofBuildError, "not registered"):
            build_proof_object(intake, classify_intake_status(intake))

    def test_voltage_cot_rejects_current_loop_target(self):
        intake = sampled_intake("V-COT", "Ti")
        with self.assertRaisesRegex(ProofBuildError, "not registered"):
            build_proof_object(intake, classify_intake_status(intake))


if __name__ == "__main__":
    unittest.main()
