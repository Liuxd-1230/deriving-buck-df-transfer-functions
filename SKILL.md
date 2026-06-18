---
name: deriving-buck-df-transfer-functions
description: Use when deriving or checking small-signal transfer functions for CCM buck converters with describing-function methods, especially COT, RBCOT, current-mode control, ramp compensation, control-to-output response, loop gain, output impedance, or three-terminal switch models.
---

# Deriving Buck DF Transfer Functions

## Core rule

v0.3 将论文公式库扩展为可检查的 DF 推理协议。不要凭“结构相似”推导新 Buck DF。任何不完全匹配注册论文模型的电路，必须先建立开关事件 `F(x,u,t)=0`，再执行 [DF reasoning protocol](references/df-reasoning-protocol.md)。缺少事件方程或扰动路径时停止，只询问缺失信息；不得输出最终传函。新推导一律标记 `UNVERIFIED_NEW_DF_MODEL`，直到论文 benchmark 或开关仿真验证。

## Required workflow

1. 按 [circuit intake protocol](references/circuit-intake-protocol.md) 获取五项简版输入，并先运行分类器；分类规则见 [model classification](references/model-classification.md)。
2. `KNOWN_MODEL`：读取 [coefficient library](references/df-coefficient-library.md) 及对应 [paper proof skeleton](references/paper-proof-skeletons/common-edge-sensitivity.md)，从物理参数生成 v0.2 case。
3. `NEAR_MODEL` 或 `NEW_MODEL`：读取 [DF reasoning protocol](references/df-reasoning-protocol.md)、对应论文 skeleton 和 [protocol schema](references/protocol-case-schema.md)，重写事件与边沿敏感度。不能直接复制相近论文的 `a_*`。
4. `INCOMPLETE`：只返回缺失项。`UNSUPPORTED`：按 [unsupported cases](references/unsupported-cases.md) 拒绝。
5. 将事件推导整理为 `d_hat = a_c(s) u_c_hat + a_g(s) v_g_hat + a_o(s) v_o_hat + a_i(s) i_L_hat` 或有来源的 direct-transfer，再与 Buck 功率级联立。
6. 用 protocol checker 检查证据链，并按 [validation status](references/validation-status.md) 声明已完成和未完成验证。协议通过不等于公式正确。

## Script interface

```bash
python scripts/df_buck_sympy.py list-models
python scripts/df_buck_sympy.py classify --intake circuit.json
python scripts/df_buck_sympy.py make-case --model MODEL --params params.json --out case.json
python scripts/df_buck_sympy.py make-protocol-case --intake circuit.json --out protocol_case.json
python scripts/df_buck_sympy.py derive --case case.json --out derivation.md
python scripts/df_buck_sympy.py check --case case.json
python scripts/df_protocol_checker.py check-json --case protocol_case.json
python scripts/df_protocol_checker.py check --report derivation.md
python scripts/df_buck_sympy.py benchmark --all
```

注册模型：`cot-cm-li-lee-2010`、`cot-cm-external-ramp-tian-2015`、`rbcot-esr-lu-2023`、`v2-cot-li-lee-2009`。

旧模型输入见 [formula patterns](references/formula-patterns.md)，v0.3 输入见 [protocol schema](references/protocol-case-schema.md)，来源索引见 [Zotero source map](references/zotero-df-source-map.md)。运行 skill 不依赖 Zotero 或论文 PDF；重排公式、proof skeleton 与离线 benchmark 都在仓库内。

## Output contract for protocol-derived models

每次推导依次给出：

依次输出分类、假设/失效边界、状态与开关方程、稳态轨迹、`F=0`、`delta_t=-delta_F/Fdot_0`、DF 关系、`a_*`/direct-transfer、功率级联立、候选传函、sanity checks、验证等级和逐项 provenance。章节名见 reasoning protocol。

## Guardrails

- 平均模型可作低频 sanity check，但绝不能包装成 DF；`rbcot-internal-ramp-huang-2025` 明确拒绝进入 DF 注册表。
- 不把低频吻合等同于接近开关频率时仍然准确。
- 不用单一 Bode 点验证完整模型；至少比较低频、交越附近及模型声明的最高有效频率。
- 不把论文中的无限阶结果未经说明地替换为低阶多项式。
- 多相 overlap、DCM、pulse skipping、burst 或非线性限流不得套用 v0.3。
- 用户直接给 `a_*` 时必须同时给 `df_source`、`event_equation`、`valid_frequency`，并标记 `CUSTOM_COEFFICIENT_UNVERIFIED`。
