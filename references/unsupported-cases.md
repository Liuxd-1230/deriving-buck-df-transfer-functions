# Unsupported cases

Reject, rather than adapt a single-phase CCM formula, when the intake contains:

- DCM or boundary conduction;
- pulse skipping, burst operation, saturation, or nonlinear current limiting;
- multiphase overlap or phase-management events;
- a non-Buck power stage;
- an average model represented as a describing function;
- an image or SPICE netlist with no explicit comparator event.

An average model can be used only as a low-frequency sanity check and must be labeled average model. Huang 2025 internal-ramp/DC-extractor is excluded from the DF registry for this reason. No automatic circuit-image recognition or full SPICE-to-DF generation is claimed.
