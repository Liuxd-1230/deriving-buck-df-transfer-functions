# Sampled-data power-stage coupling

v0.4 使用 CCM Buck 线性化状态方程注册低阶功率级耦合：

```text
Gid = Vin*(C*s+1/R)/(L*C*s^2+(L/R)*s+1)
Gvd = Vin/(L*C*s^2+(L/R)*s+1)
Ti = Hi*Gid*GPWM
Tv = Hv*Gvd*GPWM
Tc = Ti/(1+Ti)  or  Tv/(1+Tv)
```

每个式子独立绑定 `formula_id`。这里的 power stage 明确采用 ideal-ESR dynamic denominator 工程近似；ESR 可用于已注册的稳定边界趋势，但没有悄悄加入上述动态式。

current/voltage contract 互换、把 `Tc` 当 return ratio、或请求未注册 `Gvc/Gvg/Zout/Tloop` 时映射失效。
