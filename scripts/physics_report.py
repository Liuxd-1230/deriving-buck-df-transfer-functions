#!/usr/bin/env python3
"""Artifact-only paper-style report renderer for the v0.5 physical path."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from physics_workflow import attach_physics_workflow, verify_physics_workflow
from schema_validation import validate_artifact


class PhysicsReportError(ValueError):
    """Raised when hard gates prohibit a physics report."""


def _matrix(value: Any) -> str:
    return "```json\n" + json.dumps(value, ensure_ascii=False, indent=2) + "\n```"


def _table(headers: list[str], rows: list[list[Any]]) -> str:
    if not rows:
        return "（无）"
    head = "| " + " | ".join(headers) + " |"
    rule = "| " + " | ".join("---" for _ in headers) + " |"
    body = ["| " + " | ".join(str(cell).replace("|", "\\|") for cell in row) + " |" for row in rows]
    return "\n".join([head, rule, *body])


def render_physics_report(
    circuit_ir: dict[str, Any], physics_spec: dict[str, Any], mode_dae: dict[str, Any],
    orbit: dict[str, Any], linearization: dict[str, Any], checker: dict[str, Any],
    crosscheck: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    verify_physics_workflow(crosscheck, expected_state="REGISTRY_CROSSCHECK", predecessor=checker)
    if checker["status"] != "PASS":
        raise PhysicsReportError("PHYSICS_CHECKERS contains an unoverridden hard failure")
    if crosscheck["status"] == "FAIL":
        raise PhysicsReportError("REGISTRY_CROSSCHECK contains an unoverridden benchmark failure")
    target = linearization["target"]
    component_rows = []
    for component in circuit_ir["components"]:
        value = component.get("value")
        value_text = ""
        if isinstance(value, dict):
            value_text = f"{value['magnitude']} {value['unit']}"
        component_rows.append([
            component["id"], component["type"], json.dumps(component.get("terminals", {}), ensure_ascii=False),
            json.dumps(component.get("orientation", {}), ensure_ascii=False), value_text,
            json.dumps(component.get("parameters", {}), ensure_ascii=False),
            component.get("source_evidence", ""),
        ])
    net_rows = [[
        f"N{index:02d}", net["id"], json.dumps(net.get("aliases", []), ensure_ascii=False),
        json.dumps(net.get("evidence_regions", []), ensure_ascii=False),
    ] for index, net in enumerate(circuit_ir["nets"], start=1)]
    mode_sections = []
    for mode in mode_dae["modes"]:
        mode_sections.append(
            f"### 模式 `{mode['id']}`\n\n"
            f"秩：descriptor={mode['rank']['descriptor']}，dynamic={mode['rank']['dynamic']}，algebraic={mode['rank']['algebraic']}。\n\n"
            + _table(["方程", "类型", "物理内容", "来源元件"], [[item["id"], item["kind"], item["text"], item.get("component_id", item.get("net_id", ""))] for item in mode["equations"]])
            + "\n\n`E`：\n\n" + _matrix(mode["E"])
            + "\n\n`A`：\n\n" + _matrix(mode["A"])
            + "\n\n`B`：\n\n" + _matrix(mode["B"])
            + "\n\n`b`：\n\n" + _matrix(mode["b"])
        )
    path_rows = [[
        mode_id,
        json.dumps(item.get("conducting_devices", []), ensure_ascii=False),
        item.get("switch_node_constraint", ""), item.get("path", ""),
        item.get("inductor_constitutive_law", ""),
        json.dumps(item.get("capacitor_constitutive_laws", []), ensure_ascii=False),
        item.get("expected_energy_direction", ""),
    ] for mode_id, item in mode_dae["physical_explanation"]["current_paths"].items()]
    interval_rows = [[
        item["mode"], item["start_time"], item["duration"],
        orbit["events"][index]["type"], orbit["events"][index].get("expression", "fixed"),
        orbit["events"][index].get("Fdot"),
    ] for index, item in enumerate(orbit["mode_intervals"])]
    event_limit_rows = [[
        item["index"], item["from_mode"], item["to_mode"], item["time"],
        json.dumps(dict(zip(mode_dae["variables"], item["left_limit"])), ensure_ascii=False),
        json.dumps(dict(zip(mode_dae["variables"], item["right_limit"])), ensure_ascii=False),
    ] for item in orbit["events"]]
    event_sections = []
    for event in linearization["event_linearization"]:
        event_sections.append(
            f"### 事件 {event['index']}：`{event['from_mode']} → {event['to_mode']}`\n\n"
            f"类型：{event['type']}；guard：`{event.get('expression')}`；$\\dot F={event.get('Fdot')}$。\n\n"
            f"梯度 $F_x$：`{event.get('gradient_x')}`；$F_u$：`{event.get('gradient_u')}`。\n\n"
            "Saltation $\\Xi$：\n\n" + _matrix(event["Xi"])
            + "\n\n输入事件灵敏度 $\\Xi_u$：\n\n" + _matrix(event["Xi_u"])
            + "\n\n事件到事件 Poincaré 投影 $\\Pi$：\n\n" + _matrix(event["Pi"])
            + "\n\n输入投影 $\\Pi_u$：\n\n" + _matrix(event["Pi_u"])
        )
    modal_rows = [[
        item["multiplier"]["real"], item["multiplier"]["imag"], item["magnitude"],
        item["angle_deg"], json.dumps(item["residue"]),
        json.dumps(item["physical_energy_state_amplitude"], ensure_ascii=False),
    ] for item in linearization["modal_interpretation"].get("modes", [])]
    sensitivity_rows = [[
        item["parameter"], item["category"], item["nominal"], item["status"],
        json.dumps(item.get("normalised_local_sensitivity", {}), ensure_ascii=False),
    ] for item in linearization["parameter_sensitivities"]]
    check_rows = [[
        item.get("code"), item.get("status"), item.get("value", ""), item.get("limit", item.get("limits", "")),
        json.dumps(item.get("override", {}), ensure_ascii=False) if item.get("override") else "",
    ] for item in [*checker["checks"], *crosscheck["checks"]]]
    sideband_rows = [[
        item["frequency_hz"], item["selected_M"], item["converged"],
        item["delta_magnitude_db"], item["delta_phase_deg"],
    ] for item in linearization["within_cycle_response"].get("probes", [])]
    sampled_rows = [[
        item["frequency_hz"], item["magnitude_db"], item["phase_deg"]
    ] for item in linearization["sampled_frequency_response"]]
    baseband_rows = [[
        item["frequency_hz"], item["magnitude_db"], item["phase_deg"],
        item["response"]["real"], item["response"]["imag"],
    ] for item in linearization["continuous_baseband_response"]]
    sideband_spectrum_rows = []
    for probe in linearization["within_cycle_response"].get("probes", []):
        for harmonic_text, response in probe.get("coefficients", {}).items():
            sideband_spectrum_rows.append([
                probe["frequency_hz"], harmonic_text,
                probe.get("sideband_frequency_hz", {}).get(harmonic_text),
                response["real"], response["imag"],
            ])
    registry_comparison_rows = [[
        item.get("frequency_hz"), item.get("physics_magnitude_db"),
        item.get("registry_magnitude_db"), item.get("magnitude_error_db"),
        item.get("phase_error_deg"),
    ] for item in crosscheck.get("comparison", [])]
    report = f"""# {circuit_ir['case_id']}：v0.5 物理优先 Buck 小信号推导报告

## 摘要与证据等级

本报告以用户确认的 Circuit IR 为物理真源，通过元件 stamping 生成 Hybrid MNA/DAE，求周期固定点，再由 guard/reset 的事件梯度与 saltation matrix 组成 Poincaré 模型。离散周期模型是权威结果；论文 registry 仅作独立交叉检查。

- 验证状态：`{crosscheck['validation_status']}`
- 工作流：`{' → '.join(crosscheck['workflow']['history'])}`
- 目标：`{target['name']}`，`{target['input']} → {target['output']}`
- Poincaré 截面：`{json.dumps(physics_spec['poincare_section'], ensure_ascii=False)}`
- Floquet 稳定性：`{linearization['floquet']['stable']}`（不稳定是真实结果，不构成推导失败）

## 1. 电路识别与原图证据

- 原图 SHA-256：`{circuit_ir['source_image']['sha256']}`
- 原图尺寸：{circuit_ir['source_image']['width_px']} × {circuit_ir['source_image']['height_px']} px
- Circuit IR SHA-256：`{circuit_ir['workflow']['artifact_sha256']}`
- 确认人：`{circuit_ir['confirmation']['confirmed_by']}`

{_table(['ID', '类型', '端子', '极性/电流方向', '数值', '参数', '识别依据'], component_rows)}

节点编号、别名与原图证据区域：

{_table(['节点编号', '稳定 net ID', '别名', '原图归一化区域'], net_rows)}

歧义记录：

{_table(['ID', '类型', '说明', '阻塞', '状态', '解决'], [[item['id'], item['kind'], item['description'], item['blocking'], item['status'], item.get('resolution', '')] for item in circuit_ir['ambiguities']])}

## 2. 工作点、端口、符号与近似

- 输入工作点：`{json.dumps(physics_spec['inputs'], ensure_ascii=False)}`
- 保真度：`{physics_spec['fidelity']}`
- 近似：`{json.dumps(physics_spec['approximations'], ensure_ascii=False)}`
- loop break：`{json.dumps(physics_spec.get('loop_break'), ensure_ascii=False)}`

{_table(['端口', '角色', '量', '表达式', '符号约定'], [[item['name'], item['role'], item['quantity'], item['expression'], item['sign_convention']] for item in circuit_ir['ports']])}

## 3. 模式电流路径、储能与 MNA/DAE

模式电流路径来自确认后的开关赋值；电感/电容本构关系来自同一份元件 stamp。储能元件：`{json.dumps(mode_dae['energy_states'], ensure_ascii=False)}`。所有活动方程均由元件 stamp 生成，不由 agent 手写。

{_table(['模式', '导通器件', '开关节点约束', '电流路径', '电感定律', '电容定律', '能量方向'], path_rows)}

{''.join(mode_sections)}

## 4. 周期稳态轨道

shooting 固定点缩放残差为 `{orbit['fixed_point']['scaled_residual']}`，周期为 `{orbit['events'][-1]['time']}` s，最小电感电流为 `{orbit['balances']['minimum_inductor_current']}` A。

{_table(['模式', '起始时刻/s', '持续时间/s', '事件类型', 'guard', 'Fdot'], interval_rows)}

{_table(['事件', '起始模式', '下一模式', '时刻/s', '左极限', '右极限'], event_limit_rows)}

物理平衡：

{_matrix(orbit['balances'])}

## 5. 事件梯度与 Saltation

{''.join(event_sections)}

## 6. Poincaré 离散状态空间

$$x_{{k+1}}=A_d x_k+B_d u_k,\\qquad y_k=C_d x_k+D_d u_k$$

`Ad`：

{_matrix(linearization['state_space']['Ad'])}

`Bd`：

{_matrix(linearization['state_space']['Bd'])}

`Cd` / `Dd`：

{_matrix({'Cd': linearization['state_space']['Cd'], 'Dd': linearization['state_space']['Dd'], 'inputs': linearization['state_space']['inputs'], 'outputs': linearization['state_space']['outputs']})}

事件到事件 Floquet/Poincaré 乘子：`{json.dumps(linearization['floquet']['multipliers'])}`；谱半径 `{linearization['floquet']['spectral_radius']}`。环境坐标中的截面投影可能引入零乘子。common-time saltation monodromy 乘子：`{json.dumps(linearization['saltation_monodromy']['multipliers'])}`。

## 7. 目标传函与连续低频近似

Poincaré 截面采样的权威 z 域状态模型给出：

$$ {target['name']}(z)={target['z_expression']} $$

- 分子：`{target['numerator']}`
- 分母：`{target['denominator']}`
- 极点：`{target['poles']}`
- 零点：`{target['zeros']}`

采样频响严格沿 $z=e^{{j\\omega T_s}}$ 计算；请求的模拟输出传函再由周期内分段变分方程重构为连续基波。低频 s 域结果只作非权威展开：`{linearization['low_frequency_approximation']['expression']}`，阶数 `{linearization['low_frequency_approximation']['order']}`。

截面采样频响：

{_table(['频率/Hz', '幅值/dB', '相位/deg'], sampled_rows)}

## 8. 周期内连续响应与边带

边带由分段变分方程重构并作 Fourier 投影，从 `M=3` 倍增；最大 `M={linearization['within_cycle_response'].get('limits', {}).get('max_M')}`。收敛状态：`{linearization['within_cycle_response'].get('converged')}`。

{_table(['频率/Hz', '选定 M', '收敛', '相邻幅差/dB', '相邻相差/deg'], sideband_rows)}

周期内连续基波：

{_table(['频率/Hz', '幅值/dB', '相位/deg', 'Re', 'Im'], baseband_rows)}

收敛截断内的边带 Fourier 系数：

{_table(['基带频率/Hz', 'k', 'f+k·fs / Hz', 'Re', 'Im'], sideband_spectrum_rows)}

## 9. Floquet 模态、参与因子与残量

模态归因同时使用参与因子、输入输出残量和参数灵敏度；不按极点外观命名。零点默认策略：`{linearization['modal_interpretation'].get('default_zero_attribution')}`。

{_table(['Re(λ)', 'Im(λ)', '|λ|', '角度/deg', '残量', '物理能量状态幅度'], modal_rows)}

## 10. 参数灵敏度

下表为归一化中心差分局部灵敏度；每个扰动都会重新生成 MNA、重求轨道和事件线性化。

{_table(['参数', '类别', '标称值', '状态', '归一化灵敏度'], sensitivity_rows)}

## 11. Registry 独立交叉检查

状态：`{crosscheck['status']}`。{crosscheck['authority_statement']}

{_matrix({'checks': crosscheck['checks'], 'provenance': crosscheck['provenance']})}

逐频点差异：

{_table(['频率/Hz', '物理模型/dB', 'registry/dB', '幅差/dB', '相差/deg'], registry_comparison_rows)}

## 12. 物理检查、override 与证据边界

{_table(['检查码', '状态', '值', '阈值', 'override'], check_rows)}

独立 Jacobian 校验使用 `solve_ivp(DOP853)` 的真实切换时域轨迹与中心有限差分，不复用解析矩阵指数传播或 guard root finder：`{json.dumps(checker['independent_poincare'], ensure_ascii=False)}`。

边界声明：本报告未启动 SIMPLIS。外部验证只有在用户上传频率、幅值、相位、target、端口/符号、loop break、工作点与来源元数据后才会计入。平均模型只能作低频交叉检查；registry 公式不能替代此电路的物理推导，也不能自动提升验证等级。任何 override 都永久降级为 `FORCED_PHYSICS_OVERRIDE_UNVERIFIED`。
"""
    report_sha = hashlib.sha256(report.encode("utf-8")).hexdigest()
    artifact = {
        "manifest_version": "0.5", "case_id": circuit_ir["case_id"],
        "registry_crosscheck_sha256": crosscheck["workflow"]["artifact_sha256"],
        "report_sha256": report_sha, "validation_status": crosscheck["validation_status"],
        "artifacts": {
            "circuit_ir.json": circuit_ir["workflow"]["artifact_sha256"],
            "physics_spec.json": physics_spec["workflow"]["artifact_sha256"],
            "mode_dae.json": mode_dae["workflow"]["artifact_sha256"],
            "periodic_orbit.json": orbit["workflow"]["artifact_sha256"],
            "hybrid_linearization.json": linearization["workflow"]["artifact_sha256"],
            "physics_checker_result.json": checker["workflow"]["artifact_sha256"],
            "registry_crosscheck.json": crosscheck["workflow"]["artifact_sha256"],
        },
    }
    artifact = attach_physics_workflow(artifact, state="REPORT", predecessor=crosscheck)
    validate_artifact(artifact, "physics_report_manifest.schema.json")
    return report, artifact
