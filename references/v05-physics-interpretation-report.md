# v0.5 physics interpretation and report protocol

## Explain causes from evidence

For every mode, connect equations to physical paths:

- source and commutation path;
- inductor voltage and current slope;
- capacitor charge/discharge path;
- ESR/DCR/load dissipation;
- comparator guard variable and crossing direction;
- reset, ramp, timer, sampling, and delay memory.

For every Floquet/Poincaré mode, report right/left participation, confirmed physical energy-state amplitude, input/output residue, and parameter sensitivities. Name a mode only when those independent indicators agree.

Do not label a zero from its visual location. Require an explicit feedforward/feedback/path decomposition and preserve that evidence. Otherwise use `UNATTRIBUTED_PATH_EVIDENCE_INSUFFICIENT`.

## Sensitivity contract

Use normalized central local sensitivity

$$
S_p^y=\frac{p}{y}\frac{\partial y}{\partial p}.
$$

Rebuild the component-stamped model, orbit, and event linearization at both perturbations. Cover every declared nonzero L, C, load, ESR, DCR, sampling gain, ramp slope, on-time/period term, and delay term. Record zero-nominal parameters as not applicable rather than inventing a normalization.

## Registry cross-check

Bind an applicable registered model only after port, sign, working point, target, and frequency band match. Compare absolute transfer when semantics match. Use an explicitly labeled normalized-trend comparison when a paper variable uses a different port normalization; do not present it as absolute gain validation.

Require no more than `3 dB / 15 degrees` over the declared comparison band. A registry pass does not upgrade validation; a failure blocks unless the user records an allowed override.

## Paper-style report order

Render only from artifacts, in this order:

1. validation state and evidence boundary;
2. image hash, numbered circuit recognition, ambiguities, and confirmation;
3. working point, ports, signs, loop break, fidelity, and approximations;
4. mode current/energy paths and full MNA/DAE;
5. periodic orbit, event limits, balances, and CCM margin;
6. guard gradients, saltation, and Poincaré projection;
7. `Ad/Bd/Cd/Dd`, Floquet/Poincaré modes, and target z transfer;
8. sampled frequency response, continuous baseband, and sidebands;
9. poles/zeros, participation, residues, and parameter sensitivities;
10. registry/external comparisons, all checker results, overrides, and limitations.

State explicitly that the skill did not launch SIMPLIS. External data must include frequency, magnitude, phase, target, input/output port, sign, loop break when relevant, working point, and source metadata.
