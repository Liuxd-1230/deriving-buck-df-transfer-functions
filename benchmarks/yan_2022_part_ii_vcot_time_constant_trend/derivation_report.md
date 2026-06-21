# ESSF sampled-data derivation: yan_2022_part_ii_vcot_time_constant_trend

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

- `yan-2022-part-ii.vcot-dirichlet-value`
- `yan-2022-part-ii.vcot-fm-zero-ramp`
- `yan-2022-part-ii.vcot-pulse-relation`
- `yan-2022-part-ii.vcot-pulse-factor`
- `yan-2022-part-ii.vcot-sideband-value`
- `yan-2022-part-ii.vcot-gpwm`
- `yan-2022-part-ii.vcot-gvd-buck`
- `yan-2022-part-ii.vcot-tv`
- `yan-2022-part-ii.vcot-tloop`
- `yan-2022-part-ii.vcot-tc`
- `yan-2022-part-ii.vcot-gvc`

Dual-path check: independent step composition must match registry-bound expanded_target_expression.

### 1. sampling

- `formula_id`: `yan-2022-part-ii.vcot-dirichlet-value`
- Expression: `$(x_left+x_right)/2$`
- Provenance: Yan-2022-Part-II-Dirichlet-condition
- Approximation: `exact-sampling-definition`
- Dimension: `sampled-variable`

### 2. Fm

- `formula_id`: `yan-2022-part-ii.vcot-fm-zero-ramp`
- Expression: `$1/(Hv*(rC*(m1-m2)/2+m1*D*Ts/(2*C))*Ts+mc*Ts)$`
- Provenance: Yan-2022-Part-II-Eq16 references Part-I PVM/VVM Fm
- Approximation: `paper-PVM-zero-ramp`
- Dimension: `1/slope_time`

### 3. pulse_relation

- `formula_id`: `yan-2022-part-ii.vcot-pulse-relation`
- Expression: `$-exp(-s*T0)$`
- Provenance: Yan-2022-Part-II-d2-delayed-inverse-d1
- Approximation: `exact-delay-relation`
- Dimension: `D2/D1`

### 4. pulse_factor

- `formula_id`: `yan-2022-part-ii.vcot-pulse-factor`
- Expression: `$1-exp(-s*T0)$`
- Provenance: Yan-2022-Part-II-d1-plus-d2
- Approximation: `exact-two-pulse-factor`
- Dimension: `dimensionless`

### 5. sideband

- `formula_id`: `yan-2022-part-ii.vcot-sideband-value`
- Expression: `$SidebandPulse$`
- Provenance: Yan-2022-Part-II-nonzero-sideband-sum-with-pulse-factor
- Approximation: `symbolic-full-sum`
- Dimension: `pulse-weighted-sideband-sum`

### 6. GPWM

- `formula_id`: `yan-2022-part-ii.vcot-gpwm`
- Expression: `$Fm*PulseFactor/(1+Fm*H*SidebandPulse)$`
- Provenance: Yan-2022-Part-II-sampled-modulator
- Approximation: `registered-sideband-form`
- Dimension: `duty/input`

### 7. Gvd

- `formula_id`: `yan-2022-part-ii.vcot-gvd-buck`
- Expression: `$Vin*(rC*C*s+1)/(L*C*s**2+(L/R+rC*C)*s+1)$`
- Provenance: Yan-2022-Part-II-Eq17
- Approximation: `paper-esr-power-stage`
- Dimension: `voltage/duty`

### 8. Tv

- `formula_id`: `yan-2022-part-ii.vcot-tv`
- Expression: `$Hv*Gvd*GPWM$`
- Provenance: voltage-loop-block-composition
- Approximation: `exact-block-composition`
- Dimension: `return-ratio`

### 9. Tloop

- `formula_id`: `yan-2022-part-ii.vcot-tloop`
- Expression: `$Tv$`
- Provenance: loop-break-return-ratio-identification
- Approximation: `exact-block-composition`
- Dimension: `return-ratio`

### 10. Tc

- `formula_id`: `yan-2022-part-ii.vcot-tc`
- Expression: `$Tv/(1+Tv)$`
- Provenance: negative-feedback-closure
- Approximation: `exact-feedback-identity`
- Dimension: `closed-loop`

### 11. Gvc

- `formula_id`: `yan-2022-part-ii.vcot-gvc`
- Expression: `$Gvd*GPWM/(1+Tv)$`
- Provenance: closed-loop-control-to-output-composition
- Approximation: `exact-feedback-identity`
- Dimension: `output/control`

## Requested result

- Target: `Tc`
- Response kind: `closed_loop`
- Selected return ratio: `Tv`
- Target mapping: `Tc=Tv/(1+Tv)`
- Registered relation: `$Tv/(1+Tv)$`
- Expanded engineering expression: `$2*C*Hv*R*Vin*(C*rC*s + 1)*(exp(T0*s) - 1)/(2*C**2*H*L*R*SidebandPulse*s**2*exp(T0*s) + 2*C**2*H*R*SidebandPulse*rC*s*exp(T0*s) + C**2*Hv*L*R*Ts*m1*rC*s**2*exp(T0*s) - C**2*Hv*L*R*Ts*m2*rC*s**2*exp(T0*s) + C**2*Hv*R*Ts*m1*rC**2*s*exp(T0*s) - C**2*Hv*R*Ts*m2*rC**2*s*exp(T0*s) + 2*C**2*Hv*R*Vin*rC*s*exp(T0*s) - 2*C**2*Hv*R*Vin*rC*s + 2*C**2*L*R*Ts*mc*s**2*exp(T0*s) + 2*C**2*R*Ts*mc*rC*s*exp(T0*s) + C*D*Hv*L*R*Ts**2*m1*s**2*exp(T0*s) + C*D*Hv*R*Ts**2*m1*rC*s*exp(T0*s) + 2*C*H*L*SidebandPulse*s*exp(T0*s) + 2*C*H*R*SidebandPulse*exp(T0*s) + C*Hv*L*Ts*m1*rC*s*exp(T0*s) - C*Hv*L*Ts*m2*rC*s*exp(T0*s) + C*Hv*R*Ts*m1*rC*exp(T0*s) - C*Hv*R*Ts*m2*rC*exp(T0*s) + 2*C*Hv*R*Vin*exp(T0*s) - 2*C*Hv*R*Vin + 2*C*L*Ts*mc*s*exp(T0*s) + 2*C*R*Ts*mc*exp(T0*s) + D*Hv*L*Ts**2*m1*s*exp(T0*s) + D*Hv*R*Ts**2*m1*exp(T0*s))$`

## Approximation and validity

Approximation set: `exact-block-composition, exact-delay-relation, exact-feedback-identity, exact-sampling-definition, exact-two-pulse-factor, paper-PVM-zero-ramp, paper-esr-power-stage, registered-sideband-form, symbolic-full-sum`.
Sideband policy: `{"approximation": "paper simplified sampled-data form", "mode": "PAPER_SIMPLIFIED_FORM", "numeric_approximation": "Fm*(1-exp(-s*Ton))"}`.
Validity statement: limited by sampled-data paper contract and benchmark metadata.

Validation level: `SAMPLED_DATA_REGISTERED_PARTIAL`.
