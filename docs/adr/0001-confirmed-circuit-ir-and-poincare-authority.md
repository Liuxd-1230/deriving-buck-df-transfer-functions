# ADR 0001: Confirmed Circuit IR and Poincaré model are authoritative

- Status: Accepted
- Date: 2026-07-15

## Context

The v0.4.5 registry path can prove that a formula came from a named paper, but a nearby paper topology is not evidence that the same formula describes a user-uploaded circuit. Image recognition is also probabilistic and cannot safely become an equation source.

## Decision

For v0.5 user-circuit derivations:

1. The schematic image is immutable provenance.
2. A multimodal agent may propose Circuit IR, but deterministic checks and user confirmation are mandatory.
3. The exact Confirmed Circuit IR content hash and Confirmed Physics Spec are the circuit/event truth.
4. Component stamping generates Hybrid MNA/DAE mode equations.
5. The event-to-event Poincaré model is the authoritative small-signal state model. Common-time saltation monodromy is retained as separate hybrid-event evidence.
6. Registered formulas generate independent formula, trend, valid-band, or sideband cross-checks only.

## Consequences

- No agent-written active equation can bypass Circuit IR.
- A registry mismatch cannot overwrite the physical model; it blocks or requires a recorded downgrade.
- A registry match cannot upgrade internal validation to external validation.
- Any changed connection, polarity, port, event, or value invalidates downstream hashes.
- v0.4.5 paper benchmarks remain available and compatible as a parallel workflow.
