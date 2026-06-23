# v0.4.5 Typed Linear Equation Transfer Contract

v0.4.5 的未验证 / protocol-derived 路径不接受 agent 手写候选传函。核心 invariant：

```text
candidate transfer expression must be generated only by linear_system_transfer.py.
```

报告可以显示表达式，但不得构造、改写、化简或补全表达式。若分母来自 agent 手写候选传函，必须拒绝为 `FAIL_HAND_WRITTEN_DENOMINATOR_IN_UNVERIFIED_PATH`。

## Equation Roles

`linear_equation_system.json` 必须区分：

- `active_equations`：唯一进入矩阵消元的方程。
- `diagnostic_equations`：只用于报告、sanity check 或 provenance notes，不影响 transfer expression。

已由 `closed_equivalent_block.eliminated_variables` 声明消元的变量，只能出现在 `diagnostic_equations`、`diagnostic_outputs` 或 provenance notes。若出现在 `active_equations`、`unknowns`、`target.output/input` 或 feedback closure 中，必须返回：

```text
FAIL_REINTRODUCED_ELIMINATED_INTERNAL_VARIABLE
```

## Active Equation Binding

每条 active equation 必须携带：

```json
{
  "id": "eq_modulator",
  "block_id": "K_mod",
  "role": "active",
  "lhs": "d_hat",
  "rhs": "Ke*(vc_hat-vsense_hat)"
}
```

缺少 `block_id` 必须返回 `FAIL_ACTIVE_EQUATION_WITHOUT_BLOCK_ID`。checker 必须可沿：

```text
equation -> block_type -> eliminated_variables -> feedback_paths
```

追踪变量所有权。

## Target And Variable Roles

target 必须是结构化对象：

```json
{
  "name": "Gvc",
  "output": "vo_hat",
  "input": "vc_hat",
  "response_kind": "transfer_function"
}
```

禁止 `vo/vc` 这种自由字符串 target。必须检查：

- `unknowns ∩ inputs = empty`
- `target.output ∈ unknowns`
- `target.input ∈ inputs`

失败码为 `FAIL_VARIABLE_ROLE_CONFLICT` 或 `FAIL_TARGET_VARIABLE_NOT_DECLARED`。

## Block Types

- `primitive_equation`：只提供 active equation，不声明已闭合反馈。
- `open_block`：必须表示 error-to-output 或 explicit input-expression，不得声明 `feedback_paths_already_closed`。
- `closed_equivalent_block`：v0.4.5 只支持 SISO `y_hat = K(s)*x_hat`，并必须声明 `eliminated_variables`、`eliminated_equations`、`feedback_paths_already_closed`。MIMO 返回 `FAIL_MIMO_CLOSED_EQUIVALENT_NOT_SUPPORTED_V045`。
- `return_ratio_block`：必须有 loop break injection/return 定义，否则返回 `FAIL_RETURN_RATIO_LOOP_BREAK_REQUIRED`。

## Linearity

linearity 只对 `unknowns` 检查。`Gvd(s)`、`K(s)`、`H(s)` 可以是关于 `s` 的有理函数；`d_hat*vsense_hat` 这类 unknown 相乘必须返回：

```text
FAIL_NONLINEAR_IN_UNKNOWNS
```

## Denominator Provenance

若生成的 transfer expression 含非平凡分母，`derivation.json` 必须含：

```json
{
  "denominator_provenance": [
    {
      "factor_or_term": "1 + Ke*Hs",
      "source_equations": ["eq_modulator", "eq_sense_path"],
      "feedback_path": "sense_path",
      "generated_by_solver": true
    }
  ]
}
```

该 provenance 是二次 checkout 的关键入口：分母可以复杂，但必须来自 active equation system 自动消元。

## Report Rendering

`derivation_steps[]` 每步必须含 `step_id`、`title`、`latex`、`explanation`、`source_artifact`、`latex_origin`、`provenance`。核心传函公式的 `latex_origin` 只能是 `solver_generated` 或 `registry_binding`。

`render_derivation_report.py` 只能把已有 `derivation_steps[].latex` 包成 Typora 块公式：

```markdown
$$
...
$$
```

报告正文禁止未追踪的裸核心公式，例如 `Gvc(s)=...`、`Tloop(s)=...`、`d_hat=...`、`vo_hat=...`。违规返回 `FAIL_REPORT_CONTAINS_UNTRACKED_FORMULA` 或 `FAIL_FORMULA_NOT_BLOCK_MATH`。
