# Formula audit plan

The goal is to make registered formulas useful to agents without letting agents drift. Registry formulas are executable truth sources, but practice is still required: formulas must be checked against paper key values, Bode curves, switching simulations, or measurements before higher validation claims.

## Audit order

1. **Li/Lee 2010 current-mode COT**
   - Audit Eq. (9) control-to-inductor-current DF.
   - Audit Eq. (10) Padé/current-loop approximation.
   - Audit Eq. (14)-(15) low-order `k1`, `k2` paths.
   - Add the complete Eq. (16) `Gvc` chain before any figure-level claim.
   - Prepare `Ri sweep` and external-ramp sweep paper-figure checks separately.

2. **Li/Lee 2009 V2 COT**
   - Keep as direct-transfer `Gvc`.
   - Do not invent `a_c/a_g/a_o/a_i`.
   - Preserve the stability boundary `rC*C > Ton/2`.
   - Compare OSCON/ceramic cases by trend before claiming curve reproduction.

3. **Lu 2023 RBCOT**
   - Keep `Fdx/Fodx/Fox/Fp/Floop` chain as loop-gain semantics.
   - PM/GM are valid only when the response is a return ratio.
   - ESR sweep must check trend direction and paper parameter assumptions.

4. **Tian 2015 external-ramp current-mode COT**
   - Keep as current-mode COT plus linear external ramp.
   - Do not use it as a substitute for Li/Lee 2010 zero-ramp current-mode figures.
   - Do not mix it with Yan 2026 dynamic `Fm(s)` sampled-data formulas.

5. **Yan/Na sampled-data papers**
   - Part I/II remain sampled-data registered paths.
   - Zotero Yanna collection is a development source map; runtime artifacts remain self-contained.
   - 2025/2026 external-ramp, multiphase, nonoverlap/overlap are v0.5 boundaries until formulas and benchmarks are separately registered.

## Zotero/Yanna development source map

The local Zotero collection `Yanna` (`525GRVBQ`) was checked during 0.4-series development. It contains:

- Yan/Ruan/Li 2022 Part I: peak/valley current-mode and voltage-mode sampled-data modeling.
- Yan/Ruan/Li 2022 Part II: constant ON-time and constant OFF-time sampled-data modeling.
- Yan group sideband-effect paper for voltage-mode boost stability.
- Yan group 2025 multiphase COT sampled-data modeling.
- Yan group 2025 multiphase COT phase-nonoverlap sampled-data modeling.
- Yan group 2026 current-mode COT with external ramp compensation.

Use this map to find PDFs during development. Do not make runtime behavior depend on Zotero, and do not bundle PDFs in the skill.

## Required formula inventory per model

Each registered path needs:

- control ontology fields;
- source index fields;
- formula IDs and source equations;
- target transfer semantics;
- approximation policy;
- valid frequency range;
- numeric probes;
- Bode/trend benchmark plan;
- explicit not-covered list.

## Audit output

For every formula chain, write:

```text
paper equation → registry formula_id → proof binding → derivation step
→ Bode/trend evidence → validation level
```

If any arrow is missing, the validation level must stay partial or unverified.
