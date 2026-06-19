# Approximation policy

工程近似可以使用，但必须同时记录：`formula_id`、近似名称、被舍弃的物理项、有效频率和验证等级。

允许的 v0.4 形式包括 symbolic full sideband、显式 `M` 的非零项截断、论文 simplified form，以及标记为 `ideal-ESR-power-stage` 的 Buck coupling。不得把近似式重命名为 exact。

PM/GM 只适用于 `response_kind=return_ratio` 的 `Ti/Tv/Tloop`。`Gm/GPWM/Gvc/Gvg/Zout/Tc` 的裕度状态必须是 `NOT_APPLICABLE_NON_RETURN_RATIO`。

超出 `fs/2` 或 registry 声明范围、缺少误差说明、或者把 benchmark 方向性检查当成论文曲线复现时，验证声明失效。
