# Li and Lee 2010 COT current-mode proof skeleton

## 1. Paper scope
Single-phase CCM current-mode COT entity and equivalent circuit; source DOI `10.1109/TPEL.2010.2040123`.
## 2. Circuit/control law
Fixed `Ton`; sensed inductor current reaches a control threshold and variable off-time sets the period.
## 3. Switching event
Use the inter-cycle threshold relation reproduced in `df-coefficient-library.md`; do not replace it with an average duty law.
## 4. Perturbation variables
Control voltage, input/output voltage, inductor current waveform, and edge/period timing.
## 5. Edge sensitivity step
Perturb consecutive threshold crossings and solve the off-edge timing recurrence.
## 6. How DF is formed
Take the Fourier fundamental of the pulse/current sequence, yielding paper `Fc` and low-order `Fg/Fo` ratios.
## 7. How power stage is coupled
Adapt the closed current-source relation to `a_*` through the Buck inductor port identity.
## 8. Final transfer relation
Use `iL=Fc*uc+Fg*vg+Fo*vo`, then the documented `derived-adapter`; do not claim paper-native `a_*`.
## 9. Approximation made
The exact `Fc` contains `exp(-sTon)`; bundled `Fg/Fo` paths use paper low-order ratios. The Padé form is optional and explicit.
## 10. Validation used in paper
Use the paper comparisons as source context; the bundled offline benchmark verifies formulas/key values, not original simulation traces.
## 11. What can be generalized
Fixed-on-time edge recurrence, current-source entity, and adapter algebra.
## 12. What must not be generalized
The `Fc`, `Fg`, or `Fo` coefficients to external ramp, V2/RBCOT, DCM, or modified sensing without re-deriving the event.
