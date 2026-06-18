# Validation status

| Level | Allowed meaning |
|---|---|
| `PAPER_GROUNDED_VERIFIED` | Registered paper equations, reproduced benchmark, and independent switching/measurement evidence |
| `PAPER_GROUNDED_PARTIAL` | Paper formulas are bundled and key values/trends reproduced, but original switching data are unavailable |
| `PROTOCOL_DERIVED_UNVERIFIED` | Event equation and edge perturbation exist, but no paper or switching validation proves the new model |
| `CUSTOM_COEFFICIENT_UNVERIFIED` | User supplied `a_*`; the skill verifies only downstream algebra |
| `REJECTED_UNSUPPORTED` | The requested operating behavior is outside scope |

New protocol cases must also show `UNVERIFIED_NEW_DF_MODEL`. Do not say “correct”, “verified”, or “consistent with the paper” for a new derivation unless the named evidence exists. Say instead: “This is a candidate small-signal model derived by the DF protocol; symbolic/DC checks passed, while switching validation remains missing.”

Use provenance tags `paper-equation`, `paper-low-order`, `derived-adapter`, `paper-inspired-new-derivation`, `model-invented`, and `user-supplied` at component level.
