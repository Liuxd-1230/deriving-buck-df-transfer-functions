# Unsupported cases

Reject, rather than adapt a single-phase CCM formula, when the intake contains:

- DCM or boundary conduction;
- pulse skipping, burst operation, saturation, or nonlinear current limiting;
- multiphase overlap or phase-management events;
- a non-Buck power stage;
- an average model represented as a describing function;
- an image or SPICE netlist with no explicit comparator event.
- switch-node RC, sense-filter, or RC-derived comparator ramps routed to a registered zero-ramp sampled-data model;
- RC-derived comparator ramps represented only by local crossing slope or slope-only `Kmod`.

An average model can be used only as a low-frequency sanity check and must be labeled average model. Huang 2025 internal-ramp/DC-extractor is excluded from the DF registry for this reason. No automatic circuit-image recognition or full SPICE-to-DF generation is claimed.

RC-derived comparator ramps are not automatically unsupported forever, but without a registered RC-memory model they may only be rejected, downgraded, or marked `PROTOCOL_DERIVED_UNVERIFIED` with explicit state-memory proof metadata.
