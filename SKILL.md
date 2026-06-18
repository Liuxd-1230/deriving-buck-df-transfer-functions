---
name: deriving-buck-df-transfer-functions
description: Use when deriving or checking small-signal transfer functions for CCM buck converters with describing-function methods, especially COT, RBCOT, current-mode control, ramp compensation, control-to-output response, loop gain, output impedance, or three-terminal switch models.
---

# Deriving Buck DF Transfer Functions

## Overview

v0.2：使用论文固化的描述函数（DF）推导单相 CCM Buck 的小信号模型。覆盖 COT current-mode、外部 ramp、V2/RBCOT；把开关事件 DF 与功率级消元分开，禁止用平均模型冒充 DF。

## Required workflow

1. 读取 [references/df-buck-workflow.md](references/df-buck-workflow.md) 和 [references/formula-patterns.md](references/formula-patterns.md)。使用论文模型时必须再读取 [references/df-coefficient-library.md](references/df-coefficient-library.md)；来源索引见 [references/zotero-df-source-map.md](references/zotero-df-source-map.md)。
2. 明确拓扑、CCM 假设、控制律、开关事件、扰动变量、正方向及目标传函。若是 DCM、谐振拓扑或多相重叠导通，不得直接套用单相公式。
3. 优先选择注册模型并从物理参数生成 case。只有控制律不属于注册模型时，才允许使用自定义 `a_*`，并标记 `custom-unverified-df`。
4. 将调制器线性化为
   `d_hat = a_c(s) u_c_hat + a_g(s) v_g_hat + a_o(s) v_o_hat + a_i(s) i_L_hat`。
5. 用 `scripts/df_buck_sympy.py` 生成或消元得到 `Gvc`、`Gvg`、`Zout`。Li/Lee 2009 是论文直接 `Gvc` 接口，不伪造多端口 `a_*`。
6. 完成四类验证：符号/量纲、DC 与极限情况、文献基准、开关仿真或实验扫频。任何一类未完成都要显式标记。

## Script interface

```bash
python scripts/df_buck_sympy.py list-models
python scripts/df_buck_sympy.py make-case --model MODEL --params params.json --out case.json
python scripts/df_buck_sympy.py derive --case case.json --out derivation.md
python scripts/df_buck_sympy.py check --case case.json
python scripts/df_buck_sympy.py benchmark --all
```

注册模型：`cot-cm-li-lee-2010`、`cot-cm-external-ramp-tian-2015`、`rbcot-esr-lu-2023`、`v2-cot-li-lee-2009`。

输入格式见 [references/formula-patterns.md](references/formula-patterns.md)，证据见 `benchmarks/` 和 [VALIDATION.md](VALIDATION.md)。若 SymPy 不可用，脚本必须报出可操作的依赖错误。

## Output contract

每次推导依次给出：

1. 适用范围与假设
2. 符号、端口与正方向
3. 稳态关系及开关边沿条件
4. 描述函数系数 `a_c,a_g,a_o,a_i`
5. 未化简与化简后的传递函数
6. 极点、零点及物理解释
7. 验证结果、误差范围与未验证项
8. 来源映射及模型失效边界

## Guardrails

- 普通低频 voltage-mode Buck 若平均模型已足够，不强行使用 DF。
- `rbcot-internal-ramp-huang-2025` 是平均模型，v0.2 明确拒绝。
- 不把低频吻合等同于接近开关频率时仍然准确。
- 不用单一 Bode 点验证完整模型；至少比较低频、交越附近及模型声明的最高有效频率。
- 不把论文中的无限阶结果未经说明地替换为低阶多项式。
- 多相 overlap、DCM、pulse skipping、burst 或非线性限流不得套用 v0.2。
