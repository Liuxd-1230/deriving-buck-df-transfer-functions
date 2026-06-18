# CCM Buck 公式骨架与脚本输入

## v0.2 优先入口

不要先手填 `a_c/a_g/a_o/a_i`。先选择论文模型并只提供物理参数：

```powershell
python scripts/df_buck_sympy.py list-models
python scripts/df_buck_sympy.py make-case --model cot-cm-external-ramp-tian-2015 --params params.json --out case.json
```

示例 `params.json`：

```json
{
  "Vin": 12.0,
  "Vo": 1.2,
  "fs": 300000.0,
  "L": 3e-7,
  "C": 0.00448,
  "R": 0.1,
  "rL": 0.0,
  "rC": 0.00075,
  "Ri": 0.01,
  "se_ratio": 1.0
}
```

模型需要的参数和公式见 [df-coefficient-library.md](df-coefficient-library.md)。只有控制律尚未注册时才使用下述自定义接口；此时必须标作 `custom-unverified-df`。

## 统一符号

- `s`：拉普拉斯变量
- `L,C,R`：电感、输出电容、负载
- `rL,rC`：电感串联电阻与电容 ESR
- `Vg,D`：稳态输入电压与 duty ratio
- `iL,vo,d`：电感电流、输出电压和 duty 的小信号量
- `uc,vg,iload`：控制、输入电压和负载电流扰动

## 功率级关系

输出节点看到的并联阻抗为

`Zp(s) = [1/R + sC/(1+sCrC)]^-1`。

令 `AL(s)=sL+rL`。独立 duty 扰动下的开环功率级为

```text
Gvd(s)      = vo/d      = Vg Zp / (AL + Zp)
Gvg_open(s) = vo/vg     = D  Zp / (AL + Zp)
Zout_open   = -vo/iload = AL Zp / (AL + Zp)
```

DC 检查：

```text
Gvd(0)      = Vg R/(R+rL)
Gvg_open(0) = D  R/(R+rL)
Zout_open(0)= rL R/(R+rL)
```

## 描述函数接口

把调制器结果整理成

`d = ac*uc + ag*vg + ao*vo + ai*iL`。

这里的 `d` 是 DF 输出的等效归一化开关函数扰动。只有在低频平均模型条件下，才能不加说明地把它当作普通 duty perturbation。

系数可以是 `s` 的有理式、延时近似或论文给出的 DF 近似。反馈方向包含在系数符号中。例如 current sensing 形成负反馈时，常见形式是负的 `ai`；不要在脚本外再补一次负号。

联立矩阵为

```text
[ AL   1    -Vg ] [iL]   [D*vg]
[ 1   -Yp     0 ] [vo] = [iload]
[-ai  -ao     1 ] [ d]   [ac*uc + ag*vg]
```

其中 `Yp=1/Zp`。求解后定义：

```text
Gvc  = vo/uc
Gvg  = vo/vg
Zout = -vo/iload
```

若外环采用 `uc=Gc(s)[vref-H(s)vo]`，常用负反馈约定下 `Tloop=Gc*H*Gvc`。报告中仍须注明 loop-break 位置和符号约定。

## 外部/内部 ramp 注意事项

- `1/(总边沿斜率)`只能作为事件敏感度的低频直觉，不能自动替代完整 COT DF。
- 外部 ramp 可能产生与开关周期有关的附加动态；保留论文或边沿推导中的延时项。
- 内部 ramp/DC extractor 的 RC 网络应进入 `ac/ag/ao/ai` 中相应路径。
- RBCOT 中 `vo` 纹波参与调制；若先把 ESR ripple 包进 `ao`，不要在另一条反馈路径重复加入。

## 自定义 JSON 输入格式（非论文模型的后备入口）

可直接复制 `references/example-rbcot-case.json` 作为起点。下面展示相同结构：

```json
{
  "name": "single-phase-rbcot-example",
  "topology": "buck-ccm",
  "phases": 1,
  "df_source": "replace with edge-condition derivation or citation",
  "valid_frequency": "replace with a justified frequency range",
  "parameters": {
    "L": "500e-9",
    "C": "470e-6",
    "R": "0.05",
    "rL": "500e-6",
    "rC": "1e-3",
    "Vg": "12",
    "D": "0.1",
    "Fm": "0.02",
    "Ri": "1e-3",
    "Hvo": "1",
    "tau_m": "50e-9",
    "Gc": "1",
    "H": "1"
  },
  "modulator": {
    "a_c": "Fm/(1+s*tau_m)",
    "a_g": "0",
    "a_o": "-Fm*Hvo/(1+s*tau_m)",
    "a_i": "-Fm*Ri/(1+s*tau_m)"
  },
  "feedback": {
    "Gc": "Gc",
    "H": "H"
  },
  "targets": ["Gvc", "Gvg", "Zout", "Tloop"]
}
```

`parameters` 中未给值的名称保留为符号。数值只是演示旧版自定义接口，不代表某篇论文或推荐设计，也不能替代 `make-case`。

## 脚本边界

脚本能够验证矩阵消元、DC 极限、符号依赖和在完全数值化后的极点位置。脚本不能验证：

- 开关事件是否选对
- DF 系数是否漏掉 sideband、采样或传播延时
- 模型是否适用于 DCM、pulse skipping 或多相 overlap
- 低阶近似在目标频段是否足够准确

这些必须按 [df-buck-workflow.md](df-buck-workflow.md) 用文献和开关仿真验证。
