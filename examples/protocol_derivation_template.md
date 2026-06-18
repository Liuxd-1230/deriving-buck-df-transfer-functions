# DF protocol derivation

## Model classification
Declare `NEAR_MODEL` or `NEW_MODEL` and the action.
## Assumptions and unsupported effects
State single-phase CCM assumptions and exclusions.
## State variables and switching states
Define states and piecewise equations.
## Steady-state trajectory
Solve the periodic orbit used at the edge.
## Switching event equation
Write `F(x,u,t)=0` and identify the movable edge.
## Edge perturbation
Show `delta_t=-delta_F/Fdot_0` and fixed/variable timing.
## Describing-function relation
Explain pulse-area/harmonic formation and equivalent-duty meaning.
## Mapping to a_c/a_g/a_o/a_i
List every coefficient or justify a direct transfer.
## Buck power-stage coupling
Write the coupled CCM Buck equations.
## Transfer function
Show the candidate requested ratio.
## Sanity checks
Record dimensions, DC/limits, and frequency range.
## Validation status
Use `PROTOCOL_DERIVED_UNVERIFIED` and list missing evidence.
## What is paper-derived vs newly derived
Tag each component's provenance.
