# Registered model applicability contract

Registered model selection is a two-step decision:

1. classify the control ontology and source index;
2. prove the intake matches the registered model contract.

A model ID or similar control-family label is not sufficient. The classifier must check:

- `sensing_layer.type`, `input_variable`, `output_variable`, and `validation`;
- `comparator_inputs`;
- `sampled_variable`;
- fixed and movable interval semantics;
- requested target and target semantics;
- loop-break metadata for `Tloop`;
- nonidealities such as internal ramp, delay, RC injection, and sense filter.

If any required field mismatches the registry ontology, registered selection must fail or downgrade to `NEAR_MODEL`, `AUDIT_REQUIRED`, `PROTOCOL_DERIVED_UNVERIFIED`, or `UNSUPPORTED`. It must not enter `DF_REGISTERED_DIRECT`, `DF_REGISTERED_MULTIPORT`, `SAMPLED_DATA_REGISTERED`, or `PAPER_GROUNDED_PARTIAL`.

Examples:

- current-mode COT models require registered current sensing, not output ripple or switch-node RC sensing;
- V2 COT requires output-capacitor ripple sensing, not direct current sense;
- Yan 2022 zero-ramp sampled-data paths reject RC injection, sense filters, switch-node RC, and custom sensing networks;
- `Tloop` requires explicit loop-break semantics.
