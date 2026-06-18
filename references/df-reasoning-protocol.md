# DF reasoning protocol

## Mandatory 12-step chain

1. Define state variables and perturbation signs.
2. Write each switch-state differential equation.
3. Write the steady periodic trajectory.
4. Define every movable switching event as `F(x,u,t)=0`.
5. Perturb the event condition.
6. Obtain edge motion from `delta_t=-delta_F/Fdot_0` or an explicitly equivalent relation.
7. Convert edge motion into switching-function/pulse-area perturbation; explain why `d_hat` need not be ordinary low-frequency duty.
8. Form `d_hat=a_c uc_hat+a_g vg_hat+a_o vo_hat+a_i iL_hat` or a justified direct transfer.
9. Couple that relation to the CCM Buck power-stage equations.
10. Solve the requested transfer function.
11. Perform symbolic, dimensional, DC, limiting, and frequency-range sanity checks.
12. Assign the validation status and list missing evidence.

Steps 4–8 are indivisible. Analogy to a paper is not a derivation. For an RC ramp near Tian, preserve the Tian event-sensitivity skeleton but recompute `vramp(t)`, `Fdot_0`, `delta_t`, and every affected DF path.

## Mandatory report sections

Use these headings: Model classification; Assumptions and unsupported effects; State variables and switching states; Steady-state trajectory; Switching event equation; Edge perturbation; Describing-function relation; Mapping to a_c/a_g/a_o/a_i; Buck power-stage coupling; Transfer function; Sanity checks; Validation status; What is paper-derived vs newly derived.

Run `python scripts/df_protocol_checker.py check --report derivation.md`. A passing protocol proves completeness and claim discipline, not physical correctness.
