# Buck DF coefficient library (v0.2)

本文件只收录单相 CCM Buck 的描述函数模型。公式可在没有 Zotero 和论文 PDF 的电脑上使用；Zotero 仅用于编写时核对来源。

## 共同接口与来源标签

统一 duty 接口为 `d = a_c u_c + a_g v_g + a_o v_o + a_i i_L`。

- `paper-equation`：论文直接给出的关系；
- `derived-adapter`：为接入统一 Buck 端口方程而做的代数变换；
- `paper-low-order`：论文明确给出的有限阶近似；
- `EXCLUDED_NON_DF`：平均模型，不进入本库。

Li/Lee 与 Tian 先给出闭合 current-mode entity：

`i_L = F_c u_c + F_g v_g + F_o v_o`。

结合 Buck 电感端口 `(sL+r_L)i_L + v_o = Dv_g + V_gd` 得到：

```text
a_c = (sL+rL) Fc / Vg
a_g = ((sL+rL) Fg - D) / Vg
a_o = ((sL+rL) Fo + 1) / Vg
a_i = 0
```

这组 `derived-adapter` 不猜测增益。测试会把它代回端口方程，并要求精确恢复 `F_c/F_g/F_o`。

## Li/Lee 2010：COT current-mode

来源：J. Li and F. C. Lee, “New Modeling Approach and Equivalent Circuit Representation for Current-Mode Control,” DOI `10.1109/TPEL.2010.2040123`，PDF 第 4-7 页，Eqs. (1)-(16)。

固定 `T_on`，由控制阈值决定 `T_off(i)`：

```text
v_c(t_{i-1}+T_off(i-1)) + s_n T_on
= v_c(t_i+T_off(i)) + s_f T_off(i)
```

其中 `s_n=R_i(V_g-V_o)/L`，`s_f=R_iV_o/L`。线性化边沿扰动，再对脉冲序列和电感电流取傅里叶基波。

论文 Eq. (9)：

```text
Fc_exact = (fs/sf) (1-exp(-s Ton)) Vg/(L s)
```

论文 Eq. (10)：

```text
w1 = pi/Ton
Q1 = 2/pi
Fc_pade = 1/[Ri(1+s/(Q1 w1)+s^2/w1^2)]
```

低频极限必须满足 `Fc(0)=1/Ri`。v0.2 使用论文 Eqs. (14)-(15) 的低频比值 `k1≈Ton Ri/(2L)`、`k2≈-Ton Ri/(2L)`，令 `Fg=k1 Fc`、`Fo=k2 Fc`，再生成 `a_*`。因此 `Fc` 可为精确指数式，但扰动路径会标作 `paper-low-order`，不得描述为全多输入精确模型。

模型 ID：`cot-cm-li-lee-2010`；支持 `exact` 和 `pade`。

## Tian 2015/2016：COT current-mode + external ramp

来源：S. Tian et al., “Three-Terminal Switch Model of Constant On-time Current Mode with External Ramp Compensation,” DOI `10.1109/TPEL.2015.2508037`，PDF 第 3、5-7 页，Eqs. (1)-(8)、(13)、Table I。

事件条件：

```text
v_c(t_{i-1}+T_off(i-1)) + s_e T_off(i-1) + s_n T_on
= v_c(t_i+T_off(i)) + (s_e+s_f) T_off(i)
```

其中 `s_f=R_iV_o/L`、`s_e>=0`。令 `A(s)=(s_f+s_e)-s_e exp(-sT_sw)`，论文 Eqs. (4)、(6)、(7) 重排为：

```text
Fc = fs(1-exp(-sTon)) Vg / [L s A(s)]

Fg = -1/(L s) * {
       fs(1-exp(-sTon))/[(1-exp(sTsw)) A(s)]
       * [(1-exp(sTon))/(sL/Ri)] Vg + D
     }

Fo = 1/(L s) * {
       fs(1-exp(-sTon))/A(s) * 1/(sL/Ri) * Vg - 1
     }
```

把 `Fc/Fg/Fo` 送入共同 `derived-adapter` 得到 `a_c/a_g/a_o/a_i`。

论文 Eq. (8)：

```text
Fc_low = (1/Ri) (1+sTsw/2) /
         [1+(se/sf+1/2)Tsw s]
```

当 `s_e=0` 时分子分母严格抵消，`Fc_low=1/R_i`。论文 Eq. (13)：

```text
fp = fs/[pi(2se/sf+1)]
fz = fs/pi
```

论文声明低阶近似和等效电路验证范围到 `fs/2`。模型 ID：`cot-cm-external-ramp-tian-2015`。

## Lu 2023：ESR-ripple RBCOT loop gain

来源：Y. Lu et al., “Accurate Loop Gain Model of Ripple-Based Constant on-time Controlled Buck Converters,” DOI `10.1109/TPEL.2023.3254906`，PDF 第 3-6 页，Eqs. (2)-(14)。

定义 `T_sw=1/f_s`、`T_on=D T_sw`、`T_off=T_sw-T_on`、`s_f=r_CV_o/L`，以及

```text
B(s) = Tsw/(rC C)
     + [1+(Toff-2Tsw)/(2rC C)] [1-exp(-sTsw)]
```

论文 Eq. (5)：

```text
Fdx = (fs/sf)(1-exp(-sTon))(1-exp(-sTsw))(1+rC/R)/B(s)
```

论文 Eq. (8)，注意第二项是加号：

```text
Fodx = (fs/sf)(1-exp(-sTon))(1-exp(-sTsw))
       [1/(s^2 L C) + (rC/L+1/(R C))/s] / B(s)
```

论文 Eqs. (9)-(11)：

```text
Fox = -Fodx-Fdx
Fp  = Vg(1+s rC C) /
      [1+s(rC C+L/R)+s^2 L C(1+rC/R)]
Floop = Fdx Fp/(1+Fox Fp)
```

Fig. 7 中 `Fox` 经负号进入 duty 求和点，因此统一接口使用 `a_c=Fdx`、`a_g=0`、`a_o=-Fox`、`a_i=0`。Buck 闭合分母即 `1-(-Fox)Fp=1+Fox Fp`。

论文延时近似：

```text
exp(-sTsw) ~= 1 - sTsw/[1+sTsw/2+s^2 Tsw^2/pi^2]
```

验证范围到 `fs/2`。模型 ID：`rbcot-esr-lu-2023`；支持 `exact` 和 `pade`。

## Li/Lee 2009：V2 COT capacitor-ripple DF

来源：J. Li and F. C. Lee, “Modeling of V2 Current-Mode Control,” 2009；PDF 第 2-6 页，尤其 Eqs. (8)-(10)。

论文直接给出 `v_o/v_c`。v0.2 不反向伪造多端口 duty 系数，而输出 `interface=direct-transfer-function`：

```text
w1 = pi/Ton, Q1 = 2/pi
w2 = pi/Tsw
Q2 = Tsw/[pi(rC C-Ton/2)]

Gvc = (1+s rC C) /
      {[1+s/(Q1w1)+s^2/w1^2]
       [1+s/(Q2w2)+s^2/w2^2]}
```

小 duty 的进一步近似省略第一组高频极点。稳定边界是 `rC C > Ton/2`。

模型 ID：`v2-cot-li-lee-2009`；只支持 `pade` 或 `low-order`，不提供虚假的 `exact` 选项。

## EXCLUDED_NON_DF

Huang 2025 的 internal-ramp/DC-extractor 论文在 PDF 第 2 页明确选择 average model，并在第 3 页用 `Gdfb/Gramp/Hd` 建模。按用户要求：

- `rbcot-internal-ramp-huang-2025` 会报错；
- 不生成 `a_*` 或 benchmark；
- 不以“近似 DF”名义包装平均模型。

## 失效边界

- 只覆盖单相 CCM；DCM、pulse skipping、burst、限流、饱和和量化不支持。
- 多相 overlap 或相位管理参与开关事件时不得套用本库。即使 no-overlap，v0.2 也不宣称支持多相。
- 精确指数式与有限阶近似必须显式选择，不能静默替换。
- `fs/2` 是文献声明或保守 benchmark 边界，不代表所有参数下都与开关仿真同样精确。
- 没有原始 SIMPLIS/测量数据时，只能标为公式级或关键值复现。
