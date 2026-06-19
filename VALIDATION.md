# Buck DF Skill v0.3.1 Validation

## Material passport

- Artifact: `deriving-buck-df-transfer-functions`
- Validation date: 2026-06-19
- Scope: ESSF first-stage intake, registry, proof-object gate plus retained single-phase CCM COT/RBCOT models
- Overall status: `PARTIALLY_VERIFIED`
- Offline use: no Zotero library or paper PDF is required at runtime

## Claim matrix

| Check | Status | Evidence |
|---|---|---|
| Generic Buck matrix algebra | VERIFIED | Symbolic plant identities and adapter-substitution tests |
| Four registered v0.2 paper models | PARTIALLY_VERIFIED | Formula/key-value benchmarks remain bundled; no original raw switching vectors |
| Intake hard gate | VERIFIED | Text/JSON tests enforce `INCOMPLETE -> ASK_USER_ONLY`; registered model IDs cannot bypass preflight |
| Model classification | VERIFIED | Paths are `DF_REGISTERED_DIRECT`, `DF_REGISTERED_MULTIPORT`, `PROTOCOL_DERIVED_NEW`, `INCOMPLETE`, and `UNSUPPORTED` |
| Formula registry | VERIFIED | Four registered generators load canonical formulas from `formula_registry.yaml`; Q2 and bound-expression mutation tests fail as required |
| Proof object checker | VERIFIED | Direct fake `a_*`, unsupported target, incomplete intake, bad validation and formula mismatches are rejected |
| Forward-test | VERIFIED_STATIC | “做一个谷值电压模 COT” returns missing questions only and creates no proof, transfer, or plot |
| Engineering forward-test | VERIFIED_STATIC | Valley current-mode COT case requires `loop_break` for `Tloop`, preserves SIMPLIS Laplace semantics, and plots `Gvc/Tloop` with `fs/2` validity markers |
| Bode plotting | VERIFIED_STATIC | `plot-bode` emits PNG, CSV, and JSON summary for `Gvc/Gvg/Zout/Tloop`; out-of-range crossings are marked `EXTRAPOLATED_BEYOND_VALID_RANGE` |
| Compensator templates | VERIFIED_STATIC | `SIMPLIS_LAPLACE`, `OTA_GM_RO`, `PI`, `TYPE_II`, `TYPE_III`, and `CUSTOM_EXPRESSION` produce canonical expressions; Type II/III require rad/s units |
| Legacy CLI compatibility | VERIFIED_STATIC | `derive --case` renders `LEGACY_CASE_UNVERIFIED`; `check --case` remains JSON algebra diagnostics |
| `bind_expression` parentheses | VERIFIED | Binder no longer adds hidden parentheses; registry templates carry required grouping explicitly; formula consistency and benchmarks pass |
| New RC-ramp coefficient formulas | NOT_VERIFIED | The example records required derivation evidence but intentionally contains no claimed closed-form coefficients |
| Switching simulation | NOT_VERIFIED | No SIMPLIS/switching AC sweep validates a protocol-derived new model in v0.3.1 |
| Independent agent forward-test | NOT_VERIFIED | The new prompt test is deterministic CLI evidence, not an isolated-agent behavioral run |
| Multiphase overlap, DCM, skipping/burst | REJECTED_UNSUPPORTED | Classifier and checker reject these paths; no applicability claim |
| Average model represented as DF | `EXCLUDED_NON_DF` / REJECTED_UNSUPPORTED | Huang 2025 remains excluded; failure fixture returns `FAIL_FALSE_DF` |

## Paper-model evidence retained from v0.2

- Li/Lee 2010: Eqs. (9)–(10) and current-source adapter checks; exact-vs-Padé error below `0.49fs` about `0.0145 dB / 0.0149 deg`.
- Tian: Eqs. (4), (6)–(8), (13); benchmark `fp=31.831 kHz`, `fz=95.493 kHz`; exact-vs-low-order error below `0.49fs` about `1.482 dB / 10.77 deg`.
- Li/Lee 2009: bundled cases reproduce `rC*C > Ton/2` for OSCON/ceramic examples.
- Lu 2023: corrected Eq. (8) sign and Eq. (11) loop structure; an assumed `R=0.12 ohm` remains documented because the source caption omits it.

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
```

The first two suites test retained v0.2 algebra/benchmarks and v0.3.1 ESSF contracts separately. The two checker commands must return `PASS`.

## Interpretation

The proof/formula checkers validate artifact completeness, registered interfaces, formula origin, symbolic equivalence, dimension signatures, and numeric probes. They cannot prove that a newly chosen event is physically correct. `PAPER_GROUNDED_PARTIAL` retains the prior paper evidence level. Every new model remains `PROTOCOL_DERIVED_UNVERIFIED` / `UNVERIFIED_NEW_DF_MODEL` until independent evidence is supplied.

## Version verdict

`v0.3.1 = paper-grounded single-phase COT/RBCOT DF library + mandatory intake/formula-registry/proof-object gate`. It does not yet implement the sampled-data, sideband, Dirichlet, two-pulse-train, or dynamic-Fm work planned for v0.4/v0.5.
