# Model ontology and source index

v0.4.4 uses two indexes at the same time, followed by a registered-model applicability check:

1. **control ontology**: what physical/control mechanism the user has.
2. **source index**: which paper or registry entry supplies the formulas.
3. **applicability contract**: whether sensing, comparator inputs, sampled variable, timing, target semantics, and nonidealities match that registry entry.

Do not classify only by paper name. A paper can contain several mechanisms, and one mechanism can be checked against several papers.

## Control ontology

Use these fields when deciding the path before binding formulas:

| Field | Examples | Purpose |
|---|---|---|
| `control_mode` | `current-mode`, `voltage-mode`, `v2-cot`, `rbcot` | Prevents confusing V-COT sampled-data with V2 COT direct-transfer. |
| `timing` | `COT`, `COFT`, `fixed-frequency` | Chooses fixed-on/off-time pulse logic or fixed-frequency sampling. |
| `modeling_method` | `describing-function`, `sampled-data`, `direct-paper-transfer`, `protocol-derived` | Determines proof skeleton and checker. |
| `ramp` | `none`, `external`, `internal`, `zero-ramp`, `output-ripple` | Prevents using zero-ramp `Fm` on external/internal ramp cases. |
| `ripple_source` | `inductor-current`, `capacitor-ripple`, `capacitor-ESR`, `sampled-voltage` | Separates current-mode, V2 COT, and RBCOT. |
| `phase_scope` | `single-phase`, `multiphase-nonoverlap`, `multiphase-overlap` | Multiphase remains v0.5 unless separately registered. |

## Source index

Use source index only after the mechanism is known:

| Source key | Mechanism | Current registered role |
|---|---|---|
| `li-lee-2010` | Current-mode COT DF | Eq. (9)-(10) `Fc`, Eq. (14)-(15) low-order adapters; full Eq. (16) `Gvc` figure reproduction pending. |
| `li-lee-2009` | V2 COT capacitor-ripple DF | Direct-transfer `Gvc`; no fake `a_*`. |
| `tian-2015` | Current-mode COT with linear external ramp | External-ramp three-terminal/a-star model. |
| `lu-2023` | ESR-ripple RBCOT | Loop-gain/return-ratio model; PM/GM semantics apply only to return ratios. |
| `yan-2022-part-i` | PCM/VCM/PVM/VVM sampled-data | Dirichlet and sideband proof skeleton. |
| `yan-2022-part-ii` | COT/COFT sampled-data | Two pulse trains and zero-ramp sampled-data path. |

## Non-substitution rules

- **V-COT sampled-data** is not **V2 COT direct-transfer**.
- **RBCOT loop gain** is not plain `Gvc`; it must preserve return-ratio semantics.
- **Li/Lee 2010 current-mode COT** is not Tian external-ramp unless a linear external ramp is present and the source is declared.
- **Yan 2022 zero-ramp sampled-data** must not be used for 2026 dynamic `Fm(s)`, internal ramp, delay, RC injection, sense filter, or multiphase paths.

## Classifier expectation

The classifier should:

```text
user request / intake
→ infer control ontology conservatively
→ reject unsupported nonideal or multiphase boundaries
→ bind a paper/source index only when the ontology matches
→ emit target semantics and validation level
```

If the ontology is ambiguous, stop at `INCOMPLETE` or `PROTOCOL_DERIVED_UNVERIFIED`; do not select the closest-looking paper.
