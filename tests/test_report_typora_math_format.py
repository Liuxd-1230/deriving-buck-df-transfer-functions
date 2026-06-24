import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from check_report_markdown_format import check_report_markdown_format
from render_derivation_report import build_chinese_report


def v045_derivation() -> dict:
    return {
        "schema_version": "0.4.5",
        "case_id": "report-v045",
        "target": {"name": "Gvc", "output": "vo_hat", "input": "vc_hat", "response_kind": "transfer_function"},
        "generated_expression": "Gvd*Kmem",
        "generated_expression_latex": "G_{vd}(s)K_{mem}(s)",
        "generated_expression_sha256": "0" * 64,
        "elimination_metadata": {"unknowns_eliminated": ["d_hat"], "active_equations_used": ["eq_modulator_closed", "eq_power_stage"], "diagnostic_equations_used": []},
        "denominator_provenance": [],
        "derivation_steps": [
            {
                "step_id": "target_definition",
                "title": "目标传函定义",
                "latex": "G_{vc}(s)=\\frac{\\hat v_o(s)}{\\hat v_c(s)}",
                "explanation": "其中 vc 是比较器正端小信号控制量。",
                "source_artifact": "derivation.json",
                "latex_origin": "solver_generated",
                "provenance": "linear_system_transfer.py",
            },
            {
                "step_id": "generated_expression",
                "title": "候选传函",
                "latex": "G_{vc}(s)=G_{vd}(s)K_{mem}(s)",
                "explanation": "该表达式由 typed active equations 消元得到。",
                "source_artifact": "derivation.json",
                "latex_origin": "solver_generated",
                "provenance": "linear_system_transfer.py",
            },
        ],
        "derivation_steps_sha256": "1" * 64,
    }


class ReportTyporaMathFormatTests(unittest.TestCase):
    def test_report_renders_derivation_steps_as_typora_block_math(self) -> None:
        derivation = v045_derivation()
        text = build_chinese_report({
            "derivation": derivation,
            "checker_result": {"status": "PASS", "blocking": False, "checks": {}, "errors": []},
        })

        self.assertIn("## 目标传函定义\n\n$$\nG_{vc}(s)=\\frac{\\hat v_o(s)}{\\hat v_c(s)}\n$$\n\n其中 vc", text)
        self.assertEqual(check_report_markdown_format(text, derivation)["status"], "PASS")

    def test_report_checker_rejects_untracked_core_formula(self) -> None:
        derivation = v045_derivation()
        text = "## bad\n\nGvc(s)=Gvd*Kmem\n"

        result = check_report_markdown_format(text, derivation)

        self.assertEqual(result["status"], "FAIL")
        self.assertIn("FAIL_REPORT_CONTAINS_UNTRACKED_FORMULA", result["errors"])

    def test_blocking_fail_report_does_not_display_candidate_transfer(self) -> None:
        derivation = v045_derivation()
        text = build_chinese_report({
            "derivation": derivation,
            "checker_result": {
                "status": "FAIL",
                "blocking": True,
                "checks": {"linear_system_semantics": {"status": "FAIL", "reason": "FAIL_DIMENSION_SIGNATURE_MISMATCH", "blocking": True, "artifact": "linear_equation_system.json"}},
                "errors": ["FAIL_DIMENSION_SIGNATURE_MISMATCH"],
            },
        })

        self.assertIn("FAIL_DIMENSION_SIGNATURE_MISMATCH", text)
        self.assertNotIn("G_{vc}(s)=G_{vd}(s)K_{mem}(s)", text)
        self.assertNotIn("Gvd*Kmem", text)


if __name__ == "__main__":
    unittest.main()
