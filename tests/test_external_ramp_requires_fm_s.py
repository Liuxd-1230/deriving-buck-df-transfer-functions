import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from df_model_classifier import classify_intake


class ExternalRampDynamicFmBoundaryTests(unittest.TestCase):
    def test_dynamic_fm_s_external_ramp_is_not_registered_in_v031(self):
        result = classify_intake({
            "topology": "buck",
            "conduction_mode": "CCM",
            "phases": 1,
            "control_family": "external-ramp-cot-current-mode",
            "target": "Gvc",
            "dynamic_Fm_s": True,
            "model_id": "cot-cm-external-ramp-tian-2015",
        })
        self.assertEqual(result["path"], "UNSUPPORTED")
        self.assertIn("dynamic-Fm-s", result["unsupported_effects"])


if __name__ == "__main__":
    unittest.main()
