---
name: deriving-buck-df-transfer-functions
description: Use when deriving or checking small-signal transfer functions for CCM buck converters with describing-function methods, especially COT, RBCOT, current-mode control, ramp compensation, control-to-output response, loop gain, output impedance, or three-terminal switch models.
---

# Deriving Buck DF Transfer Functions

## Core rule

v0.3.1 是 ESSF 第一阶段。This skill does not trust free-form LLM derivations.

每次传函推导必须先产生 `intake_status.json`。缺少目标传函、工作模式、采样/开关事件、比较器输入或核心参数时，必须停在 `INCOMPLETE → ASK_USER_ONLY`；不得补“典型参数”、推导、消元或画图。没有 `classification.json` 和通过 checker 的 `proof_object.json`，不得生成最终报告。

注册公式的唯一真源是 `registries/formula_registry.yaml`。Markdown 只是说明层。`DF_REGISTERED_DIRECT` 只能输出 registry 允许的 direct transfer，严禁伪造 `a_c/a_g/a_o/a_i`。`DF_REGISTERED_MULTIPORT` 的每个 `a_*` 必须绑定 formula ID。新推导仍必须建立 `F(x,u,t)=0`，并标记 `UNVERIFIED_NEW_DF_MODEL` / `PROTOCOL_DERIVED_UNVERIFIED`。

## State machine

```text
START → PREFLIGHT_INTAKE
  ├─ INCOMPLETE → ASK_USER_ONLY
  └─ COMPLETE → MODEL_CLASSIFY
       ├─ DF_REGISTERED_DIRECT → registry direct contract
       ├─ DF_REGISTERED_MULTIPORT → registry a-star contract
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
python scripts/df_buck_sympy.py check --case case.json
python scripts/df_buck_sympy.py benchmark --all
```

注册模型：`cot-cm-li-lee-2010`、`cot-cm-external-ramp-tian-2015`、`rbcot-esr-lu-2023`、`v2-cot-li-lee-2009`。

旧模型输入见 [formula patterns](references/formula-patterns.md)，v0.3 协议说明见 [protocol schema](references/protocol-case-schema.md)，来源索引见 [Zotero source map](references/zotero-df-source-map.md)。运行 skill 不依赖 Zotero 或论文 PDF。

## Output contract for protocol-derived models

每次推导依次给出：

依次输出分类、假设/失效边界、状态与开关方程、稳态轨迹、`F=0`、`delta_t=-delta_F/Fdot_0`、DF 关系、`a_*`/direct-transfer、功率级联立、候选传函、sanity checks、验证等级和逐项 provenance。章节名见 reasoning protocol。

## Guardrails

- 平均模型可作低频 sanity check，但绝不能包装成 DF；`rbcot-internal-ramp-huang-2025` 明确拒绝进入 DF 注册表。
- 不把低频吻合等同于接近开关频率时仍然准确。
- 不用单一 Bode 点验证完整模型；至少比较低频、交越附近及模型声明的最高有效频率。
- 不把论文中的无限阶结果未经说明地替换为低阶多项式。
- 多相 overlap、DCM、pulse skipping、burst 或非线性限流不得套用 v0.3。
- 用户直接给 `a_*` 不能伪装成 registered formula；必须标记 `CUSTOM_COEFFICIENT_UNVERIFIED`。
- v0.3.1 不实现 sampled-data sideband、Dirichlet、COT 双脉冲或动态 `Fm(s)`；这些属于 v0.4/v0.5。
