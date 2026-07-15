# v0.5 event linearization and Poincaré protocol

## Guard and reset data

Let an event satisfy

$$
F(x,u,t)=0,
$$

with reset `x+ = R*x- + S*u + r`, pre/post vector fields `f-` and `f+`, guard gradients `n=Fx`, `Fu`, and

$$
\dot F=n^T f^-+F_t.
$$

Require a transverse event. Do not add epsilon to a small `Fdot`.

## Keep two different matrices

The common-nominal-time saltation matrix is

$$
\Xi=R+\frac{(f^+-Rf^-)n^T}{\dot F},
$$

with input term

$$
\Xi_u=S+\frac{(f^+-Rf^-)F_u}{\dot F}.
$$

This is the hybrid-flow discontinuity evidence used for saltation monodromy.

The event-to-event Poincaré endpoint projection is instead

$$
\Pi=R-\frac{(Rf^-)n^T}{\dot F},
$$

$$
\Pi_u=S-\frac{(Rf^-)F_u}{\dot F}.
$$

Use `Pi/Pi_u` when the section is the event itself and the cycle map returns the state immediately after that event. Confusing `Xi` with `Pi` produces a Jacobian that fails direct event-to-event finite differences.

## Composition and ports

Compose exact flow matrices with `Pi/Pi_u` to obtain authoritative `Ad/Bd`. Compose with `Xi/Xi_u` separately and preserve the saltation monodromy artifact. Derive `Cd/Dd` from confirmed output-port expressions on the declared section.

For a requested SISO target, bind the exact input/output columns and form

$$
G(z)=C_d(zI-A_d)^{-1}B_d+D_d.
$$

Use `z=exp(j*omega*T)` for sampled frequency response. Generate an s-domain low-frequency expression only by a declared series expansion and state its order and frequency boundary.

Require an explicit loop break before deriving `Tloop`. Apply the declared sign to `Zout` and disturbance ports.

## Independent validation

Integrate the same mode vector fields with `solve_ivp`, detect switching events independently, and central-difference the resulting cycle map in every state and input direction. Require relative `Ad` error `<=1e-3`; check `Bd` to the same threshold. The validation path must not call the affine matrix-exponential flow or its guard root finder.

For near grazing, sweep decreasing secant perturbations. Emit a candidate only when successive Jacobians converge, and keep it `REGULARIZED_DIAGNOSTIC_UNVERIFIED`.
