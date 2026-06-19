# Compensator templates

Use `scripts/compensator_templates.py` when a case needs a compensator block. Do not ask the user to hand-write arbitrary `Gc(s)` unless the block is intentionally marked `CUSTOM_EXPRESSION_UNVERIFIED`.

Supported templates:

- `SIMPLIS_LAPLACE`: `KPZ*(s+F*wz1)/((s+F*wp1)*(s+F*wp2))`. This is the SIMPLIS `s + F*w` form, not the normalized `(1+s/w)` form. DC gain is `KPZ*wz1/(F*wp1*wp2)` when `F` is the frequency scale factor.
- `OTA_GM_RO`: `gm*Ro`, or `gm/(1/Ro+s*Cea)` only when `Cea` is explicitly provided.
- `PI`: `Kp*(s+wz)/s`.
- `TYPE_II`: `K*(1+s/wz1)/(s*(1+s/wp1))`; require `frequency_units="rad_per_s"`.
- `TYPE_III`: `K*(1+s/wz1)*(1+s/wz2)/(s*(1+s/wp1)*(1+s/wp2))`; require `frequency_units="rad_per_s"`.
- `CUSTOM_EXPRESSION`: allowed only with `CUSTOM_EXPRESSION_UNVERIFIED`.

Write the chosen template result into proof/case metadata as `formula_origin`.
