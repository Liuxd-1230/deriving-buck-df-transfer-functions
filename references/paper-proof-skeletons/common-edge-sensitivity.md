# Common edge-sensitivity proof skeleton

## 1. Paper scope
Reusable event-linearization skeleton for a single-phase CCM switching model; it is not itself a paper formula.
## 2. Circuit/control law
State the switch states, fixed timing, comparator law, and signal signs.
## 3. Switching event
Write each movable edge as `F(x(t_k),u(t_k),t_k)=0`.
## 4. Perturbation variables
Declare state, control, input, output, load, ramp, delay, and edge-time perturbations.
## 5. Edge sensitivity step
Linearize to `delta_t_k=-delta_F(t_k)/Fdot_0(t_k)`; include every path entering `delta_F` and the total steady edge slope.
## 6. How DF is formed
Map edge motion to pulse area or switching-function harmonics; keep delay/exponential terms until an approximation is declared.
## 7. How power stage is coupled
Insert the resulting `d_hat` relation into the CCM Buck port equations.
## 8. Final transfer relation
Solve only the requested port ratio and preserve sign conventions.
## 9. Approximation made
List harmonic truncation, Padé/Taylor approximation, ignored parasitics, and frequency boundary.
## 10. Validation used in paper
Not applicable; require a selected paper benchmark or independent switching evidence.
## 11. What can be generalized
The implicit-event sensitivity relation and evidence ordering.
## 12. What must not be generalized
Numerical slopes, coefficients, sideband terms, or validation range from one control law to another.
