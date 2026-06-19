---
name: deriving-buck-df-transfer-functions
description: Use when deriving or checking small-signal transfer functions for CCM buck converters with describing-function methods, especially COT, RBCOT, current-mode control, ramp compensation, control-to-output response, loop gain, output impedance, or three-terminal switch models.
---

# Deriving Buck DF Transfer Functions

## Core rule

v0.4 是 ESSF 的 Yan 2022 sampled-data registered path 最小闭环。This skill does not trust free-form LLM derivations.

每次传函推导必须先产生 `intake_status.json`。缺少目标传函、工作模式、采样/开关事件、比较器输入或核心参数时，必须停在 `INCOMPLETE → ASK_USER_ONLY`；不得补“典型参数”、推导、消元或画图。没有 `classification.json` 和通过 checker 的 `proof_object.json`，不得生成最终报告。

注册公式的唯一真源是 `registries/formula_registry.yaml`。Markdown 只是说明层。`DF_REGISTERED_DIRECT` 只能输出 registry 允许的 direct transfer，严禁伪造 `a_c/a_g/a_o/a_i`。`DF_REGISTERED_MULTIPORT` 的每个 `a_*` 必须绑定 formula ID。`SAMPLED_DATA_REGISTERED` 只能使用 registry 绑定的 Yan 2022 proof fragment，并必须带 `sampling/Fm/sideband/pulse_structure/modulator_io/target_mapping`。新推导仍必须建立 `F(x,u,t)=0`，并标记 `UNVERIFIED_NEW_DF_MODEL` / `PROTOCOL_DERIVED_UNVERIFIED`。

## State machine

```text
START → PREFLIGHT_INTAKE
  ├─ INCOMPLETE → ASK_USER_ONLY
  └─ COMPLETE → MODEL_CLASSIFY
       ├─ DF_REGISTERED_DIRECT → registry direct contract
       ├─ DF_REGISTERED_MULTIPORT → registry a-star contract
       ├─ SAMPLED_DATA_REGISTERED → Yan 2022 sampled-data proof fragment
       ├─ PROTOCOL_DERIVED_NEW → event proof + UNVERIFIED
       └─ UNSUPPORTED → reject
     → BUILD proof_object.json
     → formula/proof checkers
     → report
```

## Required workflow

1. 按 [circuit intake protocol](references/circuit-intake-protocol.md) 回答五问，运行 `scripts/preflight_intake.py`。
2. 只对 `COMPLETE` artifact 运行 [model classification](references/model-classification.md)。
3. 注册模型从 formula registry 生成，[coefficient library](references/df-coefficient-library.md) 只用于人工阅读；新模型按 [DF reasoning protocol](references/df-reasoning-protocol.md) 构建事件证据，不得复制相近论文的 `a_*`。
4. 用 `build_proof_object.py` 组装 proof，再运行 `check_proof_object.py` 和 `check_formula_consistency.py`。
5. 只有 proof 检查通过后才能渲染报告。协议通过不等于物理正确。

## Script interface

```bash
python scripts/df_buck_sympy.py list-models
python scripts/preflight_intake.py --intake circuit.json --out intake_status.json
python scripts/df_buck_sympy.py classify --intake-status intake_status.json --out classification.json
python scripts/build_proof_object.py --intake-status intake_status.json --classification classification.json --out proof_object.json
python scripts/check_proof_object.py --proof proof_object.json
python scripts/check_formula_consistency.py --proof proof_object.json
python scripts/df_buck_sympy.py make-case --model MODEL --params params.json --out case.json
python scripts/df_buck_sympy.py make-protocol-case --intake circuit.json --out protocol_case.json
python scripts/df_buck_sympy.py derive --proof-object proof_object.json --out derivation.md
python scripts/df_buck_sympy.py derive --case legacy_case.json --out legacy-unverified.md
python scripts/df_buck_sympy.py check --case case.json
python scripts/df_buck_sympy.py plot-bode --case case.json --targets Gvc,Gvg,Zout,Tloop --out plots/
python scripts/df_buck_sympy.py benchmark --all
```

DF 生成器注册模型：`cot-cm-li-lee-2010`、`cot-cm-external-ramp-tian-2015`、`rbcot-esr-lu-2023`、`v2-cot-li-lee-2009`。

v0.4 sampled-data 注册路径：`yan-2022-part-i-pcm-buck`、`yan-2022-part-ii-ccot-buck-zero-ramp`、`yan-2022-part-ii-vcot-buck-zero-ramp`。这些不是 `make-case` 的 a-star DF 生成器；它们只通过 intake/classify/proof/checker 进入报告。

`check --case` 输出 JSON 代数/极限诊断；`derive --case` 只为 legacy case 渲染 `LEGACY_CASE_UNVERIFIED` Markdown，不等于 v0.3.1 proof。`derive --proof-object` 才是 ESSF 报告路径。

旧模型输入见 [formula patterns](references/formula-patterns.md)，补偿器模板见 [compensator templates](references/compensator-templates.md)，v0.3 协议说明见 [protocol schema](references/protocol-case-schema.md)，来源索引见 [Zotero source map](references/zotero-df-source-map.md)。开发 v0.4 时阅读了 Yan 2022 Part I/II PDF；运行 skill 不依赖 Zotero 或论文 PDF，且 skill 不打包 PDF。

请求 `Tloop` 时必须有 `loop_break`：injection point、OUT/IN 定义、符号约定、forward/feedback path 和 `H`。只有明确声明默认负反馈时，才可用 `Tloop = Gc*H*Gvc`；这不等价于任意 SIMPLIS probe。`plot-bode` 必须标出 `fs`、`fs/2`、有效频率边界，并把超界交越标记为 `EXTRAPOLATED_BEYOND_VALID_RANGE`。

sampled-data 的 `GPWM/Gm/Ti/Tv/Tc` 不能混称为 `Gvc/Tloop`。`target_mapping.mapping_status` 只能是 `REGISTERED_DIRECT`、`REGISTERED_DERIVED`、`PROTOCOL_DERIVED_UNVERIFIED` 或 `UNSUPPORTED`。`SYMBOLIC_FULL_SUM` 不可数值画图；Bode 必须使用 `TRUNCATED_SUM_M` 或 `PAPER_SIMPLIFIED_FORM`，并记录近似。

## Output contract for protocol-derived models

每次推导依次给出：

依次输出分类、假设/失效边界、状态与开关方程、稳态轨迹、`F=0`、`delta_t=-delta_F/Fdot_0`、DF 关系、`a_*`/direct-transfer、功率级联立、候选传函、sanity checks、验证等级和逐项 provenance。章节名见 reasoning protocol。

## Guardrails

- 平均模型可作低频 sanity check，但绝不能包装成 DF；`rbcot-internal-ramp-huang-2025` 明确拒绝进入 DF 注册表。
- 不把低频吻合等同于接近开关频率时仍然准确。
- 不用单一 Bode 点验证完整模型；至少比较低频、交越附近及模型声明的最高有效频率。
- 不把论文中的无限阶结果未经说明地替换为低阶多项式。
- 多相 overlap、DCM、pulse skipping、burst 或非线性限流不得套用 v0.3。
- Yan 2022 Part I/II 的 Dirichlet、sideband 和 COT/COFT 双脉冲只覆盖 zero-ramp sampled-data registered path；不能外推到 external/internal ramp、delay、sense filter、RC injection 或多相。
- `fm_models.py` 是 zero-ramp only。external ramp 返回 `REJECT_DYNAMIC_FM_REQUIRED_V05`；internal ramp、delay、RC injection、sense filter 均硬拒绝，不是 warning。
- 用户直接给 `a_*` 不能伪装成 registered formula；必须标记 `CUSTOM_COEFFICIENT_UNVERIFIED`。
- v0.4 不实现 2026 external-ramp dynamic `Fm(s)`、internal ramp、comparator delay、RC injection、sense filter、multiphase nonoverlap/overlap、DCM、pulse skipping/burst 或 nonlinear current limit。
