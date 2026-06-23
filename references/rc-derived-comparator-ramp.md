# RC-derived comparator ramp policy

Switch-node RC, sense-filter, and RC-derived comparator ramps are state variables with inter-cycle memory. Local crossing slope alone is insufficient to define `Kmod`.

Required metadata for an RC-derived comparator ramp:

- `comparator_input_origin = switch_node_rc` or `sense_filter`, or `comparator_ramp_model.type = rc_derived_state`;
- `R`, `C`, and `tau = R*C`;
- `p = exp(-Ts/tau)` or enough `Ts` and `tau` metadata to compute it;
- explicit `memory_treatment`;
- validation level `PROTOCOL_DERIVED_UNVERIFIED` unless a future registry entry exists.

The checker rejects slope-only forms such as:

```text
((1 - exp(-s*Ton)) / (1 - exp(-s*Ts))) * (1 / (Ts * abs(Sfall)))
```

or any equivalent `Kmod proportional to 1/(Ts*local_slope)` when the comparator ramp is an RC-derived state.

An unverified memory-aware form may be recorded as protocol-derived evidence:

```text
p = exp(-Tsw/tau)
Kmod_z = D * (1 - p*z^-1) / (sf*Tsw)
Kmod_s_memory = D * (1 - p*exp(-s*Tsw)) / (sf*Tsw)
```

If a Li/Lee-style `H_on(s)` pair is borrowed for an RC-sensing topology, it must be marked `borrowed_approximation`, not registered for this topology, not paper-grounded, and not figure reproduced.
