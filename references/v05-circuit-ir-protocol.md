# v0.5 Circuit IR protocol

## Purpose

Convert image evidence into a confirmable electrical graph without letting image recognition become equation authority.

## Three artifacts

1. `IMAGE_INTAKE` binds filename, SHA-256, pixel dimensions, and case ID. It makes no topology claim.
2. `CIRCUIT_IR_PROPOSED` contains the multimodal proposal and unresolved ambiguities.
3. `TOPOLOGY_CONFIRMED` contains the user-confirmed graph and a hash of the confirmed content.

Never edit a confirmed artifact in place. A changed wire, polarity, value, or port requires a new proposal and confirmation.

## Required electrical evidence

For every component, preserve:

- stable component ID and supported type;
- named terminal-to-net mapping;
- voltage polarity and current reference direction;
- numeric value, unit, seven-base SI dimension vector, and value source;
- original-image normalized bounding box;
- confidence and a short recognition basis;
- parameters that affect mode/event semantics.

For every net, preserve a stable ID, aliases, and image evidence regions. For every port, preserve name, role, quantity, expression, and sign convention.

## Deterministic checks

Run all of the following before confirmation:

- unique component, net, and port IDs;
- declared ground and known terminal nets;
- required terminals and confirmed orientations;
- SI dimension match for R/L/C and independent sources;
- dangling-net and floating-subcircuit checks;
- comparator positive/negative terminal evidence;
- source/high-side path, switch node, low-side path, inductor, output capacitor/ESR path, and load recognition;
- source image hash/dimensions and deterministic numbered checkout overlay;
- no open blocking ambiguity.

Treat a crossing without a junction dot, hidden net label, unreadable value, ambiguous diode direction, uncertain comparator polarity, or unclear synchronous-switch meaning as blocking.

## Confirmation questions

Ask only about unresolved evidence. At minimum confirm:

1. Are all numbered components and net labels correct?
2. Are comparator `+/-`, diode polarity, and switch ON/OFF meanings correct?
3. Are voltage/current reference directions correct?
4. Are values and units read correctly?
5. Does the target input/output port mean what the user intends?

Do not infer missing values from a paper fixture or a typical design.
