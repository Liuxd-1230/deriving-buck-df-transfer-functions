# ESSF sampled-data derivation: yan_2022_part_ii_ccot_buck_zero_ramp

> This Markdown is a rendering of hash-linked proof and derivation artifacts; it is not evidence by itself.

## Registered reasoning chain

The chain enforces sampling event → left/right limits → Dirichlet sampled value → Fm → pulse/sideband modulator → power-stage coupling → loop/closed-loop target.

## 12-step Yan sampled-data reasoning

### Independent derivation path

- 1. identify control family and requested target
- 2. declare sampling event and sampled variable
- 3. write left and right limits
- 4. apply Dirichlet sampled value
- 5. derive or bind zero-ramp Fm from the sampled value
- 6. construct pulse train relation
- 7. construct pulse factor in the s-domain
- 8. attach sideband summation policy
- 9. build GPWM/Gm sampled modulator
- 10. bind Buck ESR power stage Gid/Gvd
- 11. form return ratio Ti/Tv and Tloop
- 12. close the loop for Tc or Gvc and verify against registry

### Registry formula path

- `yan-2022-part-ii.ccot-dirichlet-value`
- `yan-2022-part-ii.ccot-fm-zero-ramp`
- `yan-2022-part-ii.ccot-pulse-relation`
- `yan-2022-part-ii.ccot-pulse-factor`
- `yan-2022-part-ii.ccot-sideband-value`
- `yan-2022-part-ii.ccot-gpwm`
- `yan-2022-part-ii.ccot-gid-buck`
- `yan-2022-part-ii.ccot-ti`
- `yan-2022-part-ii.ccot-tloop`
- `yan-2022-part-ii.ccot-tc`
- `yan-2022-part-ii.ccot-gvc`

Dual-path check: independent step composition must match registry-bound expanded_target_expression.

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
- Expression: `$Vin*(C*s+1/R)/(L*C*s**2+(L/R+rC*C)*s+1)$`
- Provenance: Yan-2022-Part-II-Eq9
- Approximation: `paper-esr-power-stage`
- Dimension: `current/duty`

### 8. Ti

- `formula_id`: `yan-2022-part-ii.ccot-ti`
- Expression: `$Hi*Gid*GPWM$`
- Provenance: current-loop-block-composition
- Approximation: `exact-block-composition`
- Dimension: `return-ratio`

### 9. Tloop

- `formula_id`: `yan-2022-part-ii.ccot-tloop`
- Expression: `$Ti$`
- Provenance: loop-break-return-ratio-identification
- Approximation: `exact-block-composition`
- Dimension: `return-ratio`

### 10. Tc

- `formula_id`: `yan-2022-part-ii.ccot-tc`
- Expression: `$Ti/(1+Ti)$`
- Provenance: negative-feedback-closure
- Approximation: `exact-feedback-identity`
- Dimension: `closed-loop`

### 11. Gvc

- `formula_id`: `yan-2022-part-ii.ccot-gvc`
- Expression: `$Gid*GPWM/(1+Ti)$`
- Provenance: closed-loop-control-to-output-composition
- Approximation: `exact-feedback-identity`
- Dimension: `output/control`

## Requested result

- Target: `Tloop`
- Response kind: `return_ratio`
- Selected return ratio: `Ti`
- Target mapping: `Tloop=Ti`
- Registered relation: `$Ti$`
- Expanded engineering expression: `$-2*Hi*Vin*(C*R*s + 1)*(exp(T0*s) - 1)*exp(-T0*s)/((-2*H*SidebandPulse + Ts*m1 - Ts*m2)*(C*L*R*s**2 + C*R*rC*s + L*s + R))$`

## Approximation and validity

Approximation set: `exact-block-composition, exact-delay-relation, exact-feedback-identity, exact-sampling-definition, exact-two-pulse-factor, paper-esr-power-stage, registered-sideband-form, symbolic-full-sum, zero-ramp-only`.
Sideband policy: `{"M": 10, "approximation": "truncated nonzero sideband sum M=10", "include_zero": false, "indices": [-10, -9, -8, -7, -6, -5, -4, -3, -2, -1, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10], "mode": "TRUNCATED_SUM_M", "numeric_approximation": "((1 - exp(T0*(10*j*ws - s)))*G(-10*j*ws + s)) + ((1 - exp(T0*(9*j*ws - s)))*G(-9*j*ws + s)) + ((1 - exp(T0*(8*j*ws - s)))*G(-8*j*ws + s)) + ((1 - exp(T0*(7*j*ws - s)))*G(-7*j*ws + s)) + ((1 - exp(T0*(6*j*ws - s)))*G(-6*j*ws + s)) + ((1 - exp(T0*(5*j*ws - s)))*G(-5*j*ws + s)) + ((1 - exp(T0*(4*j*ws - s)))*G(-4*j*ws + s)) + ((1 - exp(T0*(3*j*ws - s)))*G(-3*j*ws + s)) + ((1 - exp(T0*(2*j*ws - s)))*G(-2*j*ws + s)) + ((1 - exp(T0*(j*ws - s)))*G(-j*ws + s)) + ((1 - exp(T0*(-j*ws - s)))*G(j*ws + s)) + ((1 - exp(T0*(-2*j*ws - s)))*G(2*j*ws + s)) + ((1 - exp(T0*(-3*j*ws - s)))*G(3*j*ws + s)) + ((1 - exp(T0*(-4*j*ws - s)))*G(4*j*ws + s)) + ((1 - exp(T0*(-5*j*ws - s)))*G(5*j*ws + s)) + ((1 - exp(T0*(-6*j*ws - s)))*G(6*j*ws + s)) + ((1 - exp(T0*(-7*j*ws - s)))*G(7*j*ws + s)) + ((1 - exp(T0*(-8*j*ws - s)))*G(8*j*ws + s)) + ((1 - exp(T0*(-9*j*ws - s)))*G(9*j*ws + s)) + ((1 - exp(T0*(-10*j*ws - s)))*G(10*j*ws + s))"}`.
Validity statement: limited by sampled-data paper contract and benchmark metadata.

Validation level: `SAMPLED_DATA_REGISTERED_PARTIAL`.
