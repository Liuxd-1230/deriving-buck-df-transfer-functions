# Lu 2023 RBCOT loop-gain proof skeleton

## 1. Paper scope
Accurate ESR-ripple RBCOT loop-gain model; DOI `10.1109/TPEL.2023.3254906`.
## 2. Circuit/control law
Fixed on-time RBCOT with output ESR ripple participating in edge generation.
## 3. Switching event
Use the paper pulse/output-ripple edge construction; output perturbation has a direct modulator path.
## 4. Perturbation variables
Control, duty/switching function, output ripple, load/power-stage state, and switching delay.
## 5. Edge sensitivity step
Linearize the edge and retain `1-exp(-sTsw)` terms through `Fdx` and `Fodx`.
## 6. How DF is formed
Form `Fdx`, `Fodx`, and `Fox=-Fodx-Fdx` as reproduced in `df-coefficient-library.md`.
## 7. How power stage is coupled
Couple to paper `Fp`; the sign adapter uses `a_o=-Fox` so the denominator is `1+Fox*Fp`.
## 8. Final transfer relation
Use `Floop=Fdx*Fp/(1+Fox*Fp)` and state the loop-break/sign convention.
## 9. Approximation made
Select exact delay or the paper Padé approximation explicitly; bundled Eq. (10) assumes `rL=0`.
## 10. Validation used in paper
Paper loop-gain comparisons provide provenance; bundled benchmark checks equations and key values without original SIMPLIS/measurement data.
## 11. What can be generalized
Separate direct control and output-ripple DF paths and audit feedback signs at the summing point.
## 12. What must not be generalized
Do not reuse the ESR-only `Fox` for ceramic/RC-injected/internal-ramp networks or count the output-ripple path twice.
