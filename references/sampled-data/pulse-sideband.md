# Pulse trains and sidebands

Part II 的 pulse relation 与 pulse factor 使用不同 `formula_id`，防止只写 `1-exp(-s*T0)` 却省略 `d2(t)=-d1(t-T0)` 的物理来源。

sideband 模式：

- `SYMBOLIC_FULL_SUM`：保存论文结构，不能直接数值画图；
- `TRUNCATED_SUM_M`：显式正整数 `M`，索引为 `[-M,-1]∪[1,M]`；
- `PAPER_SIMPLIFIED_FORM`：必须记录论文近似及有效范围。

索引替换必须使用符号 `subs(n,Integer(k))`，不得字符串替换。proof 的 sideband expression 必须匹配 `formula_id`；改写为任意数值时 checker 失败。包含零项、遗漏 `M` 或静默把 full sum 变成截断时近似声明失效。
