import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from run_validation_checks import build_unified_checker_result


class ForbiddenClaimsHardGateTests(unittest.TestCase):
    def test_forbidden_claims_are_blocking_at_unverified_level(self) -> None:
        result = build_unified_checker_result(
            classification={"validation_level": "PROTOCOL_DERIVED_UNVERIFIED"},
            report_text="候选模型，但错误写成 已验证传函 和 figure reproduced。",
        )

        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(result["checks"]["forbidden_claim_check"]["blocking"])


if __name__ == "__main__":
    unittest.main()
