# ESSF sampled-data derivation: yan_2022_part_i_pcm_buck

> This Markdown is a rendering of hash-linked proof and derivation artifacts; it is not evidence by itself.

## Registered reasoning chain

The chain enforces sampling event → left/right limits → Dirichlet sampled value → Fm → pulse/sideband modulator → power-stage coupling → loop/closed-loop target.

### 1. sampling

- `formula_id`: `yan-2022-part-i.dirichlet-value`
- Expression: `$(x_left+x_right)/2$`
- Provenance: Yan-2022-Part-I-Dirichlet-condition
- Approximation: `exact-sampling-definition`
- Dimension: `sampled-variable`

### 2. Fm

- `formula_id`: `yan-2022-part-i.pcm-fm-zero-ramp`
- Expression: `$1/((m2-m1)*Ts/2)$`
- Provenance: Yan-2022-Part-I-Fm-via-Dirichlet-sampled-value
- Approximation: `zero-ramp-proof-fragment`
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
- Expression: `$Vin*(C*s+1/R)/(L*C*s**2+(L/R)*s+1)$`
- Provenance: CCM-Buck-linearized-state-equations
- Approximation: `ideal-ESR-power-stage`
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
- Registered relation: `$Ti/(1+Ti)$`
- Expanded engineering expression: `$-2*Hi*Vin*(C*R*s + 1)/(-2*C*H*L*R*SumG*s**2 - 2*C*Hi*R*Vin*s + C*L*R*Ts*m1*s**2 - C*L*R*Ts*m2*s**2 - 2*H*L*SumG*s - 2*H*R*SumG - 2*Hi*Vin + L*Ts*m1*s - L*Ts*m2*s + R*Ts*m1 - R*Ts*m2)$`

## Approximation and validity

Approximation set: `exact-block-composition, exact-feedback-identity, exact-sampling-definition, ideal-ESR-power-stage, registered-sideband-form, symbolic-full-sum, zero-ramp-proof-fragment`.
Validity statement: limited by sampled-data paper contract and benchmark metadata.

Validation level: `SAMPLED_DATA_REGISTERED_PARTIAL`.
