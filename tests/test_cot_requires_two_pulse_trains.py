import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from df_model_classifier import classify_intake


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


if __name__ == "__main__":
    unittest.main()
