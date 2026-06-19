import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from fm_models import build_fm_model


class FmModelsZeroRampOnlyTests(unittest.TestCase):
    def test_zero_ramp_ccot_returns_constant_fm(self):
        result = build_fm_model({
            "control_family": "C-COT",
            "has_external_ramp": False,
            "parameters": {"m1": 1.0, "m2": -2.0, "Ts": 1e-6},
            "dirichlet_value": "(is_left+is_right)/2",
        })
        self.assertEqual(result["status"], "OK")
        self.assertEqual(result["Fm"]["type"], "constant")
        self.assertEqual(result["Fm"]["origin"], "sampled_data_derivation")
        self.assertEqual(result["Fm"]["dirichlet_reference"], "sampling.dirichlet_value")

    def test_external_ramp_ccot_is_hard_rejected_for_v04(self):
        result = build_fm_model({
            "control_family": "C-COT",
            "has_external_ramp": True,
            "parameters": {"m1": 1.0, "m2": -2.0, "mc": 0.3, "Ts": 1e-6},
        })
        self.assertEqual(result["status"], "REJECT_DYNAMIC_FM_REQUIRED_V05")
        self.assertEqual(result["severity"], "hard_fail")

    def test_nonzero_internal_paths_are_hard_rejected(self):
        cases = [
            ("has_internal_ramp", "REJECT_INTERNAL_RAMP_NOT_REGISTERED"),
            ("has_delay", "REJECT_DELAY_NOT_REGISTERED"),
            ("has_rc_injection", "REJECT_RC_INJECTION_NOT_REGISTERED"),
            ("has_filter_in_sense_path", "REJECT_SENSE_FILTER_NOT_REGISTERED"),
        ]
        for flag, status in cases:
            with self.subTest(flag=flag):
                result = build_fm_model({"control_family": "C-COT", flag: True})
                self.assertEqual(result["status"], status)
                self.assertEqual(result["severity"], "hard_fail")


if __name__ == "__main__":
    unittest.main()
