import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from check_rc_memory_factor import check_rc_memory_factor
from tests.test_rc_state_kmod_memory_factor import rc_case


class RcStateComparatorRampPolicyTests(unittest.TestCase):
    def test_rc_derived_ramp_requires_memory_factor_p(self) -> None:
        artifact = rc_case()
        artifact["comparator_ramp_model"].pop("p")
        artifact["switching"].pop("Ts")

        result = check_rc_memory_factor(artifact)

        self.assertEqual(result["status"], "FAIL")
        self.assertIn("FAIL_MISSING_RC_MEMORY_FACTOR", result["errors"])


if __name__ == "__main__":
    unittest.main()
