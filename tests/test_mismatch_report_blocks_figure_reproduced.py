import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from mismatch_report import build_mismatch_report
from run_validation_checks import build_unified_checker_result


class MismatchBlocksFigureReproducedTests(unittest.TestCase):
    def test_reference_target_semantics_unclear_blocks_figure_reproduced(self) -> None:
        mismatch = build_mismatch_report({
            "case_id": "unclear-reference",
            "target": "Gvc",
            "measurement_semantics": {"injection_point": "unknown"},
        })

        result = build_unified_checker_result(mismatch_report=mismatch)

        self.assertEqual(mismatch["final_classification"], "REFERENCE_TARGET_SEMANTICS_UNCLEAR")
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(result["checks"]["mismatch_report_check"]["blocking"])


if __name__ == "__main__":
    unittest.main()
