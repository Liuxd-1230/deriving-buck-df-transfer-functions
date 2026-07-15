# v0.5 periodic-orbit protocol

## Preconditions

Require confirmed numeric inputs, load/device values, mode order, each fixed duration, each guard expression and direction, reset/delay semantics, Poincaré section, and enough independent initial physical state values. Mode equations may be reported before the initial guess exists, but do not solve a transfer function.

## Exact affine propagation

For each reduced mode

$$
\dot x=A_mx+B_mu+c_m,
$$

obtain `Phi`, `Gamma`, and `q` from one augmented matrix exponential. Do not replace a mode with an averaged duty equation.

Find a guard root only inside its declared `min_duration/max_duration` window and enforce its declared crossing direction. Apply resets in physical named variables or with an explicit reduced affine reset.

## Shooting

Define one complete event-to-event cycle map `P(x,u)` and solve

$$
P(x^\*,u)-x^\*=0.
$$

Store the fixed point, each mode duration, each event time, event left/right full-variable limits, and the final scaled residual. Stop with `FAIL_PERIODIC_ORBIT_NOT_FOUND` when shooting does not converge; do not return a transfer candidate.

## Physics balances

Reconstruct dense within-mode trajectories and independently check:

- descriptor KCL/KVL residual;
- inductor volt-second balance, including declared DCR drop;
- capacitor net charge;
- initial/final stored magnetic and electric energy;
- resistor and DCR dissipation;
- independent and controlled source absorbed/delivered energy;
- ideal-switch absorbed energy;
- total power/energy balance;
- minimum inductor current.

Scale each residual by the corresponding physical term norm and require `<=1e-7`. Require `iL_min>0` for CCM.

Floquet instability does not invalidate an orbit calculation. Report the instability as a physical property.
