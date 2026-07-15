# v0.5 continuous baseband and sideband protocol

## Lift the discrete state response

For a sampled input frequency `omega`, first solve the section state response from

$$
(e^{j\omega T}I-A_d)\hat x_0=B_d\hat u.
$$

Propagate that perturbation through each nominal mode with the piecewise variational equation and the event-to-event projection matrices. Evaluate the confirmed analog output expression throughout the cycle.

## Fourier projection

If `h(tau,omega)` is the within-cycle complex output envelope relative to the cycle input, compute sideband `k` as

$$
H_k(j\omega)=\frac{1}{T}\int_0^T h(\tau,\omega)
e^{-j(\omega+k\omega_s)\tau}\,d\tau.
$$

`H0` is the continuous baseband response used to compare an analog `Gvc/Gvg/Zout` with a paper or external Bode dataset. The rational z-domain section response remains available separately.

## Truncation rule

Start at `M=3`, then use `6,12,24,48,64`. Compare adjacent reconstructions. Mark a probe converged only when magnitude changes by at most `0.1 dB` and phase by at most `1 degree`. Mark the full result converged only when every declared probe converges. Never extend beyond `M=64` and pretend convergence.

Store each retained coefficient, its physical frequency `f+k*fs`, selected M, adjacent differences, and convergence status.

Do not use a sideband aggregate as the stability authority. Stability belongs to the event-to-event Poincaré model.
