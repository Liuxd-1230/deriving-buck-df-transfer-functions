# Paper Bode validation specification

Core principle: **practice is the final arbiter**. In Chinese engineering terms: **实事求是**. A clean symbolic derivation is a candidate; it becomes trusted only after it survives practical checks.

## Evidence levels

| Level | Meaning | What it can claim |
|---|---|---|
| `SUBFORMULA_VERIFIED` | One paper subformula matches symbolic/numeric probes. | The subformula was transcribed and evaluated consistently. |
| `CHAIN_VERIFIED` | Registered formulas compose into the intended transfer chain. | The internal derivation chain is algebraically consistent. |
| `FIGURE_REPRODUCED` | A paper Bode/key trend is reproduced with stated parameters and error notes. | The bundled model reproduces that named figure or trend. |
| `SIMULATION_OR_MEASUREMENT_REPRODUCED` | Switching simulation or measurement data independently agrees. | The model is supported by independent practice evidence. |

## Minimum Bode evidence

A single Bode point is not enough. A validation artifact must include:

- low-frequency gain or asymptote;
- crossover or important resonance/peaking region;
- behavior near the declared model limit such as `fs/2`;
- sweep direction for the paper variable, for example `Ri`, `se/sf`, `rC*C`, or `Ton`;
- parameters used, including any assumptions not stated by the paper figure;
- whether the curve is exact, Padé, truncated sideband, or paper simplified form.

## Honest claim rules

- Do not call a result `FIGURE_REPRODUCED` without a named figure, target transfer, parameters, and error/trend statement.
- Do not call registry consistency physical truth.
- Do not use PM/GM on `Gvc`, `Gvg`, `Zout`, `GPWM`, `Gm`, or `Tc`; only return ratios such as `Ti`, `Tv`, and `Tloop` support margin semantics.
- Do not use a paper figure from one mechanism as evidence for a different mechanism.
- If a figure is visually similar but parameter assumptions differ, keep the result partial.

## Benchmark artifact expectation

Each figure-oriented benchmark should contain:

```text
params.json
generated_case.json or derivation.json
formula_origin.json
bode_model.csv
bode.png
expected_key_values.json
expected_trends.json when applicable
notes.md
```

The notes must say exactly what was reproduced and what remains missing.
