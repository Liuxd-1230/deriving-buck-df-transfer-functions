# Yan 2022 Part I proof skeleton

1. 写明采样时刻为两调制器输入的交点。
2. 保存反馈扰动的左、右极限。
3. 用 Dirichlet 条件得到采样值；对应 `formula_id` 由 paper contract registry 指定。
4. 从该采样值推得 zero-ramp `Fm`。
5. 定义非零 sideband sum，不包含基带零项。
6. 形成

```text
GPWM = Fm/(1+Fm*H*SumG)
```

7. current contract：`Ti=Hi*Gid*GPWM`；voltage contract：`Tv=Hv*Gvd*GPWM`。
8. 需要闭环响应时才使用 `Tc=T/(1+T)`。

每项的 `formula_id` 必须来自 `paper_contract_registry.yaml`。工程近似要写入 derivation step；失效于外/内斜坡、delay、filter、动态 `Fm(s)` 与未注册目标。
