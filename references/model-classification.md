# Model classification

Run classification before derivation:

```bash
python scripts/df_buck_sympy.py classify --intake circuit.json
```

| Path | Meaning | Action |
|---|---|---|
| `KNOWN_MODEL` | Exact registered v0.2 model, no declared modification | `use_known_model` |
| `NEAR_MODEL` | A registered event structure was modified | `derive_by_protocol` |
| `NEW_MODEL` | Complete, event-described single-phase CCM Buck with no match | `derive_by_protocol` |
| `INCOMPLETE` | Required event, comparator, target, mode, or parameters are missing | `ask_for_missing_info` |
| `UNSUPPORTED` | Model crosses an explicit boundary | `reject_unsupported` |

The output records topology, conduction mode, phase count, control family, matched model ID, confidence, action, missing information, unsupported effects, and validation level. Structured fields are authoritative. Free text may help identify a boundary but must never be used to invent an event equation.

Registered model IDs remain `cot-cm-li-lee-2010`, `cot-cm-external-ramp-tian-2015`, `v2-cot-li-lee-2009`, and `rbcot-esr-lu-2023`.
