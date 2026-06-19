# Model classification

Run classification before derivation:

```bash
python scripts/preflight_intake.py --intake circuit.json --out intake_status.json
python scripts/df_buck_sympy.py classify --intake-status intake_status.json --out classification.json
```

| Path | Meaning | Action |
|---|---|---|
| `DF_REGISTERED_DIRECT` | Registry provides only named direct transfer functions | bind direct formula; never invent `a_*` |
| `DF_REGISTERED_MULTIPORT` | Registry provides `a_*` or an explicit registered adapter | bind every coefficient to a formula ID |
| `PROTOCOL_DERIVED_NEW` | Complete new/modified event-described Buck | build unverified proof object |
| `INCOMPLETE` | Required event, comparator, target, mode, or parameters are missing | `ask_for_missing_info` |
| `UNSUPPORTED` | Model crosses an explicit boundary | `reject_unsupported` |

Classification accepts only a `COMPLETE` v0.3.1 intake artifact. The output records topology, mode, model ID, confidence, action, missing information, unsupported effects, and validation level. Structured fields are authoritative.

Registered model IDs remain `cot-cm-li-lee-2010`, `cot-cm-external-ramp-tian-2015`, `v2-cot-li-lee-2009`, and `rbcot-esr-lu-2023`.
