# v0.5 Hybrid MNA/DAE protocol

## Equation convention

Stamp every confirmed mode into

$$
E\dot z = Az + Bu + b,
$$

where `z` retains node voltages, branch currents of voltage-defined elements, energy states, ramp/timer states, and LTI-block states. Keep algebraic variables so the report can show KCL, KVL, switch constraints, and provenance.

## Stamp semantics

Use the terminal polarity and current direction declared in Circuit IR.

| Element | Descriptor contribution |
| --- | --- |
| Resistor | conductance in the nodal `A` block |
| Capacitor | capacitance in the nodal `E` block |
| Inductor | branch current, KCL incidence, and `L di/dt = vp-vn-rL i` |
| Voltage/current source | declared DC and input-column contribution |
| VCCS/VCVS | control-terminal incidence and declared gain |
| Ideal switch/diode ON | exact zero-voltage constraint |
| Ideal switch/diode OFF | exact zero-current constraint |
| Ramp | `xdot=slope` in declared active modes plus voltage output constraint |
| Timer | `xdot=rate` in declared active modes |
| Rational LTI block | declared SISO state-space realization |

Comparators contribute event semantics, not an invented continuous constitutive equation.

## Index-1 reduction

Use an SVD basis of `E` to separate dynamic and algebraic coordinates. With transformed blocks,

$$
E_{11}\dot x=A_{11}x+A_{12}y+B_1u+b_1,
$$

$$
0=A_{21}x+A_{22}y+B_2u+b_2.
$$

Require nonsingular `A22`. Eliminate only for numerical propagation:

$$
\dot x=A_r x+B_r u+c_r,
$$

and retain reconstruction `z=Zx*x+Zu*u+z0` plus the original descriptor artifact.

## Physical interpretation

For each mode, state which commutation devices conduct, how source energy reaches the inductor/load, where capacitor current flows, which elements dissipate power, and which states store energy. Derive this text from component IDs, terminals, mode assignments, and stamped laws.

## Hard failures

Return explicit codes for floating topology, ideal-source loop, singular algebraic block, missing switch assignment, incompatible mode descriptor, unsupported component, nonpositive passive value, invalid LTI realization, or non-Buck power path.

Never repair a nominal singular model silently. An explicitly requested normalized `gmin/rmin` epsilon sweep belongs only to the diagnostic branch and stays unverified.
