import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from check_forbidden_claims import scan_report_formula_rendering
from render_derivation_report import build_chinese_report


class ReportFormulaRenderingContractTests(unittest.TestCase):
    def test_report_renders_derivation_step_latex_as_typora_block_math(self) -> None:
        derivation = {
            "case_id": "linear-report",
            "target_transfer": "Gvc",
            "generated_expression": "Gvd*Ke/(Hs*Ke + 1)",
            "expanded_target_expression": "Gvd*Ke/(Hs*Ke + 1)",
            "derivation_steps": [
                {
                    "step_id": "target_definition",
                    "title": "目标传函",
                    "latex": "G_{vc}(s)=\\frac{\\hat v_o(s)}{\\hat v_c(s)}",
                    "explanation": "目标由结构化 target.output/input 字段生成。",
                    "source_artifact": "derivation.json",
                    "latex_origin": "solver_generated",
                    "provenance": "linear_system_transfer.py",
                },
                {
                    "step_id": "generated_transfer",
                    "title": "求解器生成候选传函",
                    "latex": "G_{vc}(s)=\\frac{G_{vd}K_e}{1+K_eH_s}",
                    "explanation": "该候选传函由 active equation system 自动消元得到。",
                    "source_artifact": "derivation.json",
                    "latex_origin": "solver_generated",
                    "provenance": "denominator_provenance",
                },
            ],
            "approximation_policy": {"declared": False, "items": [], "valid_frequency": "not_declared"},
            "validation": {"level": "PROTOCOL_DERIVED_UNVERIFIED"},
        }

        report = build_chinese_report({
            "intake": {"normalized": {"case_id": "linear-report", "target_transfer": "Gvc"}},
            "classification": {"path": "PROTOCOL_DERIVED_NEW", "validation_level": "PROTOCOL_DERIVED_UNVERIFIED"},
            "proof_object": {"transfer": {"target_transfer": "Gvc", "origin": "linear-system-pending"}},
            "derivation": derivation,
            "formula_origin": None,
            "checker_result": {"status": "PASS", "checks": {}, "errors": []},
            "bode_summary": None,
            "mismatch_report": None,
        })

        self.assertIn("$$\nG_{vc}(s)=\\frac{\\hat v_o(s)}{\\hat v_c(s)}\n$$", report)
        self.assertIn("$$\nG_{vc}(s)=\\frac{G_{vd}K_e}{1+K_eH_s}\n$$", report)
        self.assertEqual(
            scan_report_formula_rendering(report, derivation_steps=derivation["derivation_steps"])["status"],
            "PASS",
        )

    def test_untracked_core_formula_in_report_body_fails(self) -> None:
        text = "正文里裸写 Gvc(s)=Gvd*K/(1+K*H) 不是 derivation_steps 渲染。"
        result = scan_report_formula_rendering(text, derivation_steps=[])
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["code"], "FAIL_REPORT_CONTAINS_UNTRACKED_FORMULA")

    def test_step_latex_must_be_rendered_as_block_math(self) -> None:
        steps = [{
            "step_id": "generated_transfer",
            "title": "求解器生成候选传函",
            "latex": "G_{vc}(s)=\\frac{G_{vd}K_e}{1+K_eH_s}",
            "explanation": "...",
            "source_artifact": "derivation.json",
            "latex_origin": "solver_generated",
            "provenance": "linear_system_transfer.py",
        }]
        result = scan_report_formula_rendering(
            "G_{vc}(s)=\\frac{G_{vd}K_e}{1+K_eH_s}",
            derivation_steps=steps,
        )
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["code"], "FAIL_FORMULA_NOT_BLOCK_MATH")


if __name__ == "__main__":
    unittest.main()
