# Buck physical-first and DF skill validation

## v0.5 validation passport

- Validation date: 2026-07-15
- Scope: confirmed Circuit IR, component-stamped Hybrid MNA/DAE, periodic orbit, saltation/Poincaré linearization, independent switching finite differences, continuous baseband/sidebands, sensitivities, registry cross-check, and paper-style report
- Physical authority: confirmed Circuit IR + confirmed Physics Spec + event-to-event Poincaré model
- External simulator policy: the skill does not launch SIMPLIS

| v0.5 check | Status | Evidence |
|---|---|---|
| Image/Circuit IR trust boundary | VERIFIED_STATIC | SHA-256/dimensions, stable IDs, terminals, orientations, SI dimensions, ambiguity gate, deterministic SVG/raster checkout, and two confirmations |
| Schematic forward-test set | REVIEWED_STATIC | V², current-mode, external-ramp, ESR-ripple RBCOT, synchronous QH/QL, and an ambiguous crossing were visually checked; the finite set does not claim arbitrary-image recognition accuracy |
| R/L/C, sources, controlled sources, switches/diodes, ramp, timer, LTI stamps | VERIFIED | unit tests exercise descriptor stamps and exact switch constraints |
| Index-1 descriptor reduction | VERIFIED | every golden mode retains descriptor/algebraic matrices and reconstructs full variables |
| Periodic orbit | VERIFIED_NUMERIC | four golden families solve by exact affine flow + guard root + shooting |
| KCL/KVL and fixed-point residuals | VERIFIED_NUMERIC | golden residuals remain below `1e-7` |
| Volt-second, charge, and power/energy balance | VERIFIED_NUMERIC | component-port reconstruction and independent quadrature remain below `1e-7` |
| CCM gate | VERIFIED_NUMERIC | all four goldens retain positive minimum inductor current; negative boundary remains blocking/overridable only after solve |
| Saltation and Poincaré semantics | VERIFIED | artifacts preserve both `Xi/Xi_u` and event-endpoint `Pi/Pi_u` instead of conflating them |
| Independent Poincaré Jacobian | VERIFIED_NUMERIC | `solve_ivp(DOP853)` central finite differences do not reuse affine flow/guard root; golden relative errors are about `1e-9`, below `1e-3` |
| z-domain and continuous baseband | VERIFIED_NUMERIC | section response uses `z=exp(jωT)`; analog baseband is independently lifted through piecewise variational flow |
| Sideband convergence | VERIFIED_NUMERIC | `M=3,6,12,24,48,64`; all declared golden probes satisfy `0.1 dB/1°` |
| Parameter sensitivity | VERIFIED_NUMERIC | each nonzero L/C/load/ESR/gain/ramp/timing parameter rebuilds MNA, orbit, and event linearization at both perturbations |
| Floquet interpretation | VERIFIED_STATIC | participation, residues, physical energy-state amplitude, sensitivities, and evidence-limited zero attribution are emitted |
| Four registry goldens | CROSSCHECKED | V² and current-mode use absolute transfer; external-ramp and RBCOT use explicitly labeled normalized trend; each declared band is within `3 dB/15°` |
| Registry authority boundary | VERIFIED_STATIC | registry never replaces `Ad/Bd` and never upgrades validation |
| Override/regularization policy | VERIFIED_STATIC | only named post-solve checks may be overridden; gmin/rmin and grazing secant candidates remain permanently unverified |
| V² schematic-to-report golden | VERIFIED_NUMERIC | real SVG → checkout → two confirmations → MNA/orbit/Poincaré → Gvc/baseband/sidebands → report |

The v0.5 tests are deterministic software/numerical evidence, not laboratory measurement. `PHYSICS_DERIVED_EXTERNAL_CROSSCHECKED` requires a user-supplied independent switching simulation or measurement dataset with complete metadata.

Regression result: all 255 retained v0.4.5 tests plus 40 v0.5 tests pass (`295` total across `tests/` and `scripts/`).

## v0.4.2 retained material passport

## Material passport

- Artifact: `deriving-buck-df-transfer-functions`
- Validation date: 2026-06-19
- Scope: ESSF intake/proof gate, retained single-phase CCM COT/RBCOT DF models, Yan 2022 sampled-data registered path minimal closure, and dual-index formula audit guardrails
- Overall status: `PARTIALLY_VERIFIED`
- Offline use: no Zotero library or paper PDF is required at runtime

## Claim matrix

| Check | Status | Evidence |
|---|---|---|
| Generic Buck matrix algebra | VERIFIED | Symbolic plant identities and adapter-substitution tests |
| Four registered v0.2 paper models | PARTIALLY_VERIFIED | Formula/key-value benchmarks remain bundled; no original raw switching vectors |
| Intake hard gate | VERIFIED | Text/JSON tests enforce `INCOMPLETE -> ASK_USER_ONLY`; registered model IDs cannot bypass preflight |
| Runtime schemas and provenance | VERIFIED_STATIC | Draft 2020-12 validation plus canonical JSON SHA-256 links enforce every transition through `FORMULA_BINDING → DERIVATION → CHECKERS → REPORT` |
| Model classification | VERIFIED | Paths are `DF_REGISTERED_DIRECT`, `DF_REGISTERED_MULTIPORT`, `PROTOCOL_DERIVED_NEW`, `INCOMPLETE`, and `UNSUPPORTED` |
| Dual-index model selection | VERIFIED_STATIC | Registered models expose `control_ontology` and `source_index`; classifier binds current-mode, V2 COT, RBCOT, sampled-data, and external-ramp paths by mechanism before source claims |
| Formula registry | VERIFIED | Four registered generators load canonical formulas from `formula_registry.yaml`; Q2 and bound-expression mutation tests fail as required |
| Yan 2022 sampled-data registry | PARTIALLY_VERIFIED | Part I/II registered paths generate `GPWM → Gid/Gvd → Ti/Tv → Tc`; scope remains single-phase zero-ramp and does not imply arbitrary sampled-data support |
| Sampled-data derivation checker | VERIFIED_STATIC | Every derivation step, target closure, approximation, order and predecessor hash is recomputed from paper/formula registries |
| Proof object checker | VERIFIED | Direct fake `a_*`, unsupported target, incomplete intake, bad validation and formula mismatches are rejected |
| Sampled-data proof contract | VERIFIED_STATIC | Checker requires sampling limits, Dirichlet value, Fm reference, sideband mode, modulator_io, target_mapping and registry formula bindings |
| Dirichlet checker | VERIFIED_STATIC | `Fm.origin=sampled_data_derivation` without a Dirichlet reference returns `FAIL_FM_WITHOUT_DIRICHLET_REFERENCE` |
| COT/COFT pulse structure | VERIFIED_STATIC | Part II proofs missing `d1/d2/d2(t)=-d1(t-T0)/1-exp(-s*T0)` return `FAIL_COT_TWO_PULSE_TRAINS` |
| Zero-ramp Fm hard rejection | VERIFIED_STATIC | external/internal ramp, delay, RC injection and sense-filter cases reject with explicit v0.4/v0.5 boundary codes |
| Sampled-data target mapping | VERIFIED_STATIC | Yan v0.4 registers `Gm/GPWM/Ti/Tv/Tc`; `Gvc/Tloop/Gvg/Zout` are not claimed as Yan 2022 benchmark targets and are rejected or left unverified unless separately registered |
| Sideband numeric evaluator | VERIFIED_STATIC | `plot-bode` supports `exp(-s*T)`, `TRUNCATED_SUM_M`, and `PAPER_SIMPLIFIED_FORM`; `SYMBOLIC_FULL_SUM` is rejected for numeric plots |
| Sideband substitution | VERIFIED_STATIC | SymPy `subs(n,Integer(k))` preserves identifiers; default truncation is `[-M,-1]∪[1,M]` with explicit positive integer `M` |
| Stability-margin semantics | VERIFIED_STATIC | PM/GM are computed only for `Ti/Tv/Tloop` return ratios; other responses return `NOT_APPLICABLE_NON_RETURN_RATIO` |
| V-COT time-constant trend | VERIFIED_STATIC | Benchmark guards Yan Part II boundary `rC*C > T0/2`; increasing `rC` or `C` improves margin, increasing `Ton/T0` reduces it |
| Forward-test | VERIFIED_STATIC | “做一个谷值电压模 COT” returns missing questions only and creates no proof, transfer, or plot |
| Engineering forward-test | VERIFIED_STATIC | Valley current-mode COT case requires `loop_break` for `Tloop`, preserves SIMPLIS Laplace semantics, and plots `Gvc/Tloop` with `fs/2` validity markers |
| Bode plotting | VERIFIED_STATIC | `plot-bode` emits PNG, CSV, and JSON summary for DF `Gvc/Gvg/Zout/Tloop` and sampled-data `Gm/GPWM/Ti/Tv/Tc`; out-of-range crossings are marked |
| Compensator templates | VERIFIED_STATIC | `SIMPLIS_LAPLACE`, `OTA_GM_RO`, `PI`, `TYPE_II`, `TYPE_III`, and `CUSTOM_EXPRESSION` produce canonical expressions; Type II/III require rad/s units |
| Legacy CLI compatibility | VERIFIED_STATIC | `derive --case` renders `LEGACY_CASE_UNVERIFIED`; `check --case` remains JSON algebra diagnostics |
| `bind_expression` parentheses | VERIFIED | Binder no longer adds hidden parentheses; registry templates carry required grouping explicitly; formula consistency and benchmarks pass |
| Li/Lee 2010 full `Gvc` figure reproduction | NOT_VERIFIED | Current benchmark verifies Eq. (9)-(10) `Fc` subformulas only; Eq. (16) `Gvc`, `Ri sweep`, and external-ramp sweep remain an explicit audit target |
| New RC-ramp coefficient formulas | NOT_VERIFIED | The example records required derivation evidence but intentionally contains no claimed closed-form coefficients |
| Switching simulation | NOT_VERIFIED | No SIMPLIS/switching AC sweep validates a protocol-derived new model in v0.3.1 |
| Independent agent forward-test | NOT_VERIFIED | The new prompt test is deterministic CLI evidence, not an isolated-agent behavioral run |
| Multiphase overlap/nonoverlap | PLANNED_V05 | Classifier emits distinct `MULTIPHASE_OVERLAP` / `MULTIPHASE_NONOVERLAP` paths and rejection codes; neither can enter a single-phase proof |
| DCM, skipping/burst | REJECTED_UNSUPPORTED | Classifier and checker reject these paths; no applicability claim |
| Average model represented as DF | `EXCLUDED_NON_DF` / REJECTED_UNSUPPORTED | Huang 2025 remains excluded; failure fixture returns `FAIL_FALSE_DF` |

## Paper-model evidence retained from v0.2

- Li/Lee 2010: Eqs. (9)–(10) and current-source adapter checks; exact-vs-Padé error below `0.49fs` about `0.0145 dB / 0.0149 deg`. This is `SUBFORMULA_VERIFIED` / partial chain evidence, not full Eq. (16) `Gvc` figure reproduction.
- Tian: Eqs. (4), (6)–(8), (13); benchmark `fp=31.831 kHz`, `fz=95.493 kHz`; exact-vs-low-order error below `0.49fs` about `1.482 dB / 10.77 deg`.
- Li/Lee 2009: bundled cases reproduce `rC*C > Ton/2` for OSCON/ceramic examples.
- Lu 2023: corrected Eq. (8) sign and Eq. (11) loop structure; an assumed `R=0.12 ohm` remains documented because the source caption omits it.

## Yan 2022 sampled-data v0.4 evidence

- Part I: Dirichlet sampling contract and zero-ramp sampled `Fm` proof fragment are registered. Runtime artifacts do not require the PDF.
- Part II C-COT/C-COFT: proof object requires two pulse trains and `1-exp(-s*T0)`; benchmark uses unified `plot-bode`.
- Part II V-COT/V-COFT: proof object separates `GPWM/Tv/Tc`; `Gvc/Tloop` are not v0.4 Yan registered benchmark targets. The trend benchmark protects `rC*C > T0/2`.
- Sideband policy: registry stores symbolic/paper skeletons; numeric Bode must declare `TRUNCATED_SUM_M` or `PAPER_SIMPLIFIED_FORM`.
- Power-stage coupling: current contracts use `Gid/Hi/Ti`; voltage contracts use `Gvd/Hv/Tv`; `Tc` is generated only as `Ti/(1+Ti)` or `Tv/(1+Tv)`.
- Margin policy: only `Ti/Tv/Tloop` are return ratios. `Gm/GPWM/Gvc/Gvg/Zout/Tc` report `NOT_APPLICABLE_NON_RETURN_RATIO` for PM/GM.

## v0.4.2 formula audit evidence policy

Practice is the final arbiter: symbolic consistency, registry binding, and a visually plausible Bode plot are not enough by themselves. Evidence levels are:

- `SUBFORMULA_VERIFIED`: a paper subformula and numeric probes match.
- `CHAIN_VERIFIED`: the registered formula chain composes into the intended target.
- `FIGURE_REPRODUCED`: a named paper figure or key trend is reproduced with parameters and error/trend notes.
- `SIMULATION_OR_MEASUREMENT_REPRODUCED`: switching simulation or measurement independently supports the model.

The Yanna/Zotero collection and local PDFs are development sources for audit; runtime artifacts remain self-contained and do not bundle PDFs.

## v0.4 not covered

- 2026 external-ramp C-COT dynamic `Fm(s)`;
- internal ramp;
- comparator delay;
- RC injection;
- sense filter;
- multiphase nonoverlap;
- multiphase overlap;
- DCM or boundary conduction;
- pulse skipping/burst;
- nonlinear current limit;
- hardware or switching-simulation verification for new protocol-derived models.

## Reproduction

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:MPLBACKEND='Agg'
python -m unittest discover -s scripts -p 'test_*.py' -v
python -m unittest discover -s tests -p 'test_*.py' -v
python scripts/run_benchmarks.py --all
python scripts/check_formula_consistency.py --all
python scripts/check_proof_object.py --proof tests/fixtures/valid_li_lee_2009_direct.json
pytest tests/test_forward_prompts.py tests/test_formula_consistency.py tests/test_direct_model_no_fake_a_star.py tests/test_cot_requires_two_pulse_trains.py tests/test_external_ramp_requires_fm_s.py tests/test_compensator_templates.py tests/test_tloop_loop_break.py tests/test_plot_bode.py tests/test_bind_expression_parentheses.py
pytest tests/test_sampled_data_dirichlet.py tests/test_fm_models_zero_ramp_only.py tests/test_sideband_sum.py tests/test_sampled_data_target_mapping.py tests/test_sampled_data_registered_models.py tests/test_sampled_data_benchmark_trends.py tests/test_plot_bode_sideband.py
```

The first two suites test retained v0.2 algebra/benchmarks and v0.3.1 ESSF contracts separately. The two checker commands must return `PASS`.

## Interpretation

The proof/formula checkers validate artifact completeness, registered interfaces, formula origin, symbolic equivalence, dimension signatures, and numeric probes. They cannot prove that a newly chosen event is physically correct. `PAPER_GROUNDED_PARTIAL` retains the prior paper evidence level. Every new model remains `PROTOCOL_DERIVED_UNVERIFIED` / `UNVERIFIED_NEW_DF_MODEL` until independent evidence is supplied.

## Version verdict

`v0.4.2 = paper-grounded single-phase COT/RBCOT DF library + mandatory intake/formula-registry/proof-object gate + Yan 2022 sampled-data registered path minimal closure + dual-index formula audit guardrails`. It still does not implement dynamic `Fm(s)`, nonideal ramp/filter/delay paths, multiphase sampled-data, or arbitrary protocol-derived model verification.
