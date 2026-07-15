# Buck Hybrid Small-Signal Modeling

This context defines the language used to turn a confirmed Buck schematic into an auditable hybrid small-signal model.

## Language

**Proposed Circuit IR**:
A machine-readable interpretation extracted from a schematic image whose connectivity, polarity, and switching semantics have not yet been accepted by the user.
_Avoid_: Parsed circuit, recognized schematic

**Confirmed Circuit IR**:
A Proposed Circuit IR whose exact content hash has been accepted as the authoritative description of circuit connectivity and component orientation.
_Avoid_: Schematic truth, inferred netlist

**Physics Spec**:
The confirmed operating point, switching sequence, event guards, perturbation ports, target response, and approximation boundary used with a Confirmed Circuit IR.
_Avoid_: Assumptions blob, simulation setup

**Switch Mode**:
One interval of the hybrid orbit in which switch and diode conduction states, circuit equations, and continuous vector field are fixed.
_Avoid_: Duty state, phase

**Switching Event**:
A fixed-time or guard-triggered transition between Switch Modes, including its direction and reset semantics.
_Avoid_: Sample, edge, trigger when the distinction matters

**Periodic Orbit**:
The steady repeating switched trajectory and event sequence about which the small-signal model is linearized.
_Avoid_: DC operating point, average solution

**Hybrid Linearization**:
The composition of within-mode variational flow and event sensitivity around a Periodic Orbit.
_Avoid_: Average model, hand-derived DF

**Saltation Matrix**:
The common-nominal-time perturbation jump across a state-dependent switching event.
_Avoid_: Poincare projection

**Poincare Projection**:
The event-endpoint projection used when a cycle map returns the state on the moving event section itself.
_Avoid_: Saltation matrix

**Poincare Model**:
The authoritative once-per-cycle discrete state-space model anchored at a declared section of the Periodic Orbit.
_Avoid_: Continuous plant, ordinary duty model

**Continuous Baseband Response**:
The analog-output fundamental obtained by lifting the Poincare state response through every within-cycle variational flow and Fourier-projecting at the perturbation frequency.
_Avoid_: Section-sampled transfer, averaged response

**Registry Cross-check**:
An independent comparison between a physics-derived result and a registered paper formula; it is evidence, not a source for the physics-derived equations.
_Avoid_: Formula binding, paper-derived model

**Physics Override**:
An explicit user decision to continue past a named applicability or quality failure, permanently downgrading the result.
_Avoid_: Ignore warnings, force pass

**Regularized Diagnostic**:
A non-authoritative candidate obtained from a recorded epsilon sweep or secant limit study when the unregularized numerical problem is singular or non-smooth.
_Avoid_: Fixed model, stabilized solution
