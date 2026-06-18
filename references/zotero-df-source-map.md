# Zotero DF 文献作用图

来源：本地 Zotero collection `DF`，collection key `C7ZUER5N`。Zotero item key 与 PDF attachment key 分开列出。使用时优先改写推导逻辑并给 DOI/题名，不复制长段原文。

> Zotero 只用于 v0.2 编写时核对。运行 skill 不需要 Zotero；完整重排公式见 [df-coefficient-library.md](df-coefficient-library.md)，离线证据见 `benchmarks/`。

## v0.2 implementation status

| Source | Model ID | Status |
|---|---|---|
| Li & Lee 2010 | `cot-cm-li-lee-2010` | bundled DF + benchmark |
| Tian et al. 2015/2016 | `cot-cm-external-ramp-tian-2015` | bundled DF + benchmark |
| Li & Lee 2009 | `v2-cot-li-lee-2009` | direct paper Gvc + benchmark |
| Lu et al. 2023 | `rbcot-esr-lu-2023` | bundled DF + benchmark |
| Huang et al. 2025 | none | `EXCLUDED_NON_DF` |

## 核心来源

| 用途 | 文献 | Item / PDF key | 备注 |
|---|---|---|---|
| COT current-mode DF 基础 | Jian Li, Fred C. Lee, “New Modeling Approach and Equivalent Circuit Representation for Current-Mode Control,” 2010, DOI `10.1109/TPEL.2010.2040123` | `CLXWL327` / `Q4TJ88D9` | 将电感、开关和调制器作为整体；适合建立通用 DF/等效电路框架。 |
| 外部 ramp 与三端开关 | Shuilin Tian et al., “Three-Terminal Switch Model of Constant On-time Current Mode with External Ramp Compensation,” DOI `10.1109/TPEL.2015.2508037` | `CNWLJK2K` / `6HV5JBKF` | 外部 ramp 引入与开关周期相关的动态；含 control-to-output 与低阶化简思路。 |
| V²/RBCOT 纹波路径 | Jian Li, Fred C. Lee, “Modeling of V² Current-Mode Control,” DOI `10.1109/APEC.2009.4802672` | `2Y5R2WNN` / `VCLF76I9` | 输出电容纹波参与调制，适合检查 ESR/电容纹波和次谐波条件。 |
| RBCOT loop gain | Danzhu Lu, Xiaoyang Zeng, Zhiliang Hong, “Accurate Loop Gain Model of Ripple-Based Constant on-time Controlled Buck Converters,” 2023, DOI `10.1109/TPEL.2023.3254906` | `T4BB6QL6` / `WMWYFLC9` | 用于 loop gain、交越和 phase margin 的文献基准。 |
| Internal ramp / DC extractor | I-Lun Huang et al., “Modeling of Ripple-Based Constant On-Time Control with Internal Ramp Compensation for Buck Converters,” 2025, DOI `10.1109/IAS62731.2025.11061731` | `MTGXK8Z8` / `UDUBA2PS` | 内部 RC ramp/DC extractor 不应被当作常数。 |
| CMCOT/IQCOT/RBCOT 对比 | Wen-Chin Liu et al., “A Novel Ultrafast Transient Constant on-Time Buck Converter for Multiphase Operation,” 2021, DOI `10.1109/TPEL.2021.3076430` | `J74T563G` / `X55RNER8` | 可用于比较 control-to-output 与 output impedance；多相部分仅作扩展。 |

## 多相扩展与边界

| 文献 | Item / PDF key | 用法 |
|---|---|---|
| Sridhar & Li, “Multiphase Constant On-Time Control With Phase Overlapping—Part I: Small-Signal Model,” 2024, DOI `10.1109/TPEL.2024.3368343` | `PBFM62B4` / `RK4IGGF8` | 说明单相模型在脉冲重叠区失效；需要全 duty-range 多相 DF。 |
| Sridhar & Li, “Part II: Stability Analysis,” 2024, DOI `10.1109/TPEL.2023.3345275` | `CUJ67QQI` / `9GJRJ92L` | 检查 `D>1/N`、critical ramp 与多相总电流环稳定性。 |

## 背景与辅助来源

| 文献 | Item / PDF key | 用法 |
|---|---|---|
| Jian Li, “Current-Mode Control: Modeling and its Digital Application” | `UFCNFFD5` / `FPCBX929` | 系统性背景、DF 与 sample-data/average model 的关系。 |
| Robert Sheehan, “Understanding and Applying Current-Mode Control Theory” | `VH38PG3X` / `6KDA4P3L` | 电流环、slope compensation、sampling gain 的工程直觉与低频检查。 |
| Cheng, Chen, Wang, “Small-Signal Model of Flyback Converter…VFPCM,” DOI `10.1109/TPEL.2017.2716830` | `XHQRT8NL` / `IGZ448J2` | 只作 variable-frequency DF 方法类比；不得把 Flyback 功率级公式移植到 Buck。 |

## 选源规则

1. 单相 COT current-mode + external ramp：优先 Li/Lee 2010 与 Tian。
2. RBCOT/V²：加入 Li/Lee 2009、Lu 2023；内部 ramp 时再加入 Huang 2025。
3. 多相或 `D>1/N`：必须读取 Sridhar & Li Part I/II，不得只引用单相模型。
4. 工程低频 sanity check：可用 Sheehan；高频准确性仍以 DF 文献和仿真为准。
