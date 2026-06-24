import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from check_rc_memory_factor import check_rc_memory_factor
from run_validation_checks import build_unified_checker_result


class V045CheckerPipelineRegressionTests(unittest.TestCase):
    def test_rc_memory_factor_checks_top_level_proof_ramp_model(self) -> None:
        proof = {
            "case_id": "rc-proof",
            "intake": {"normalized": {"sensing_layer": {"type": "direct_current_sense"}}},
            "comparator_ramp_model": {"type": "rc_derived_state"},
        }

        result = check_rc_memory_factor(proof)

        self.assertNotEqual(result["status"], "NOT_APPLICABLE")
        self.assertIn("FAIL_MISSING_RC_TAU", result["errors"])

    def test_rc_memory_factor_checks_nested_sensing_comparator_ramp_model(self) -> None:
        proof = {
            "case_id": "nested-rc-proof",
            "intake": {
                "normalized": {
                    "sensing_layer": {
                        "type": "custom_sensing_network",
                        "comparator_ramp_model": {"type": "rc_derived_state"},
                    }
                }
            },
        }

        result = check_rc_memory_factor(proof)

        self.assertNotEqual(result["status"], "NOT_APPLICABLE")
        self.assertIn("FAIL_MISSING_RC_TAU", result["errors"])

    def test_report_formula_rendering_runs_when_report_path_exists(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            report = Path(td) / "report.md"
            report.write_text("正文裸写 Gvc(s)=Gvd*Kmod", encoding="utf-8")
            result = build_unified_checker_result(
                classification={"validation_level": "PROTOCOL_DERIVED_UNVERIFIED"},
                derivation={},
                report_path=report,
            )

        check = result["checks"]["report_formula_rendering_check"]
        self.assertEqual(check["status"], "FAIL")
        self.assertNotEqual(check["status"], "NOT_APPLICABLE")

    def test_not_checked_dimension_signature_blocks_pass_claim(self) -> None:
        result = build_unified_checker_result(
            classification={"path": "PROTOCOL_DERIVED_NEW", "validation_level": "PROTOCOL_DERIVED_UNVERIFIED"},
            derivation={
                "derivation_version": "0.4.5",
                "generated_by": "linear_system_transfer.py",
                "denominator_provenance": [],
                "steps": [{"dimension_signature": "not-checked"}],
            },
            derivation_check={"status": "PASS", "errors": []},
        )

        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(result["checks"]["dimension_signature_check"]["blocking"])


if __name__ == "__main__":
    unittest.main()
