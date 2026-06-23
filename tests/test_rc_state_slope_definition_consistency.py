import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from check_rc_memory_factor import check_rc_memory_factor
from tests.test_rc_state_kmod_memory_factor import rc_case


class RcStateSlopeDefinitionConsistencyTests(unittest.TestCase):
    def test_v0_over_tau_source_must_match_numeric_value(self) -> None:
        artifact = rc_case()
        artifact["comparator_ramp_model"] |= {
            "sf_source": "V0_over_tau",
            "V0": 1.2,
            "sf": 1.0,
        }

        result = check_rc_memory_factor(artifact)

        self.assertEqual(result["status"], "FAIL")
        self.assertIn("FAIL_INCONSISTENT_RC_SLOPE_DEFINITION", result["errors"])

    def test_measured_average_falling_slope_must_be_labeled(self) -> None:
        artifact = rc_case()
        artifact["comparator_ramp_model"] |= {
            "sf_source": "V0_over_tau",
            "sf": 0.1249e6,
            "measured_average_falling_slope": 0.1249e6,
        }

        result = check_rc_memory_factor(artifact)

        self.assertEqual(result["status"], "FAIL")
        self.assertIn("FAIL_INCONSISTENT_RC_SLOPE_DEFINITION", result["errors"])


if __name__ == "__main__":
    unittest.main()
