# Li and Lee 2009 V2 COT proof skeleton

## 1. Paper scope
V2 current-mode/COT output-ripple model; DOI `10.1109/APEC.2009.4802672`.
## 2. Circuit/control law
The comparator observes output/capacitor ripple; fixed on-time and ripple crossing determine the cycle.
## 3. Switching event
Use the paper ripple-crossing construction; preserve ESR/capacitor-ripple participation rather than inventing a current-sense event.
## 4. Perturbation variables
Control voltage, output ripple, capacitor current/voltage, and edge timing.
## 5. Edge sensitivity step
Linearize the ripple crossing and track the switching-frequency pair and on-time pair.
## 6. How DF is formed
The paper supplies a direct `Gvc`; v0.3 does not reverse-engineer fake multiport `a_*` coefficients.
## 7. How power stage is coupled
The direct paper transfer already contains the relevant ripple/power interaction for this interface.
## 8. Final transfer relation
Use the `Gvc` expression and stability boundary reproduced in `df-coefficient-library.md`.
## 9. Approximation made
The bundled model is Padé/low-order; the further small-duty form drops the on-time high-frequency pair.
## 10. Validation used in paper
Use paper comparisons as provenance; bundled OS-CON/ceramic boundary cases are offline checks, not original trace reproduction.
## 11. What can be generalized
Keep direct-transfer interfaces when that is what the source actually derives.
## 12. What must not be generalized
Do not infer `a_o`, `a_i`, or an exact model; do not reuse the ESR stability boundary for different ripple injection networks.
