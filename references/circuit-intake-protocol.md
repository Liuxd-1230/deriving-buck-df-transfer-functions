# Circuit intake protocol

`scripts/preflight_intake.py` is the mandatory gate. `INCOMPLETE` always means `ASK_USER_ONLY`; classification, proof construction, transfer-function generation, and plotting are forbidden.

## 5-question quick intake

Ask only what is needed for the selected path:

1. What target is required: `Gvc`, `Gvg`, `Zout`, `Tloop`, or an inner-current relation?
2. Is this single-phase CCM Buck, and which COT/RBCOT/V2/current-mode control family applies?
3. What turns each switch edge on or off, and which edge is fixed or movable?
4. What signals drive the positive and negative comparator inputs?
5. What are `Vin`, `Vo`, `fs` or `Ton`, `L`, `C`, `R`, `rC`, and any sensing/ramp/network parameters?

For a registered model, model ID + target + physical parameters is sufficient. For a near model, also state the difference. For a new model, an explicit comparator event is mandatory.

## AI internal intake checklist

Internally check ten areas without forcing the user to fill a long form: target; power stage; operating mode; control law; switching events; comparator inputs; feedback/ripple path; current-sense path; ramp/delay/sampling; perturbation entrances.

Ask only for missing facts. Never substitute “typical” comparator wiring. If the switching event or comparator path is absent, return classification and missing information only. Do not output a final transfer function.

## Structured intake conventions

Use `target`, `topology`, `conduction_mode`, `phases`, `control_family`, `switching_events`, `comparator_inputs`, and `parameters`. A movable event needs `equation`, `edge_slope`, and `delta_edge`. Use `similar_model` plus `modifications` for a near model.
