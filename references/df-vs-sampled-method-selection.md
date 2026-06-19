# DF vs sampled-data method selection

Use this document when an intake could fit both describing-function and sampled-data language.

## Describing-function path

Choose DF when the paper or derivation represents the modulator as a nonlinear block whose perturbation relation is converted into duty/current/output relations.

Examples:

- Li/Lee 2010 current-mode COT: current-loop DF and `Gvc` chain.
- Li/Lee 2009 V2 COT: direct DF `Gvc`.
- Tian 2015 current-mode COT with linear external ramp: a-star/three-terminal switch model.
- Lu 2023 RBCOT: DF loop-gain chain.

Required output:

```text
event law or paper DF → formula binding → target transfer → Bode evidence
```

## Sampled-data path

Choose sampled-data when the proof depends on sampling instants, Dirichlet values, sideband sums, pulse train structure, or `Fm` from sampled variables.

Examples:

- Yan 2022 Part I PCM/VCM/PVM/VVM.
- Yan 2022 Part II C-COT/V-COT zero-ramp sampled-data.

Required output:

```text
sampling event → left/right limits → Dirichlet value → Fm
→ pulse/sideband structure → GPWM/Gm → Gid/Gvd → Ti/Tv → Tc
```

## Cross-check path

Use both methods only as cross-checks, not substitutions. A sampled-data `Tc` is not automatically `Gvc`; a DF direct `Gvc` is not automatically a return ratio.

Cross-check examples:

- Compare low-frequency gain between DF and sampled-data when both are valid.
- Compare ESR/time-constant trend direction between V2/RBCOT and sampled-data trend benchmarks.
- Compare `fs/2` behavior only when both models declare that frequency range.

## Rejection rules

- If external ramp requires dynamic `Fm(s)`, reject v0.4 sampled-data registered path.
- If internal ramp, delay, RC injection, or sense filter appears, reject unless a matching registry contract exists.
- If the user requests a paper Bode figure but parameters or plotted target are unknown, ask for missing evidence or mark reproduction pending.
- If the model is protocol-derived, keep `PROTOCOL_DERIVED_UNVERIFIED` until independent practice evidence exists.
