# Protocol case schema

A v0.3 case is an evidence record, not merely a coefficient container.

```json
{
  "case_version": "0.3",
  "mode": "derive-by-protocol",
  "target": "Gvc",
  "classification": {"path": "NEW_MODEL", "action": "derive_by_protocol"},
  "state_variables": ["iL", "vo"],
  "switching_state_equations": {"on": "...", "off": "..."},
  "steady_state_trajectory": "...",
  "power_stage": {"Vin": 12, "Vo": 1.2, "L": 3e-7, "C": 0.00047},
  "control_timing": {"fixed": "Ton", "variable": "Toff/Tsw"},
  "switching_events": [{
    "name": "off_edge",
    "fixed_or_movable": "movable",
    "equation": "F_off=Ri*iL+vramp-vc=0",
    "edge_slope": "Fdot_0=dF_off/dt",
    "delta_edge": "delta_t_off=-delta_F/Fdot_0"
  }],
  "perturbation_paths": {"uc_hat": "enters F_off"},
  "df_relation": {
    "form": "d_hat=a_c*uc_hat+a_i*iL_hat",
    "a_c": "A_c(s)", "a_i": "A_i(s)",
    "origin": "paper-inspired-new-derivation",
    "duty_caveat": "equivalent switching-function perturbation"
  },
  "validation_status": {
    "level": "PROTOCOL_DERIVED_UNVERIFIED",
    "claim": "UNVERIFIED_NEW_DF_MODEL",
    "completed": ["symbolic", "dc-limit"],
    "missing": ["paper-benchmark", "switching-simulation"]
  }
}
```

Allowed modes are `known-model`, `derive-by-protocol`, `custom-unverified-df`, and `unsupported`. User coefficients require top-level `df_source`, `event_equation`, and `valid_frequency`.
