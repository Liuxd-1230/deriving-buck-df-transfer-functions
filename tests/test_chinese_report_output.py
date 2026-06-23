import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RENDERER = ROOT / "scripts" / "render_derivation_report.py"

REQUIRED_HEADINGS = [
    "## 1. 结论摘要",
    "## 2. 输入信息与目标传函",
    "## 3. 模型分类结果",
    "## 4. sensing layer / sampling event / comparator 输入",
    "## 5. 公式来源与注册信息",
    "## 6. 逐步推导过程",
    "## 7. 代数消元或传函生成过程",
    "## 8. 近似、低阶模型与适用边界",
    "## 9. 检查器结果",
    "## 10. Bode / 数值结果",
    "## 11. 与仿真或参考数据的 mismatch report",
    "## 12. validation level 与禁止声明",
    "## 13. 二次 checkout 索引",
    "## 14. 未确认事项与下一步建议",
]


def write_json(root: Path, name: str, value: dict) -> Path:
    path = root / name
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def minimal_artifacts(root: Path) -> dict[str, Path]:
    paths = {
        "intake": write_json(root, "intake_status.json", {
            "intake_version": "0.4",
            "status": "COMPLETE",
            "missing": [],
            "action": "CONTINUE_TO_CLASSIFICATION",
            "normalized": {
                "case_id": "report-case",
                "target_transfer": "Tc",
                "sensing_layer": {"type": "direct_current_sense", "validation": "registered"},
                "sampling_event": "intersection(is,iref)",
                "comparator_inputs": {"positive": "is", "negative": "iref"},
            },
        }),
        "classification": write_json(root, "classification.json", {
            "path": "SAMPLED_DATA_REGISTERED",
            "model_id": "yan-2022-part-ii-ccot-buck-zero-ramp",
            "validation_level": "SAMPLED_DATA_REGISTERED_PARTIAL",
        }),
        "proof_object": write_json(root, "proof_object.json", {
            "case_id": "report-case",
            "classification": {"path": "SAMPLED_DATA_REGISTERED"},
            "sampling": {
                "sampling_instant": "intersection(is,iref)",
                "left_limit": "is(k-)",
                "right_limit": "is(k+)",
                "dirichlet_value": "(is(k-)+is(k+))/2",
            },
            "pulse_structure": {"type": "COT_TWO_PULSE_TRAINS", "d1": "d1", "d2": "d2", "frequency_factor": "1-exp(-s*T0)"},
            "sideband": {"mode": "TRUNCATED_SUM_M", "sum_expression": "sideband_sum"},
            "modulator": {"model_type": "GPWM", "expression": "GPWM"},
            "target_mapping": {"mapping_rule": "Tc=Ti/(1+Ti)", "mapping_status": "REGISTERED_DERIVED"},
            "power_stage": {"Gid": {"expression": "Gid"}, "Gvd": {"expression": "Gvd"}},
            "transfer": {"target_transfer": "Tc", "expression": "Ti/(1+Ti)"},
            "validation": {"level": "SAMPLED_DATA_REGISTERED_PARTIAL", "completed": [], "missing": []},
        }),
        "derivation": write_json(root, "derivation.json", {
            "case_id": "report-case",
            "target_transfer": "Tc",
            "expanded_target_expression": "Ti/(1+Ti)",
            "steps": [{"object": "Ti", "formula_id": "f-ti", "expression": "Hi*Gid*GPWM"}],
            "approximation_policy": {"items": ["TRUNCATED_SUM_M"], "valid_frequency": "fs/2"},
            "validation": {"level": "SAMPLED_DATA_REGISTERED_PARTIAL"},
        }),
        "formula_origin": write_json(root, "formula_origin.json", {
            "formula_ids": ["f-ac", "f-gid", "f-ti", "f-tc", "f-sideband"],
            "formulas": [
                {"object": "a_c", "formula_id": "f-ac", "source_model_id": "common", "canonical_sympy_expr": "Fc", "origin": "formula_registry.yaml", "validation": "CHAIN_PARTIAL"},
                {"object": "Gid", "formula_id": "f-gid", "source_model_id": "yan", "canonical_sympy_expr": "Gid", "origin": "formula_registry.yaml", "validation": "CHAIN_PARTIAL"},
                {"object": "Ti", "formula_id": "f-ti", "source_model_id": "yan", "canonical_sympy_expr": "Hi*Gid*GPWM", "origin": "block composition", "validation": "CHAIN_PARTIAL"},
                {"object": "Tc", "formula_id": "f-tc", "source_model_id": "yan", "canonical_sympy_expr": "Ti/(1+Ti)", "origin": "formula_registry.yaml", "validation": "CHAIN_PARTIAL"},
                {"object": "sideband", "formula_id": "f-sideband", "source_model_id": "yan", "canonical_sympy_expr": "sideband_sum", "origin": "paper_contract_registry.yaml", "validation": "CHAIN_PARTIAL"},
            ],
        }),
        "checker_result": write_json(root, "checker_result.json", {
            "status": "PASS",
            "checks": {
                "preflight_intake": {"status": "PASS", "reason": "完整", "blocking": True, "artifact": "intake_status.json"},
                "model_classification": {"status": "PASS", "reason": "已分类", "blocking": True, "artifact": "classification.json"},
            },
            "errors": [],
        }),
        "bode_summary": write_json(root, "bode_summary.json", {"results": {"Tc": {"low_frequency_gain": "0 dB", "validity": "WITHIN_DECLARED_RANGE"}}}),
        "mismatch_report": write_json(root, "mismatch_report.json", {"final_classification": "UNKNOWN"}),
    }
    return paths


class ChineseReportOutputTests(unittest.TestCase):
    def test_report_contains_all_chinese_headings_in_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = minimal_artifacts(root)
            out = root / "report.md"
            manifest = root / "report_manifest.json"

            result = subprocess.run(
                [
                    sys.executable,
                    str(RENDERER),
                    "--intake-status", str(paths["intake"]),
                    "--classification", str(paths["classification"]),
                    "--proof-object", str(paths["proof_object"]),
                    "--derivation", str(paths["derivation"]),
                    "--formula-origin", str(paths["formula_origin"]),
                    "--checker-result", str(paths["checker_result"]),
                    "--bode-summary", str(paths["bode_summary"]),
                    "--mismatch-report", str(paths["mismatch_report"]),
                    "--out", str(out),
                    "--manifest", str(manifest),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                timeout=60,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            text = out.read_text(encoding="utf-8")
            positions = [text.index(heading) for heading in REQUIRED_HEADINGS]
            self.assertEqual(positions, sorted(positions))


if __name__ == "__main__":
    unittest.main()
