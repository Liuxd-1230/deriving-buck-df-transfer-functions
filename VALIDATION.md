# Buck DF Skill v0.3 Validation

## Material passport

- Artifact: `deriving-buck-df-transfer-functions`
- Validation date: 2026-06-18
- Scope: paper-grounded single-phase CCM COT/RBCOT models plus an event-based derivation protocol
- Overall status: `PARTIALLY_VERIFIED`
- Offline use: no Zotero library or paper PDF is required at runtime

## Claim matrix

| Check | Status | Evidence |
|---|---|---|
| Generic Buck matrix algebra | VERIFIED | Symbolic plant identities and adapter-substitution tests |
| Four registered v0.2 paper models | PARTIALLY_VERIFIED | Formula/key-value benchmarks remain bundled; no original raw switching vectors |
| Circuit intake classifier | VERIFIED | Unit and CLI tests cover `KNOWN_MODEL`, `NEAR_MODEL`, `NEW_MODEL`, `INCOMPLETE`, and `UNSUPPORTED` |
| Protocol case construction | VERIFIED | Tests require `F=0`, movable edge, `delta_t`, DF provenance, and unverified status |
| Protocol checker | VERIFIED | Fixtures produce all required pass/fail/warning classes, including false DF and false verification claims |
| Static forward scenarios | VERIFIED | Known Tian, missing event, RC-ramp near model, and multiphase-overlap examples execute through the CLI |
| New RC-ramp coefficient formulas | NOT_VERIFIED | The example records required derivation evidence but intentionally contains no claimed closed-form coefficients |
| Switching simulation | NOT_VERIFIED | No SIMPLIS/switching AC sweep validates a protocol-derived new model in v0.3 |
| Independent agent forward-test | NOT_VERIFIED | No isolated subagent execution surface was available; static contract/CLI tests are not represented as agent behavior evidence |
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
python scripts/df_protocol_checker.py check-json --case tests/protocol_failures/bode_only.json
```

The first two suites test v0.2 regression and v0.3 behavior separately. A `WARNING_INCOMPLETE_VALIDATION` result for `bode_only.json` is expected and proves that Bode-only evidence is not promoted to verification.

## Interpretation

The checker validates protocol completeness and claim honesty; it cannot prove that the chosen event or derived coefficient is physically correct. `PAPER_GROUNDED_PARTIAL` retains the prior paper evidence level. Every near/new model remains `PROTOCOL_DERIVED_UNVERIFIED` / `UNVERIFIED_NEW_DF_MODEL` until a paper benchmark or switching simulation is supplied.

## Version verdict

`v0.3 = paper-grounded single-phase COT/RBCOT DF library + disciplined event-based derivation protocol`. It must not be called a universal Buck DF solver.
