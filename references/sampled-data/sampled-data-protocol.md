# Sampled-data ESSF protocol

注册路径只能按以下证据链推进：

```text
sampling event → left/right limits → Dirichlet value → Fm
→ pulse structure → sideband-aware GPWM/Gm
→ Gid/Gvd → Ti/Tv → Tc
```

每一步必须携带 `formula_id`、source equation、dimension signature、approximation 和有效频率。proof 绑定对象，`derivation.json` 执行代数组合，Markdown 只渲染结果。

电流控制只允许 `Gid → Ti`，电压控制只允许 `Gvd → Tv`；`Tc=T/(1+T)`，不能用调制器表达式冒充。任一 registry binding 缺失或表达式被改写即失效并返回 formula-consistency failure。

失效边界：dynamic ramp、delay、RC injection、sense filter、多相、DCM、pulse skipping 均不进入 v0.4 registered path。
