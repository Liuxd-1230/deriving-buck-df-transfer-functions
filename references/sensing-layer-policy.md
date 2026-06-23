# Sensing layer policy

Missing sensing information and explicit custom sensing are different states.

For `workflow.intent == user-circuit-derivation`, missing `sensing_layer` is `INCOMPLETE_INTAKE` / `ASK_USER_ONLY`. The skill must not infer a default current-sense path, output-ripple path, comparator input, or paper model.

Explicit custom, measured, user-supplied, unknown, or unregistered sensing may proceed only as downgraded evidence:

- `NEAR_MODEL`
- `AUDIT_REQUIRED`
- `MODEL_ANALOGY_ONLY`
- `PROTOCOL_DERIVED_UNVERIFIED`

It must not be called paper-grounded, verified, figure reproduced, or registered unless the sensing path is explicitly registered and the model applicability contract passes.

Internal benchmarks and examples may proceed only when they declare a registered sensing layer or a registered model contract.
