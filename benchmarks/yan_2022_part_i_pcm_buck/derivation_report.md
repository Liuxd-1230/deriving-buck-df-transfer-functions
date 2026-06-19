# ESSF sampled-data derivation: yan_2022_part_i_pcm_buck

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
- 11. form return ratio Ti/Tv
- 12. close the loop for Tc or another explicitly registered target and verify against registry

### Registry formula path

- `yan-2022-part-i.dirichlet-value`
- `yan-2022-part-i.pcm-fm-zero-ramp`
- `yan-2022-part-i.sideband-value`
- `yan-2022-part-i.gpwm`
- `yan-2022-part-i.gid-buck`
- `yan-2022-part-i.ti`
- `yan-2022-part-i.tc-current`

Dual-path check: independent step composition must match registry-bound expanded_target_expression.

### 1. sampling

- `formula_id`: `yan-2022-part-i.dirichlet-value`
- Expression: `$(x_left+x_right)/2$`
- Provenance: Yan-2022-Part-I-Dirichlet-condition
- Approximation: `exact-sampling-definition`
- Dimension: `sampled-variable`

### 2. Fm

- `formula_id`: `yan-2022-part-i.pcm-fm-zero-ramp`
- Expression: `$1/(((m1-m2)/2+mc)*Ts)$`
- Provenance: Yan-2022-Part-I-Eq5
- Approximation: `zero-ramp-mc-retained`
- Dimension: `1/slope_time`

### 3. sideband

- `formula_id`: `yan-2022-part-i.sideband-value`
- Expression: `$SumG$`
- Provenance: Yan-2022-Part-I-sideband-sum-nonzero-indices
- Approximation: `symbolic-full-sum`
- Dimension: `plant-sideband-sum`

### 4. GPWM

- `formula_id`: `yan-2022-part-i.gpwm`
- Expression: `$Fm/(1+Fm*H*SumG)$`
- Provenance: Yan-2022-Part-I-sampled-modulator
- Approximation: `registered-sideband-form`
- Dimension: `duty/input`

### 5. Gid

- `formula_id`: `yan-2022-part-i.gid-buck`
- Expression: `$Vin*(C*s+1/R)/(L*C*s**2+(L/R+rC*C)*s+1)$`
- Provenance: Yan-2022-Part-II-Eq9; same buck Gid used by Part-I current loop
- Approximation: `paper-esr-power-stage`
- Dimension: `current/duty`

### 6. Ti

- `formula_id`: `yan-2022-part-i.ti`
- Expression: `$Hi*Gid*GPWM$`
- Provenance: current-loop-block-composition
- Approximation: `exact-block-composition`
- Dimension: `return-ratio`

### 7. Tc

- `formula_id`: `yan-2022-part-i.tc-current`
- Expression: `$Ti/(1+Ti)$`
- Provenance: negative-feedback-closure
- Approximation: `exact-feedback-identity`
- Dimension: `closed-loop`

## Requested result

- Target: `Tc`
- Response kind: `closed_loop`
- Selected return ratio: `Ti`
- Target mapping: `Tc=Ti/(1+Ti)`
- Registered relation: `$Ti/(1+Ti)$`
- Expanded engineering expression: `$2*Hi*Vin*(C*R*s + 1)/(2*C*H*L*R*SumG*s**2 + 2*C*H*R*SumG*rC*s + 2*C*Hi*R*Vin*s + C*L*R*Ts*m1*s**2 - C*L*R*Ts*m2*s**2 + 2*C*L*R*Ts*mc*s**2 + C*R*Ts*m1*rC*s - C*R*Ts*m2*rC*s + 2*C*R*Ts*mc*rC*s + 2*H*L*SumG*s + 2*H*R*SumG + 2*Hi*Vin + L*Ts*m1*s - L*Ts*m2*s + 2*L*Ts*mc*s + R*Ts*m1 - R*Ts*m2 + 2*R*Ts*mc)$`

## Approximation and validity

Approximation set: `exact-block-composition, exact-feedback-identity, exact-sampling-definition, paper-esr-power-stage, registered-sideband-form, symbolic-full-sum, zero-ramp-mc-retained`.
Sideband policy: `{"approximation": "paper simplified sampled-data form", "mode": "PAPER_SIMPLIFIED_FORM", "numeric_approximation": "Fm"}`.
Validity statement: limited by sampled-data paper contract and benchmark metadata.

Validation level: `SAMPLED_DATA_REGISTERED_PARTIAL`.
