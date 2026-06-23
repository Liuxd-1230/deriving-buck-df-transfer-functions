---
name: deriving-buck-df-transfer-functions
description: Use when deriving or checking CCM Buck small-signal transfer functions with describing-function or sampled-data methods, especially COT, RBCOT, Yan Part I/II, Dirichlet sampling, sidebands, loop gain, or output impedance.
---

# Deriving Buck DF Transfer Functions

## Core rule

v0.4.4 是 ESSF 的 Yan 2022 sampled-data registered path 闭环，并增加 sensing/validation policy、registered model applicability contract、RC-derived comparator ramp memory checker 与中文 artifact-driven report contract。This skill does not trust free-form LLM derivations.

v0.3.1 direct-transfer、a-star、补偿器、Tloop 与 legacy CLI 仍保持兼容；它们不能绕过 v0.4.4 的 sampled-data、sensing、applicability、checker 和 report artifact 链。

每次传函推导必须先产生 `intake_status.json`。缺少目标传函、工作模式、采样/开关事件、比较器输入或核心参数时，必须停在 `INCOMPLETE → ASK_USER_ONLY`；`workflow.intent == user-circuit-derivation` 缺少 `sensing_layer` 时也必须停在 `ASK_USER_ONLY`。不得补“典型参数”、推导、消元或画图。没有 `classification.json` 和通过 checker 的 `proof_object.json`，不得生成报告。

注册公式的唯一真源是 `registries/formula_registry.yaml`。Markdown 只是说明层。`DF_REGISTERED_DIRECT` 只能输出 registry 允许的 direct transfer，严禁伪造 `a_c/a_g/a_o/a_i`。`DF_REGISTERED_MULTIPORT` 的每个 `a_*` 必须绑定 formula ID。`SAMPLED_DATA_REGISTERED` 只能使用 registry 绑定的 Yan 2022 proof fragment，并必须带 `sampling/Fm/sideband/pulse_structure/modulator_io/target_mapping`。新推导仍必须建立 `F(x,u,t)=0`，并标记 `UNVERIFIED_NEW_DF_MODEL` / `PROTOCOL_DERIVED_UNVERIFIED`。

## State machine

```text
START → INTENT_CLASSIFY → PREFLIGHT_INTAKE
  ├─ INCOMPLETE → ASK_USER_ONLY
  └─ COMPLETE → MODEL_CLASSIFY
       ├─ DF_REGISTERED_DIRECT → registry direct contract
       ├─ DF_REGISTERED_MULTIPORT → registry a-star contract
       ├─ SAMPLED_DATA_REGISTERED → Yan 2022 sampled-data proof fragment
       ├─ PROTOCOL_DERIVED_NEW → event proof + UNVERIFIED
       └─ UNSUPPORTED → reject
     → FORMULA_BINDING (`proof_object.json`)
     → DERIVATION (`derivation.json`)
     → CHECKERS (`checker_result.json`)
     → REPORT (`report_manifest.json` + Markdown)
```

## Required workflow

1. 按 [circuit intake protocol](references/circuit-intake-protocol.md) 回答五问，运行 `scripts/preflight_intake.py`。
2. 只对 `COMPLETE` artifact 运行 [model classification](references/model-classification.md)。
3. 注册模型从 `model_registry + formula_registry + paper_contract_registry` 绑定；新模型按 [DF reasoning protocol](references/df-reasoning-protocol.md) 构建事件证据，不得复制相近论文的 `a_*`。
4. 用 `build_proof_object.py` 生成 `FORMULA_BINDING` proof，并运行 proof/formula checker。
5. sampled-data registered proof 必须用 `derive_transfer.py` 生成独立 `DERIVATION`；推理顺序见 [sampled-data protocol](references/sampled-data/sampled-data-protocol.md)。
6. 用 `check_derivation.py` 复算公式、顺序和前驱 hash，生成 `CHECKERS` artifact。
7. 只有统一 `checker_result.json` 无 blocking `FAIL` 时，才能用 `render_derivation_report.py` 进入可继续的 `REPORT`。Markdown 不能替代 proof 或 derivation。

## Script interface

```bash
python scripts/df_buck_sympy.py list-models
python scripts/preflight_intake.py --intake circuit.json --out intake_status.json
python scripts/df_buck_sympy.py classify --intake-status intake_status.json --out classification.json
python scripts/build_proof_object.py --intake-status intake_status.json --classification classification.json --out proof_object.json
python scripts/check_proof_object.py --proof proof_object.json
python scripts/check_formula_consistency.py --proof proof_object.json
python scripts/derive_transfer.py --proof proof_object.json --out derivation.json
python scripts/check_derivation.py --proof proof_object.json --derivation derivation.json --out checker_result.json
python scripts/render_derivation_report.py --intake-status intake_status.json --classification classification.json --proof-object proof_object.json --derivation derivation.json --checker-result checker_result.json --out report.md --manifest report_manifest.json
python scripts/df_buck_sympy.py make-case --model MODEL --params params.json --out case.json
python scripts/df_buck_sympy.py make-protocol-case --intake circuit.json --out protocol_case.json
python scripts/df_buck_sympy.py derive --proof-object proof_object.json --out legacy-proof-rendering.md
python scripts/df_buck_sympy.py derive --case legacy_case.json --out legacy-unverified.md
python scripts/df_buck_sympy.py check --case case.json
python scripts/df_buck_sympy.py plot-bode --case case.json --targets Gvc,Gvg,Zout,Tloop --out plots/
python scripts/df_buck_sympy.py benchmark --all
```

DF 生成器注册模型：`cot-cm-li-lee-2010`、`cot-cm-external-ramp-tian-2015`、`rbcot-esr-lu-2023`、`v2-cot-li-lee-2009`。

v0.4.4 sampled-data 注册路径：`yan-2022-part-i-pcm-buck`、`yan-2022-part-ii-ccot-buck-zero-ramp`、`yan-2022-part-ii-vcot-buck-zero-ramp`。这些不是 `make-case` 的 a-star DF 生成器；它们只通过 intake/classify/proof/checker 进入报告。

`check --case` 输出 JSON 代数/极限诊断。`df_buck_sympy.py derive` 是兼容渲染入口；v0.4.4 sampled-data 的权威路径必须经过 `derive_transfer.py → check_derivation.py → render_derivation_report.py`。

旧模型输入见 [formula patterns](references/formula-patterns.md)，补偿器模板见 [compensator templates](references/compensator-templates.md)，v0.3 协议说明见 [protocol schema](references/protocol-case-schema.md)，来源索引见 [Zotero source map](references/zotero-df-source-map.md)。0.4 系列开发阶段阅读了 Yan 2022 Part I/II PDF；运行 skill 不依赖 Zotero 或论文 PDF，且 skill 不打包 PDF。

旧 DF 论文公式的人类可读索引保留在 `references/df-coefficient-library.md`；它不是 machine-readable registry 的替代品。

v0.4.4 uses a dual-index model selection rule plus a registered-model applicability contract. First classify the control ontology; then bind the paper/source index; then check sensing layer, comparator inputs, sampled variable, timing, target semantics, nonidealities, and loop-break semantics before allowing a registered path. Read `references/model-ontology.md`, `references/model-applicability-contract.md`, and `references/sensing-layer-policy.md` when a request may confuse current-mode, voltage-mode, V2 COT, RBCOT, sampled-data, external ramp, internal ramp, delay, filter, or multiphase mechanisms. Read `references/df-vs-sampled-method-selection.md` when both DF and sampled-data language could apply.

RC-derived comparator ramps are state variables with inter-cycle memory. Local crossing slope alone is insufficient to define Kmod. If no registered RC-memory model exists, such cases must be rejected, downgraded, or labeled PROTOCOL_DERIVED_UNVERIFIED with explicit memory-state proof and approximation metadata. Read `references/rc-derived-comparator-ramp.md` before handling switch-node RC, sense-filter, or custom comparator-ramp cases.

For formula audits, read `references/formula-audit-plan.md` and `references/paper-bode-validation-spec.md`. Practice is the final arbiter: registry consistency and symbolic algebra are not enough for a verified claim. Use evidence levels `SUBFORMULA_VERIFIED`, `CHAIN_VERIFIED`, `FIGURE_REPRODUCED`, and `SIMULATION_OR_MEASUREMENT_REPRODUCED` honestly.

For Li/Lee 2010 current-mode COT `Gvc`, read `references/li-lee-2010-current-mode-gvc.md` before generating or comparing Bode plots. The existing Li/Lee 2010 benchmark checks Eq. (9)-(10) subformulas; it does not yet claim full Eq. (16) `Gvc` figure reproduction.

请求 `Tloop` 时必须有 `loop_break`：injection point、OUT/IN 定义、符号约定、forward/feedback path 和 `H`。只有明确声明默认负反馈时，才可用 `Tloop = Gc*H*Gvc`；这不等价于任意 SIMPLIS probe。`plot-bode` 必须标出 `fs`、`fs/2`、有效频率边界，并把超界交越标记为 `EXTRAPOLATED_BEYOND_VALID_RANGE`。

sampled-data 的 `GPWM/Gm/Ti/Tv/Tc` 不能混称为 `Gvc/Tloop`。`target_mapping.mapping_status` 只能是 `REGISTERED_DIRECT`、`REGISTERED_DERIVED`、`PROTOCOL_DERIVED_UNVERIFIED` 或 `UNSUPPORTED`。`SYMBOLIC_FULL_SUM` 不可数值画图；Bode 必须使用 `TRUNCATED_SUM_M` 或 `PAPER_SIMPLIFIED_FORM`，并记录近似。

PM/GM 只对 `response_kind=return_ratio` 的 `Ti/Tv/Tloop` 计算。`Gm/GPWM/Gvc/Gvg/Zout/Tc` 必须返回 `NOT_APPLICABLE_NON_RETURN_RATIO`，不得用 0 dB 交越伪装稳定裕度。

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
- v0.4.4 不实现 2026 external-ramp dynamic `Fm(s)`、internal ramp、comparator delay、RC injection、sense filter、multiphase nonoverlap/overlap、DCM、pulse skipping/burst 或 nonlinear current limit as registered models。RC-derived comparator ramps may only proceed as rejected, downgraded, or `PROTOCOL_DERIVED_UNVERIFIED` protocol evidence with explicit memory metadata.
