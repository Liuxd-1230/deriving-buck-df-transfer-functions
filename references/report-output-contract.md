# 中文报告输出契约

JSON artifact 是机器证据源，中文 Markdown 报告是人工二次 checkout 界面。报告只能渲染已有 artifact，不得重新推导、补公式、推断隐藏默认值或升级 validation。

## 必需输出

每次 derivation、benchmark、validation、mismatch、Bode、unsupported、ASK_USER_ONLY 至少生成：

- `report.md`
- `report_manifest.json`

如有数据，还应登记：

- `intake_status.json`
- `classification.json`
- `proof_object.json`
- `derivation.json`
- `formula_origin.json`
- `checker_result.json`
- `bode_summary.json`
- `mismatch_report.json`

## 固定章节

`report.md` 必须按顺序包含 14 个章节：

1. `## 1. 结论摘要`
2. `## 2. 输入信息与目标传函`
3. `## 3. 模型分类结果`
4. `## 4. sensing layer / sampling event / comparator 输入`
5. `## 5. 公式来源与注册信息`
6. `## 6. 逐步推导过程`
7. `## 7. 代数消元或传函生成过程`
8. `## 8. 近似、低阶模型与适用边界`
9. `## 9. 检查器结果`
10. `## 10. Bode / 数值结果`
11. `## 11. 与仿真或参考数据的 mismatch report`
12. `## 12. validation level 与禁止声明`
13. `## 13. 二次 checkout 索引`
14. `## 14. 未确认事项与下一步建议`

不适用章节不得删除，必须写明未提供或不适用原因。

## 禁止声明

当 validation level 为 near-model、unverified、low-order、target semantics unclear 或 reference semantics unclear 时，报告禁止出现：

- `final transfer function`
- `correct transfer function`
- `verified transfer function`
- `paper-grounded`
- `figure reproduced`
- `最终传函`
- `正确传函`
- `已验证传函`
- `论文验证`
- `图像复现`
- `完全正确`

只能使用候选传函、未验证模型、近似模型、低阶近似、需要仿真确认、待审计公式链等表述。

## ASK_USER_ONLY

`ASK_USER_ONLY` 报告不得选择 `model_id`，不得展示候选传函。只能列出缺失字段、允许选择、禁止推导原因，以及为什么不能自动套用默认模型。

## v0.4.4 unified checker visibility

`checker_result.json` 必须作为统一检查入口，至少包含：

- `preflight_intake`
- `model_classification`
- `model_applicability`
- `proof_object_check`
- `formula_consistency`
- `normalization_check`
- `power_stage_dynamics_check`
- `mismatch_report_check`
- `forbidden_claim_check`
- `rc_memory_factor_check`
- `validation_policy_check`

每项必须有 `PASS` / `FAIL` / `WARN` / `NOT_APPLICABLE`、`reason`、`blocking` 和 `artifact`。存在 blocking `FAIL` 时，报告标题必须降级为“未完成推导：信息不足 / 检查失败报告”，不得把候选表达式写成最终结论。
