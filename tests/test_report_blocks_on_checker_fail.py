import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from render_derivation_report import build_chinese_report


class ReportBlocksOnCheckerFailTests(unittest.TestCase):
    def test_blocking_checker_fail_uses_incomplete_title(self) -> None:
        report = build_chinese_report({
            "intake": {"status": "COMPLETE", "normalized": {"case_id": "blocked-case", "target_transfer": "Gvc"}},
            "classification": {"path": "NEAR_MODEL", "validation_level": "PROTOCOL_DERIVED_UNVERIFIED"},
            "checker_result": {
                "status": "FAIL",
                "blocking": True,
                "checks": {
                    "rc_memory_factor_check": {
                        "status": "FAIL",
                        "reason": "FAIL_RC_DERIVED_RAMP_SLOPE_ONLY",
                        "blocking": True,
                        "artifact": "checker_result.json",
                    }
                },
            },
        })

        self.assertTrue(report.startswith("# 未完成推导：信息不足 / 检查失败报告"))
        self.assertIn("rc_memory_factor_check", report)
        self.assertIn("FAIL_RC_DERIVED_RAMP_SLOPE_ONLY", report)


if __name__ == "__main__":
    unittest.main()
