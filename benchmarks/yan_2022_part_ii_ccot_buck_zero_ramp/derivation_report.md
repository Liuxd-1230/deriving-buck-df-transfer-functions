# ESSF sampled-data derivation: yan_2022_part_ii_ccot_buck_zero_ramp

> This Markdown is a rendering of hash-linked proof and derivation artifacts; it is not evidence by itself.

## Registered reasoning chain

The chain enforces sampling event → left/right limits → Dirichlet sampled value → Fm → pulse/sideband modulator → power-stage coupling → loop/closed-loop target.

### 1. sampling

- `formula_id`: `yan-2022-part-ii.ccot-dirichlet-value`
- Expression: `$(x_left+x_right)/2$`
- Provenance: Yan-2022-Part-II-Dirichlet-condition
- Approximation: `exact-sampling-definition`
- Dimension: `sampled-variable`

### 2. Fm

- `formula_id`: `yan-2022-part-ii.ccot-fm-zero-ramp`
- Expression: `$1/((m2-m1)*Ts/2)$`
- Provenance: Yan-2022-Part-II-zero-ramp-Fm
- Approximation: `zero-ramp-only`
- Dimension: `1/slope_time`

### 3. pulse_relation

- `formula_id`: `yan-2022-part-ii.ccot-pulse-relation`
- Expression: `$-exp(-s*T0)$`
- Provenance: Yan-2022-Part-II-d2-delayed-inverse-d1
- Approximation: `exact-delay-relation`
- Dimension: `D2/D1`

### 4. pulse_factor

- `formula_id`: `yan-2022-part-ii.ccot-pulse-factor`
- Expression: `$1-exp(-s*T0)$`
- Provenance: Yan-2022-Part-II-d1-plus-d2
- Approximation: `exact-two-pulse-factor`
- Dimension: `dimensionless`

### 5. sideband

- `formula_id`: `yan-2022-part-ii.ccot-sideband-value`
- Expression: `$SidebandPulse$`
- Provenance: Yan-2022-Part-II-nonzero-sideband-sum-with-pulse-factor
- Approximation: `symbolic-full-sum`
- Dimension: `pulse-weighted-sideband-sum`

### 6. GPWM

- `formula_id`: `yan-2022-part-ii.ccot-gpwm`
- Expression: `$Fm*PulseFactor/(1+Fm*H*SidebandPulse)$`
- Provenance: Yan-2022-Part-II-sampled-modulator
- Approximation: `registered-sideband-form`
- Dimension: `duty/input`

### 7. Gid

- `formula_id`: `yan-2022-part-ii.ccot-gid-buck`
- Expression: `$Vin*(C*s+1/R)/(L*C*s**2+(L/R)*s+1)$`
- Provenance: CCM-Buck-linearized-state-equations
- Approximation: `ideal-ESR-power-stage`
- Dimension: `current/duty`

### 8. Ti

- `formula_id`: `yan-2022-part-ii.ccot-ti`
- Expression: `$Hi*Gid*GPWM$`
- Provenance: current-loop-block-composition
- Approximation: `exact-block-composition`
- Dimension: `return-ratio`

### 9. Tc

- `formula_id`: `yan-2022-part-ii.ccot-tc`
- Expression: `$Ti/(1+Ti)$`
- Provenance: negative-feedback-closure
- Approximation: `exact-feedback-identity`
- Dimension: `closed-loop`

## Requested result

- Target: `Tc`
- Registered relation: `$Ti/(1+Ti)$`
- Expanded engineering expression: `$-2*Hi*Vin*(C*R*s + 1)*(exp(T0*s) - 1)/(-2*C*H*L*R*SidebandPulse*s**2*exp(T0*s) - 2*C*Hi*R*Vin*s*exp(T0*s) + 2*C*Hi*R*Vin*s + C*L*R*Ts*m1*s**2*exp(T0*s) - C*L*R*Ts*m2*s**2*exp(T0*s) - 2*H*L*SidebandPulse*s*exp(T0*s) - 2*H*R*SidebandPulse*exp(T0*s) - 2*Hi*Vin*exp(T0*s) + 2*Hi*Vin + L*Ts*m1*s*exp(T0*s) - L*Ts*m2*s*exp(T0*s) + R*Ts*m1*exp(T0*s) - R*Ts*m2*exp(T0*s))$`

## Approximation and validity

Approximation set: `exact-block-composition, exact-delay-relation, exact-feedback-identity, exact-sampling-definition, exact-two-pulse-factor, ideal-ESR-power-stage, registered-sideband-form, symbolic-full-sum, zero-ramp-only`.
Validity statement: limited by sampled-data paper contract and benchmark metadata.

Validation level: `SAMPLED_DATA_REGISTERED_PARTIAL`.
