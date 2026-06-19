# Buck DF Skill v0.4.1 Validation

## Material passport

- Artifact: `deriving-buck-df-transfer-functions`
- Validation date: 2026-06-19
- Scope: ESSF intake/proof gate, retained single-phase CCM COT/RBCOT DF models, and Yan 2022 sampled-data registered path minimal closure
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
| New RC-ramp coefficient formulas | NOT_VERIFIED | The example records required derivation evidence but intentionally contains no claimed closed-form coefficients |
| Switching simulation | NOT_VERIFIED | No SIMPLIS/switching AC sweep validates a protocol-derived new model in v0.3.1 |
| Independent agent forward-test | NOT_VERIFIED | The new prompt test is deterministic CLI evidence, not an isolated-agent behavioral run |
| Multiphase overlap/nonoverlap | PLANNED_V05 | Classifier emits distinct `MULTIPHASE_OVERLAP` / `MULTIPHASE_NONOVERLAP` paths and rejection codes; neither can enter a single-phase proof |
| DCM, skipping/burst | REJECTED_UNSUPPORTED | Classifier and checker reject these paths; no applicability claim |
| Average model represented as DF | `EXCLUDED_NON_DF` / REJECTED_UNSUPPORTED | Huang 2025 remains excluded; failure fixture returns `FAIL_FALSE_DF` |

## Paper-model evidence retained from v0.2

- Li/Lee 2010: Eqs. (9)–(10) and current-source adapter checks; exact-vs-Padé error below `0.49fs` about `0.0145 dB / 0.0149 deg`.
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

`v0.4 = paper-grounded single-phase COT/RBCOT DF library + mandatory intake/formula-registry/proof-object gate + Yan 2022 sampled-data registered path minimal closure`. It still does not implement dynamic `Fm(s)`, nonideal ramp/filter/delay paths, multiphase sampled-data, or arbitrary protocol-derived model verification.
