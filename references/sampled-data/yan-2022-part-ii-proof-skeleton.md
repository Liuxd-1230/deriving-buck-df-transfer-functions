# Yan 2022 Part II proof skeleton

Part II 在 Part I 的 Dirichlet/`Fm` 之后必须增加两组窄脉冲：

```text
d = d1+d2
d2(t) = -d1(t-T0)
D2/D1 = -exp(-s*T0)
pulse_factor = 1-exp(-s*T0)
```

随后使用注册 `formula_id` 构造：

```text
GPWM = Fm*pulse_factor/(1+Fm*H*SidebandPulse)
```

`SidebandPulse` 表示对每个非零 sideband 同时施加移频后的 pulse factor。C-COT/C-COFT 只能走 `Gid/Hi/Ti`；V-COT/V-COFT 只能走 `Gvd/Hv/Tv`；`Tc` 从对应 return ratio 闭合。

失效条件：缺 `d1/d2`、把 `T0` 错当 `Ts`、sideband 含零项、或使用 v0.5 dynamic `Fm(s)` 场景。
