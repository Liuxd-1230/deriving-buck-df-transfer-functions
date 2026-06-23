import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from run_validation_checks import REQUIRED_CHECKS, build_unified_checker_result


class CheckerResultAggregationTests(unittest.TestCase):
    def test_checker_result_contains_all_required_checks(self) -> None:
        result = build_unified_checker_result(
            intake={"status": "COMPLETE"},
            classification={"path": "PROTOCOL_DERIVED_NEW", "validation_level": "PROTOCOL_DERIVED_UNVERIFIED"},
            proof={"validation": {"level": "PROTOCOL_DERIVED_UNVERIFIED"}},
            derivation={},
            report_text="候选传函，需要仿真确认",
        )

        self.assertEqual(result["checker_version"], "0.4.5")
        self.assertEqual(set(REQUIRED_CHECKS), set(result["checks"]))
        for check in result["checks"].values():
            self.assertIn(check["status"], {"PASS", "FAIL", "WARN", "NOT_APPLICABLE"})
            self.assertIn("reason", check)
            self.assertIn("blocking", check)
            self.assertIn("artifact", check)

    def test_forbidden_claim_fail_makes_overall_status_fail(self) -> None:
        result = build_unified_checker_result(
            classification={"validation_level": "PROTOCOL_DERIVED_UNVERIFIED"},
            report_text="This is the final transfer function and figure reproduced.",
        )

        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(result["checks"]["forbidden_claim_check"]["blocking"])

    def test_mismatch_unclear_blocks_figure_reproduced_claim(self) -> None:
        result = build_unified_checker_result(
            mismatch_report={
                "final_classification": "REFERENCE_TARGET_SEMANTICS_UNCLEAR",
                "forbidden_claims": ["FIGURE_REPRODUCED"],
            },
        )

        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(result["checks"]["mismatch_report_check"]["blocking"])

    def test_low_order_full_power_claim_is_blocking(self) -> None:
        result = build_unified_checker_result(
            derivation={"target_transfer": "Gvc", "expanded_target_expression": "1/(1+s/wz)"},
            claims=["FULL_POWER_STAGE_GVC"],
        )

        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(result["checks"]["power_stage_dynamics_check"]["blocking"])


if __name__ == "__main__":
    unittest.main()
