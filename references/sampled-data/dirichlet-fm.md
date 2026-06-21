# Dirichlet sampling and Fm

若扰动在采样时刻存在第一类间断，采样值必须是左右极限平均：

```text
x(k) = (x(k-)+x(k+))/2
```

该对象与 `Fm` 分别绑定 `formula_id`。checker 不只查字段存在，还确认 `Fm.dirichlet_reference` 指向 `sampling.dirichlet_value`，并比较两项 registry 表达式。

v0.4 只注册 zero-ramp constant `Fm`。external ramp 返回 `REJECT_DYNAMIC_FM_REQUIRED_V05`；internal ramp、delay、RC injection、sense filter 分别硬拒绝。把这些场景套入 constant `Fm` 时模型立即失效。
