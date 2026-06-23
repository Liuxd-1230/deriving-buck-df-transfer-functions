# Li/Lee 2010 current-mode COT Gvc audit

Source checked during development:

- Local PDF: `New_Modeling_Approach_and_Equivalent_Circuit_Representation_for_Current-Mode_Control.pdf`
- Zotero item: `CLXWL327`
- Paper: Jian Li and Fred C. Lee, IEEE TPEL 2010

The skill must not bundle the PDF. These notes record the audit boundary and registry work needed for a self-contained implementation.

## Formula chain observed in the paper

The current-mode COT derivation is not only Eq. (9). The paper chain is:

1. COT current-mode event law with fixed `Ton` and perturbed `Toff`.
2. Fourier/DF derivation of `iL/vc`.
3. Eq. (9): exact exponential control-to-inductor-current relation.
4. Eq. (10): Padé approximation with `w1 = pi/Ton` and `Q1 = 2/pi`.
5. Eq. (11): first control-to-output approximation using output network.
6. Eq. (12)-(13): input-voltage and output-voltage perturbation paths.
7. Eq. (14)-(15): `k1(s)` and `k2(s)` low-order path ratios.
8. Eq. (16): final current-mode COT `vo/vc` with output-network term and high-frequency double-pole term.

The current implementation has `Fc` exact/Padé plus low-order `k1/k2` adapter support. The current implementation does not yet claim FIGURE_REPRODUCED for the full Eq. (16) `Gvc` paper curves.

## Eq. (16) implementation target

The complete `Gvc` benchmark must bind the final paper-level chain rather than using `Fc` alone. The implementation should keep these pieces separate:

```text
Fc: control-to-inductor-current DF
k1: input-voltage path ratio
k2: output-voltage path ratio
output_network: ESR/load/capacitor term
hf_pair: 1/(1+s/(Q1*w1)+s^2/w1^2)
Gvc_li2010: Eq. (16) composition
```

Only after these pieces are bound and checked should the benchmark plot `Gvc`.

## Paper-figure validation targets

Prepare separate benchmarks for:

- `Ri sweep`: user-requested current-mode COT `Gvc` with `Ri = 0.2 mOhm` and related paper sweep values.
- `external ramp sweep`: user-requested `se = 0.2*sf` and other paper sweep values, while recording whether the source is Li/Lee 2010 extension or Tian 2015 external-ramp model.
- output impedance and audio susceptibility only after their target semantics are registered.

## Required honesty

- Do not say the existing `li_lee2010_cot_cm` benchmark reproduces the paper `Gvc` figure; it currently checks Eq. (9)-(10) subformulas.
- Do not use Tian 2015 as an explanation for a Li/Lee 2010 figure unless the selected source and equation chain are explicitly changed.
- Do not infer figure parameters from image appearance. Use paper text, table values, digitized plot metadata, or user-provided values.
- Do not promote to `FIGURE_REPRODUCED` until low-frequency gain, peaking/crossover region, high-frequency trend, and sweep direction agree with the paper figure within a stated tolerance.

## Next implementation slice

1. Add registry entries for Eq. (16) composition.
2. Add a benchmark scaffold for `li_lee2010_current_mode_gvc_ri_sweep`.
3. Generate two Bode paths:
   - direct paper Eq. (16) composition;
   - current registry/adapter path.
4. Compare the two paths and mark discrepancies before changing validation level.
