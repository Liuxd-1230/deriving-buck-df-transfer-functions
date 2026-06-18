# Buck DF Skill v0.2 Validation

## Material Passport

- Artifact: `deriving-buck-df-transfer-functions`
- Validation date: 2026-06-18
- Scope: single-phase CCM COT/RBCOT describing-function models
- Overall status: `PARTIALLY_VERIFIED`
- Offline requirement: benchmark generation does not access Zotero or bundled PDFs

## Claim matrix

| Check | Status | Evidence |
|---|---|---|
| Generic Buck matrix algebra | VERIFIED | Symbolic plant identities and adapter substitution tests in `scripts/test_*.py` |
| Li/Lee 2010 COT current DF | PARTIALLY_VERIFIED | Eqs. (9)-(10) reproduced; exact-vs-Padé error below `0.49fs` is about `0.0145 dB / 0.0149 deg`; no raw SIMPLIS vectors |
| Tian external-ramp COT DF | PARTIALLY_VERIFIED | Eqs. (4), (6)-(8) bundled; Eq. (13) gives `fp=31.831 kHz`, `fz=95.493 kHz`; exact-vs-low-order error below `0.49fs` is about `1.482 dB / 10.77 deg`; no raw SIMPLIS vectors |
| Li/Lee 2009 V2 stability claim | VERIFIED | Bundled cases reproduce `rC*C > Ton/2`: OSCON stable, ceramic unstable |
| Lu 2023 ESR-ripple loop model | PARTIALLY_VERIFIED | Corrected Eq. (8) plus sign reproduces Fig. 9 shape and trend; assumed `RL=0.12 ohm` because caption omits it; `3.2 mOhm` gives PM about `40.6 deg` versus paper's approximate `45 deg` |
| Huang 2025 internal-ramp model | EXCLUDED_NON_DF | Paper explicitly adopts an average model; model ID is rejected and no benchmark is generated |
| Offline reproduction without Zotero | VERIFIED | `scripts/run_benchmarks.py --all` emits four complete benchmark directories from bundled parameters |
| Exact/approximation separation | VERIFIED | Model metadata and CLI require `exact`, `pade`, or `low-order`; unsupported forms fail |
| Multiphase overlap, DCM, pulse skipping | NOT_VERIFIED | Explicitly unsupported; no applicability claim |
| Independent switching simulation | NOT_VERIFIED | No switching simulation or SIMPLIS sweep is bundled or run in v0.2 |
| Independent forward-agent skill test | NOT_VERIFIED | No subagent execution surface was available during this revision |

## Reproduction

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:MPLBACKEND='Agg'
D:/Python313/python.exe scripts/run_benchmarks.py --all
```

Each directory under `benchmarks/` contains `params.json`, `generated_case.json`, `expected_key_values.json`, `results.json`, `bode_model.csv`, `bode.png`, and `notes.md`.

## Interpretation

`VERIFIED` is used only for exact symbolic identities, deterministic offline generation, or a paper claim with enough published data to decide it. `PARTIALLY_VERIFIED` means the formula is transcribed and produces the reported qualitative/key-value behavior, but raw switching-simulation or measurement vectors are unavailable. Passing unit tests is not treated as proof that a paper formula matches hardware.

## Version verdict

The artifact may be labeled `v0.2 = paper-grounded single-phase COT/RBCOT DF derivation skill` after the current unit suite, all four benchmarks, and the skill validator pass in one fresh verification run. It must not be called a universal Buck DF skill.
