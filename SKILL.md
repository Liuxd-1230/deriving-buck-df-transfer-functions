---
name: deriving-buck-df-transfer-functions
description: Derive and check single-phase CCM Buck small-signal models from schematics or confirmed circuit data using a physical-first Circuit IR, Hybrid MNA/DAE, periodic-orbit shooting, saltation/Poincare linearization, z-domain response, and sidebands. Use for COT, current-mode COT, external-ramp COT, V2 COT, ESR-ripple RBCOT, Gvc/Gvg/Zout/Tloop, circuit-physics interpretation, or legacy registered DF/sampled-data paper benchmarks.
---

# Deriving Buck DF Transfer Functions

## Route first

Choose exactly one path.

- For a user schematic, uploaded circuit image, netlist-like description, or a request to understand the actual circuit, use the v0.5 physical path.
- For an existing registered paper benchmark or a request to reproduce a legacy v0.4.5 artifact, use the legacy registry path.
- Never replace a user circuit with the nearest paper formula. A registry result is cross-check evidence only.

## v0.5 physical path

Use this hash-linked state machine:

```text
IMAGE_INTAKE → CIRCUIT_IR_PROPOSED → TOPOLOGY_CONFIRMED
→ PHYSICS_SPEC_CONFIRMED → MODE_DAE → PERIODIC_ORBIT
→ HYBRID_LINEARIZATION → PHYSICS_CHECKERS
→ REGISTRY_CROSSCHECK → REPORT
```

### Trust boundaries

1. Let multimodal reasoning propose Circuit IR; do not let it author active equations.
2. Run deterministic connectivity, terminal, orientation, dimension, Buck-topology, ambiguity, image-hash, and checkout-overlay checks.
3. Stop at `ASK_USER_ONLY` for any unresolved wire, comparator polarity, switch semantic, missing value, or missing target/port meaning.
4. Continue only after the user confirms the annotated Circuit IR.
5. Confirm a separate Physics Spec containing working point, target, signs, mode order, guard direction, fixed/moving events, reset/delay semantics, Poincaré section, fidelity, and approximations.
6. Treat component-stamped Hybrid MNA/DAE and the confirmed event specification as the physical source of truth.

Read [Circuit IR protocol](references/v05-circuit-ir-protocol.md) whenever an image or topology is involved. Read [Hybrid MNA protocol](references/v05-hybrid-mna-protocol.md) before accepting mode equations.

### Derivation and validation

1. Generate each mode as `E xdot = A x + B u + b`, retaining algebraic variables, KCL/KVL, constitutive equations, energy states, and component provenance.
2. Solve the periodic orbit with exact affine flow, guard root finding, and shooting. Record event left/right limits and mode durations.
3. Require scaled KCL/KVL, fixed-point, volt-second, charge, and power/energy residuals at or below `1e-7`.
4. Require positive minimum inductor current for CCM. An unstable Floquet result is a valid physical result, not a derivation failure.
5. Generate both the common-time saltation matrix and the event-to-event Poincaré projection. Use the event-to-event map for authoritative `Ad/Bd` and z-domain targets.
6. Validate analytic `Ad/Bd` against an independent `solve_ivp` switching map with central finite differences. Require relative error at or below `1e-3`.
7. Reconstruct continuous baseband and sidebands from piecewise variational flow. Start with `M=3`, double through at most `M=64`, and require adjacent truncations within `0.1 dB / 1 deg`.
8. Rebuild MNA, orbit, and event linearization for normalized local sensitivities of declared L, C, load, ESR/DCR, gains, ramp, timing, and delay parameters.
9. Explain modes with current paths, stored/dissipated/source energy, participation factors, residues, and sensitivities. Attribute a zero only when an explicit path decomposition supports it.

Read [periodic-orbit protocol](references/v05-periodic-orbit-protocol.md), [event/Poincaré protocol](references/v05-event-poincare-protocol.md), [continuous/sideband protocol](references/v05-sideband-protocol.md), and [physics interpretation/report protocol](references/v05-physics-interpretation-report.md) for the corresponding stages.

### Commands

```bash
python scripts/circuit_ir.py image-intake --image schematic.png --case-id CASE --out image_intake.json
python scripts/circuit_ir.py propose --ir proposed_ir.json --image-intake image_intake.json --out circuit_ir_proposed.json
python scripts/circuit_ir.py validate --ir circuit_ir_proposed.json --image schematic.png --overlay circuit_checkout.png
python scripts/circuit_ir.py confirm --ir circuit_ir_proposed.json --out circuit_ir.json
python scripts/physics_spec.py --spec physics_spec_proposed.json --circuit-ir circuit_ir.json --out physics_spec.json
python scripts/derive_physics_model.py --circuit-ir circuit_ir.json --physics-spec physics_spec.json --out result/
```

Create the V² COT golden inputs with:

```bash
python scripts/v05_golden_cases.py --family v2-cot --image examples/v05-v2-cot/schematic.svg --registry-crosscheck --out golden-inputs/
```

Supported v0.5 golden families are `v2-cot`, `current-mode-cot`, `external-ramp-cot`, and `esr-ripple-rbcot`.

### Failure and override policy

- Stop on unconfirmed topology, missing physical parameters, singular nominal topology, invalid event order/direction, absent event, absent periodic orbit, or non-transverse analytic event.
- Run normalized `gmin/rmin` epsilon sweeps only in the explicit diagnostic branch. Run decreasing-step secant Poincaré sweeps for near grazing. Never add a hidden epsilon to a saltation denominator.
- Keep every numerical diagnostic permanently `REGULARIZED_DIAGNOSTIC_UNVERIFIED`, even when it converges.
- Allow only post-solve residual, CCM, sideband, independent-Jacobian, external-data, or registry-deviation checks to be individually overridden. Record check code, reason, and user confirmation; set `FORCED_PHYSICS_OVERRIDE_UNVERIFIED` permanently.
- Do not launch SIMPLIS. Accept user-supplied external data only with frequency, magnitude, phase, target, port/sign, loop-break, working-point, and source metadata.

Use only these successful validation states:

- `PHYSICS_DERIVED_INTERNAL_VALIDATED`
- `PHYSICS_DERIVED_EXTERNAL_CROSSCHECKED`
- `FORCED_PHYSICS_OVERRIDE_UNVERIFIED`
- `REGULARIZED_DIAGNOSTIC_UNVERIFIED`

## v0.4.5 legacy registry path

Keep legacy commands and artifacts compatible. Start with `intake_status.json`; stop at `INCOMPLETE → ASK_USER_ONLY` for missing target, mode, events, comparator inputs, sensing layer, or core parameters. Do not invent typical values.

```text
INTENT_CLASSIFY → PREFLIGHT_INTAKE → MODEL_CLASSIFY → FORMULA_BINDING
→ DERIVATION → CHECKERS → REPORT
```

The machine-readable formula source remains `registries/formula_registry.yaml`. Registered direct models may emit only registered direct transfers; registered multiport models must bind every `a_*`; Yan sampled-data models must retain sampling, `Fm`, pulse, target mapping, and sideband evidence. New legacy-path equations remain explicitly unverified.

Retain classifier branches `DF_REGISTERED_DIRECT`, `DF_REGISTERED_MULTIPORT`, `SAMPLED_DATA_REGISTERED`, and `PROTOCOL_DERIVED_NEW`. A new legacy-path model must still establish `F(x,u,t)=0` and carry `UNVERIFIED_NEW_DF_MODEL` or `PROTOCOL_DERIVED_UNVERIFIED`. Read [legacy circuit intake](references/circuit-intake-protocol.md) and [legacy DF reasoning](references/df-reasoning-protocol.md) for those artifacts.

Use these commands for legacy work:

```bash
python scripts/preflight_intake.py --intake circuit.json --out intake_status.json
python scripts/df_buck_sympy.py classify --intake-status intake_status.json --out classification.json
python scripts/build_proof_object.py --intake-status intake_status.json --classification classification.json --out proof_object.json
python scripts/derive_transfer.py --proof proof_object.json --out derivation.json
python scripts/check_derivation.py --proof proof_object.json --derivation derivation.json --out checker_result.json
python scripts/render_derivation_report.py --intake-status intake_status.json --classification classification.json --proof-object proof_object.json --derivation derivation.json --checker-result checker_result.json --out report.md --manifest report_manifest.json
python scripts/df_buck_sympy.py make-case --model MODEL --params params.json --out case.json
python scripts/df_buck_sympy.py benchmark --all
```

Read [model ontology](references/model-ontology.md), [model applicability](references/model-applicability-contract.md), [sensing policy](references/sensing-layer-policy.md), and [DF versus sampled-data selection](references/df-vs-sampled-method-selection.md) when classifying a legacy case. Read [sampled-data protocol](references/sampled-data/sampled-data-protocol.md) for Yan Part I/II.

The retained v0.3.1/v0.4.5 generators are `cot-cm-li-lee-2010`, `cot-cm-external-ramp-tian-2015`, `rbcot-esr-lu-2023`, and `v2-cot-li-lee-2009`. Read [DF coefficient library](references/df-coefficient-library.md) for provenance. For audits, read [formula audit plan](references/formula-audit-plan.md), [paper Bode validation](references/paper-bode-validation-spec.md), and [Li/Lee 2010 Gvc boundary](references/li-lee-2010-current-mode-gvc.md).

## Universal guardrails

- Require an explicit loop break for `Tloop`: injection point, OUT/IN, sign, forward path, feedback path, and `H`.
- Do not report PM/GM for `Gvc`, `Gvg`, `Zout`, `Gm`, or `GPWM`; margins apply only to an explicit return ratio.
- Do not label an averaged model as DF or Poincaré physics. Use averaging only as a low-frequency cross-check.
- Do not extrapolate single-phase CCM results to multiphase overlap, DCM, pulse skipping, burst, or nonlinear current limit.
- Keep formula provenance, image provenance, confirmation hashes, predecessor hashes, signs, units, approximations, valid bands, failures, and evidence boundaries visible in the final report.
