#!/usr/bin/env python3
"""Render artifact-driven Chinese review reports for ESSF outputs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from artifact_workflow import WorkflowError, attach_workflow, verify_workflow
from report_manifest import ARTIFACT_PURPOSES, build_report_manifest, write_manifest


class ReportError(ValueError):
    """Raised when report rendering input cannot be read."""


REQUIRED_CHECKS = (
    "preflight_intake",
    "model_classification",
    "model_applicability",
    "formula_consistency",
    "proof_object_check",
    "linear_equation_system_check",
    "variable_role_check",
    "block_shape_check",
    "denominator_provenance_check",
    "normalization_check",
    "power_stage_dynamics_check",
    "validation_policy_check",
    "forbidden_claim_check",
    "report_formula_rendering_check",
    "mismatch_report_check",
    "rc_memory_factor_check",
)


def _load(path: str | Path | None) -> dict[str, Any] | None:
    if not path:
        return None
    value = Path(path)
    if not value.exists():
        return None
    try:
        data = json.loads(value.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ReportError(f"Invalid JSON artifact {value}: {exc}") from exc
    return data if isinstance(data, dict) else {"value": data}


def _case_id(artifacts: dict[str, dict[str, Any] | None]) -> str:
    for key in ("derivation", "proof_object", "intake", "classification"):
        artifact = artifacts.get(key)
        if not isinstance(artifact, dict):
            continue
        if artifact.get("case_id"):
            return str(artifact["case_id"])
        normalized = artifact.get("normalized")
        if isinstance(normalized, dict) and normalized.get("case_id"):
            return str(normalized["case_id"])
    return "unknown-case"


def _validation_level(artifacts: dict[str, dict[str, Any] | None]) -> str:
    for key in ("proof_object", "derivation", "classification"):
        artifact = artifacts.get(key) or {}
        validation = artifact.get("validation")
        if isinstance(validation, dict) and validation.get("level"):
            return str(validation["level"])
        if artifact.get("validation_level"):
            return str(artifact["validation_level"])
    return "UNKNOWN"


def _is_ask_user_only(intake: dict[str, Any] | None) -> bool:
    return isinstance(intake, dict) and intake.get("action") == "ASK_USER_ONLY"


def _has_blocking_fail(checker: dict[str, Any] | None) -> bool:
    if not isinstance(checker, dict):
        return False
    if checker.get("status") == "FAIL" and checker.get("blocking"):
        return True
    checks = checker.get("checks")
    if not isinstance(checks, dict):
        return False
    return any(
        isinstance(item, dict)
        and item.get("status") == "FAIL"
        and bool(item.get("blocking"))
        for item in checks.values()
    )


def _safe_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _formula_rows(formula_origin: dict[str, Any] | None, proof: dict[str, Any] | None) -> list[str]:
    rows = ["| 对象 | 公式 ID | 来源模型 | canonical expression | origin | validation |",
            "| --- | --- | --- | --- | --- | --- |"]
    formulas = []
    if isinstance(formula_origin, dict):
        formulas = formula_origin.get("formulas") or []
    if isinstance(formulas, list):
        for item in formulas:
            if not isinstance(item, dict):
                continue
            obj = item.get("object") or item.get("formula_object") or item.get("formula_id", "unknown")
            rows.append(
                "| {obj} | {fid} | {source} | `{expr}` | {origin} | {validation} |".format(
                    obj=obj,
                    fid=item.get("formula_id", "未提供"),
                    source=item.get("source_model_id", "未提供"),
                    expr=item.get("canonical_sympy_expr", item.get("expression", "未提供")),
                    origin=item.get("origin", item.get("source", "formula_origin.json")),
                    validation=item.get("validation", item.get("approximation", "未提供")),
                )
            )
    if len(rows) == 2 and isinstance(proof, dict):
        for binding in proof.get("formula_bindings", []) or []:
            if isinstance(binding, dict):
                rows.append(
                    f"| {binding.get('formula_id', 'unknown')} | {binding.get('formula_id', '未提供')} | "
                    f"{binding.get('source_model_id', '未提供')} | `{binding.get('expression', '未提供')}` | "
                    "proof_object.json | CHAIN_PARTIAL |"
                )
    if len(rows) == 2:
        rows.append("| 未提供 | 未提供 | 未提供 | `未提供` | 未提供 | 未提供 |")
    return rows


def _checker_rows(checker: dict[str, Any] | None) -> list[str]:
    rows = ["| checker | status | reason | blocking | related artifact |",
            "| --- | --- | --- | --- | --- |"]
    checks = checker.get("checks") if isinstance(checker, dict) else None
    if not isinstance(checks, dict):
        checks = {}
    for name in REQUIRED_CHECKS:
        item = checks.get(name)
        if isinstance(item, dict):
            status = item.get("status", "NOT_APPLICABLE")
            reason = item.get("reason", "")
            blocking = item.get("blocking", False)
            artifact = item.get("artifact", "")
        else:
            status = "NOT_APPLICABLE"
            reason = "未提供该检查 artifact。"
            blocking = False
            artifact = "未提供"
        rows.append(f"| {name} | {status} | {reason} | {blocking} | {artifact} |")
    if isinstance(checker, dict) and checker.get("errors"):
        rows.append(f"| checker_result.errors | {checker.get('status', 'FAIL')} | {_safe_json(checker.get('errors'))} | True | checker_result.json |")
    return rows


def _checkout_lines(artifacts: dict[str, dict[str, Any] | None], *, ask_only: bool = False) -> list[str]:
    lines = []
    key_fields = {
        "intake": "status, missing, action, normalized.sensing_layer",
        "classification": "path, validation_level, sensing_layer" if ask_only else "path, model_id, validation_level, sensing_layer",
        "proof_object": "classification, sampling, sensing_layer, pulse_structure, transfer",
        "formula_origin": "formula_ids, formulas[].formula_id, formulas[].origin",
        "derivation": "steps, expanded_target_expression, approximation_policy",
        "checker_result": "checks, status, errors",
        "bode_summary": "results, valid_frequency_limit_hz, validity",
        "mismatch_report": "measurement_semantics, final_classification",
    }
    for key, purpose in ARTIFACT_PURPOSES.items():
        availability = "已提供" if artifacts.get(key) is not None else "未提供"
        if ask_only and key == "classification":
            purpose = "ASK_USER_ONLY 阶段不得进入模型分类；若存在该 artifact，需要确认它不是本次未完成输入生成的模型选择。"
        lines.append(f"- {key}.json：{availability}。用途：{purpose} 关键字段：{key_fields[key]}。人工复查：打开这些字段核对证据链。")
    return lines


def _derivation_steps(artifacts: dict[str, dict[str, Any] | None], *, ask_only: bool) -> list[str]:
    if ask_only:
        return ["本 case 为 INCOMPLETE_INTAKE，未进入推导阶段。"]
    intake = artifacts.get("intake") or {}
    proof = artifacts.get("proof_object") or {}
    derivation = artifacts.get("derivation") or {}
    strict_steps = derivation.get("derivation_steps")
    if isinstance(strict_steps, list) and strict_steps:
        lines: list[str] = []
        reasoning = derivation.get("reasoning_method") if isinstance(derivation.get("reasoning_method"), dict) else {}
        if reasoning:
            lines.extend([
                str(reasoning.get("name", "derivation reasoning")),
                "Independent derivation path：" + _safe_json(reasoning.get("independent_derivation_path", [])),
                "Registry formula path：" + _safe_json(reasoning.get("registry_formula_path", [])),
                "",
            ])
        for step in strict_steps:
            if not isinstance(step, dict):
                continue
            lines.extend([
                f"### {step.get('title', step.get('step_id', '推导步骤'))}",
                "",
                "$$",
                str(step.get("latex", "")),
                "$$",
                "",
                str(step.get("explanation", "")),
                "",
                f"来源 artifact：`{step.get('source_artifact', '未提供')}`；latex_origin：`{step.get('latex_origin', '未提供')}`；provenance：`{step.get('provenance', '未提供')}`。",
                "",
            ])
        if lines:
            return lines
    normalized = intake.get("normalized") if isinstance(intake.get("normalized"), dict) else {}
    transfer = proof.get("transfer") if isinstance(proof.get("transfer"), dict) else {}
    lines = [
        f"1. event condition / comparator equation：{_safe_json(normalized.get('comparator_inputs', '未提供'))}",
        f"2. sampled variable / sensing path：{normalized.get('sampled_variable', '未提供')} / {_safe_json(normalized.get('sensing_layer', '未提供'))}",
        "3. perturbation variable definition：以 artifact 中的 sampling、modulator_io 或 transfer 字段为准；未提供时不补默认定义。",
        f"4. modulator 或 describing-function interface：{_safe_json(proof.get('modulator', '未提供'))}",
        f"5. power-stage interface：{_safe_json(proof.get('power_stage', '未提供'))}",
        f"6. loop gain / return ratio / closed-loop mapping：{_safe_json(proof.get('target_mapping', '未提供'))}",
        f"7. target transfer definition：{transfer.get('target_transfer', derivation.get('target_transfer', '未提供'))}",
        f"8. final candidate expression：`{transfer.get('expression', derivation.get('expanded_target_expression', '未提供'))}`",
    ]
    modulator = proof.get("modulator") if isinstance(proof.get("modulator"), dict) else {}
    if modulator.get("model_type") in {"a-star", "protocol-derived"}:
        lines.append("DF / a-star interface：`d_hat = a_c * c_hat + a_g * v_g_hat + a_o * v_o_hat + a_i * i_L_hat`。")
    if proof.get("sampling") or proof.get("pulse_structure") or proof.get("sideband"):
        sampling = proof.get("sampling") or {}
        pulse = proof.get("pulse_structure") or {}
        sideband = proof.get("sideband") or {}
        lines.extend([
            f"- sampling instant：{sampling.get('sampling_instant', '未提供')}",
            f"- left/right limit：{sampling.get('left_limit', '未提供')} / {sampling.get('right_limit', '未提供')}",
            f"- Dirichlet value：{sampling.get('dirichlet_value', '未提供')}",
            f"- pulse train structure：{pulse.get('type', '未提供')}",
            f"- d1 / d2：{pulse.get('d1', '未提供')} / {pulse.get('d2', '未提供')}",
            f"- 1-exp(-s*T0)：{pulse.get('frequency_factor', '未提供')}",
            f"- sideband mode / sideband sum：{sideband.get('mode', '未提供')} / {sideband.get('sum_expression', '未提供')}",
        ])
    reasoning = derivation.get("reasoning_method") if isinstance(derivation.get("reasoning_method"), dict) else {}
    if reasoning:
        lines.extend([
            "12-step Yan sampled-data reasoning",
            "Independent derivation path：" + _safe_json(reasoning.get("independent_derivation_path", [])),
            "Registry formula path：" + _safe_json(reasoning.get("registry_formula_path", [])),
        ])
    expressions = derivation.get("expressions") if isinstance(derivation.get("expressions"), dict) else {}
    target = derivation.get("target_transfer")
    if target and target in expressions:
        lines.append(f"{target}={expressions[target]}")
    return lines


def build_chinese_report(
    artifacts: dict[str, dict[str, Any] | None],
) -> str:
    intake = artifacts.get("intake")
    ask_only = _is_ask_user_only(intake)
    blocking_fail = _has_blocking_fail(artifacts.get("checker_result"))
    case_id = _case_id(artifacts)
    validation_level = _validation_level(artifacts)
    title = "未完成推导：信息不足 / 检查失败报告" if ask_only or blocking_fail else f"{case_id} 中文审查报告"
    normalized = (intake or {}).get("normalized") if isinstance((intake or {}).get("normalized"), dict) else {}
    classification = artifacts.get("classification") or {}
    proof = artifacts.get("proof_object") or {}
    derivation = artifacts.get("derivation") or {}
    bode = artifacts.get("bode_summary")
    mismatch = artifacts.get("mismatch_report")
    checker = artifacts.get("checker_result")

    lines = [f"# {title}", ""]
    lines.extend([
        "## 1. 结论摘要",
        "",
        (
            f"本次输入缺少 {', '.join(intake.get('missing', []))}，因此未进入推导阶段。"
            if ask_only and isinstance(intake, dict)
            else (
                "checker_result.json 存在 blocking FAIL，因此本报告停止在审查层，不输出最终结论。"
                if blocking_fail
                else f"本报告基于已存在 artifact 渲染，validation level 为 `{validation_level}`。报告不执行新推导、不补公式、不升级验证等级。"
            )
        ),
        "",
        "## 2. 输入信息与目标传函",
        "",
        f"- case_id：`{case_id}`",
        f"- target_transfer：`{normalized.get('target_transfer', derivation.get('target_transfer', '未提供'))}`",
        f"- intake action：`{(intake or {}).get('action', '未提供')}`",
        f"- missing：`{_safe_json((intake or {}).get('missing', []))}`",
        "",
        "## 3. 模型分类结果",
        "",
    ])
    if ask_only:
        lines.append("本 case 未进入模型分类阶段；ASK_USER_ONLY 报告不选择模型。")
    else:
        lines.extend([
            f"- path：`{classification.get('path', '未提供')}`",
            f"- model_id：`{classification.get('model_id', '未提供')}`",
            f"- validation_level：`{classification.get('validation_level', validation_level)}`",
        ])
    lines.extend([
        "",
        "## 4. sensing layer / sampling event / comparator 输入",
        "",
        f"- sensing_layer：`{_safe_json(normalized.get('sensing_layer', '未提供'))}`",
        f"- sampling_event：`{normalized.get('sampling_event', '未提供')}`",
        f"- comparator_inputs：`{_safe_json(normalized.get('comparator_inputs', '未提供'))}`",
        "",
        "## 5. 公式来源与注册信息",
        "",
        *_formula_rows(artifacts.get("formula_origin"), proof),
        "",
        "## 6. 逐步推导过程",
        "",
        *_derivation_steps(artifacts, ask_only=ask_only),
        "",
        "## 7. 代数消元或传函生成过程",
        "",
        (
            "本 case 为 INCOMPLETE_INTAKE，未进入推导阶段。"
            if ask_only
            else f"derivation.steps：`{_safe_json(derivation.get('steps', '未提供'))}`。expanded_target_expression：`{derivation.get('expanded_target_expression', '未提供')}`。"
        ),
        "",
        "## 8. 近似、低阶模型与适用边界",
        "",
        f"- approximation_policy：`{_safe_json(derivation.get('approximation_policy', '未提供'))}`",
        "Approximation：以上近似字段来自 derivation.json / proof_object.json，报告不重新解释或升级。",
        "若 checker 标出 LOW_ORDER_APPROXIMATION，该路径不保证复现完整功率级动态。",
        "",
        "## 9. 检查器结果",
        "",
        *_checker_rows(checker),
        "",
        "## 10. Bode / 数值结果",
        "",
        (
            f"Bode artifact 摘要：`{_safe_json(bode)}`。低频增益、主要极点/零点、LC 或功率级动态区域、ESR zero 区域、fs/2 附近行为、有效频率范围和相位行为均以 bode_summary.json / bode.csv 为准。"
            if bode
            else "本 case 未提供 Bode 或 validation 数值数据，因此不生成 Bode 分析结论。"
        ),
        "",
        "## 11. 与仿真或参考数据的 mismatch report",
        "",
        (
            f"mismatch_report：`{_safe_json(mismatch)}`。"
            if mismatch
            else "本 case 未提供参考仿真数据，因此不生成 mismatch report。"
        ),
        "",
        "## 12. validation level 与禁止声明",
        "",
        f"- validation level：`{validation_level}`",
        "本报告遵守 validation wording policy：降级、近似或语义不清时只能称为未验证模型、近似模型、需要仿真确认或待审计公式链。",
        "",
        "## 13. 二次 checkout 索引",
        "",
        *_checkout_lines(artifacts, ask_only=ask_only),
        "",
        "## 14. 未确认事项与下一步建议",
        "",
        (
            "请补充缺失字段后重新运行 intake gate；不得自动假设 sensing path、典型参数或默认模型。"
            if ask_only
            else "请按二次 checkout 索引复查 artifact 字段；若参考语义、sensing layer 或低阶近似仍不明确，不得升级验证声明。"
        ),
        "",
    ])
    return "\n".join(str(item) for item in lines)


def build_report_artifacts(
    derivation: dict[str, Any], checker: dict[str, Any]
) -> tuple[dict[str, Any], str]:
    """Compatibility API used by benchmark generation."""

    verify_workflow(derivation, expected_state="DERIVATION")
    verify_workflow(checker, expected_state="CHECKERS", predecessor=derivation)
    artifacts = {"derivation": derivation, "checker_result": checker}
    markdown = build_chinese_report(artifacts)
    manifest = {
        "report_version": "0.4",
        "case_id": _case_id(artifacts),
        "report": "derivation_report.md",
        "artifacts": {
            "derivation": {"path": "derivation.json", "purpose": ARTIFACT_PURPOSES["derivation"]},
            "checker_result": {"path": "checker_result.json", "purpose": ARTIFACT_PURPOSES["checker_result"]},
        },
    }
    return (
        attach_workflow(
            manifest,
            state="REPORT",
            intent=derivation["workflow"]["intent"],
            predecessor=checker,
        ),
        markdown,
    )


def _artifact_paths(args: argparse.Namespace) -> dict[str, Path | None]:
    return {
        "intake": Path(args.intake_status) if args.intake_status else None,
        "classification": Path(args.classification) if args.classification else None,
        "proof_object": Path(args.proof_object) if args.proof_object else None,
        "derivation": Path(args.derivation) if args.derivation else None,
        "formula_origin": Path(args.formula_origin) if args.formula_origin else None,
        "checker_result": Path(args.checker_result or args.checker) if (args.checker_result or args.checker) else None,
        "bode_summary": Path(args.bode_summary) if args.bode_summary else None,
        "mismatch_report": Path(args.mismatch_report) if args.mismatch_report else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Render an artifact-driven Chinese ESSF report.")
    parser.add_argument("--intake-status")
    parser.add_argument("--classification")
    parser.add_argument("--proof-object")
    parser.add_argument("--derivation")
    parser.add_argument("--formula-origin")
    parser.add_argument("--checker-result")
    parser.add_argument("--checker", help="Backward-compatible alias for --checker-result.")
    parser.add_argument("--bode-summary")
    parser.add_argument("--mismatch-report")
    parser.add_argument("--out", required=True)
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args()
    try:
        paths = _artifact_paths(args)
        artifacts = {key: _load(path) for key, path in paths.items()}
        markdown = build_chinese_report(artifacts)
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(markdown, encoding="utf-8")
        manifest = build_report_manifest(
            case_id=_case_id(artifacts),
            report_path=out_path,
            artifact_paths=paths,
        )
        write_manifest(Path(args.manifest), manifest)
        print(f"Wrote report: {out_path.resolve()}")
        return 0
    except (OSError, ReportError, WorkflowError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
