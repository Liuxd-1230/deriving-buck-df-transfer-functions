import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from check_rc_memory_factor import check_rc_memory_factor
from run_validation_checks import build_unified_checker_result
from tests.test_rc_state_kmod_memory_factor import rc_case


class RcStateBorrowedApproximationTests(unittest.TestCase):
    def test_borrowed_on_time_pair_is_warning_not_paper_grounding(self) -> None:
        artifact = rc_case()
        artifact["comparator_ramp_model"]["borrowed_approximation"] = "Li/Lee 2009 H_on"

        result = check_rc_memory_factor(artifact)

        self.assertIn(result["status"], {"WARN", "FAIL"})
        self.assertIn("WARN_BORROWED_ON_TIME_PAIR_APPROXIMATION", result["warnings"])

    def test_borrowed_approximation_still_fails_forbidden_verified_claims(self) -> None:
        result = build_unified_checker_result(
            classification={"validation_level": "PROTOCOL_DERIVED_UNVERIFIED"},
            report_text="borrowed approximation, paper-grounded, figure reproduced",
        )

        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(result["checks"]["forbidden_claim_check"]["blocking"])


if __name__ == "__main__":
    unittest.main()
