# Tian 2015 external-ramp proof skeleton

## 1. Paper scope
Three-terminal switch DF for COT current mode with a linear external ramp; DOI `10.1109/TPEL.2015.2508037`.
## 2. Circuit/control law
Fixed `Ton`; the off-edge comparator combines sensed current, control voltage, and external ramp.
## 3. Switching event
Use the consecutive-cycle event in `df-coefficient-library.md`, containing `se`, `sf`, `Ton`, and `Tsw`.
## 4. Perturbation variables
Control, input, output, current waveform, off-edge time, and switching period.
## 5. Edge sensitivity step
Perturb the event; total edge dynamics form `A(s)=(sf+se)-se*exp(-sTsw)`.
## 6. How DF is formed
Convert the off-edge recurrence into paper `Fc/Fg/Fo`, retaining exponential terms before Eq. (8) low-order reduction.
## 7. How power stage is coupled
Use the documented closed-current-source to Buck duty adapter.
## 8. Final transfer relation
Generate `a_c/a_g/a_o/a_i` from `Fc/Fg/Fo`, then solve the requested Buck transfer.
## 9. Approximation made
Eq. (8) is first order; `fp` and `fz` follow the stated low-order path and are not the exact multi-input model.
## 10. Validation used in paper
Paper equations/equivalent-circuit comparisons support the model to its stated range; bundled evidence reproduces formulas and key trends only.
## 11. What can be generalized
The event-sensitivity workflow and need to include ramp slope/delay in `Fdot_0`.
## 12. What must not be generalized
Do not reuse `A(s)` for an RC/nonlinear/internal ramp. Recompute `vramp(t)`, edge slope, recurrence, and DF.
