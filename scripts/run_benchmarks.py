#!/usr/bin/env python3
"""Generate offline evidence for the bundled Buck describing-function models."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import subprocess
import shutil
from pathlib import Path
from typing import Any, Callable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import sympy as sp


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from df_model_library import generate_case  # noqa: E402
from formula_registry import formula_binding, get_formula  # noqa: E402
from artifact_workflow import attach_workflow  # noqa: E402


LEGACY_BENCHMARK_NAMES = (
    "tian2015_external_ramp",
    "li_lee2010_cot_cm",
    "li_lee2009_v2_rbcot",
    "lu2023_rbcot_loopgain",
)
SAMPLED_DATA_BENCHMARK_NAMES = (
    "yan_2022_part_i_pcm_buck",
    "yan_2022_part_ii_ccot_buck_zero_ramp",
    "yan_2022_part_ii_vcot_buck_zero_ramp",
    "yan_2022_part_ii_vcot_time_constant_trend",
)
BENCHMARK_NAMES = LEGACY_BENCHMARK_NAMES + SAMPLED_DATA_BENCHMARK_NAMES


def _json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _run_plot_bode(case_path: Path, targets: str, out_dir: Path) -> None:
    command = [
        sys.executable,
        str(SCRIPT_DIR / "df_buck_sympy.py"),
        "plot-bode",
        "--case",
        str(case_path),
        "--targets",
        targets,
        "--out",
        str(out_dir),
    ]
    completed = subprocess.run(command, cwd=SKILL_DIR, text=True, capture_output=True, timeout=120)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr or completed.stdout)


def _sampled_common_artifacts(
    *,
    root: Path,
    name: str,
    model_id: str,
    part_family: str,
    control_family: str,
    target: str,
    transfer_functions: dict[str, str],
    formula_ids: list[str],
    parameters: dict[str, Any],
    sampled_variable: str,
    sideband: dict[str, Any],
    expected: dict[str, Any],
    trends: dict[str, Any] | None,
    notes: str,
) -> dict[str, Any]:
    intake = {
        "intake_version": "0.4",
        "status": "COMPLETE",
        "missing": [],
        "action": "CONTINUE_TO_CLASSIFICATION",
        "normalized": {
            "case_id": name,
            "topology": "buck",
            "conduction_mode": "CCM",
            "phases": 1,
            "control_family": control_family,
            "target": target,
            "target_transfer": target,
            "sampling_event": "modulator input intersection",
            "switching_events": [{"name": "sample", "equation": "input-reference=0"}],
            "comparator_inputs": {"positive": sampled_variable, "negative": "reference"},
            "sampled_variable": sampled_variable,
            "has_external_ramp": False,
            "has_internal_ramp": False,
            "has_delay": False,
            "has_rc_injection": False,
            "has_filter_in_sense_path": False,
            "parameters": parameters,
        },
    }
    intake = attach_workflow(intake, state="PREFLIGHT_INTAKE", intent="paper-benchmark")
    classification = {
        "classification_version": "0.4",
        "path": "SAMPLED_DATA_REGISTERED",
        "part_family": part_family,
        "model_id": model_id,
        "target_transfer": target,
        "validation_level": "SAMPLED_DATA_REGISTERED_PARTIAL",
    }
    classification = attach_workflow(classification, state="MODEL_CLASSIFY", intent="paper-benchmark", predecessor=intake)
    proof_bindings = [
        formula_binding(formula_id)
        for formula_id in formula_ids
        if target in get_formula(formula_id)["supported_targets"]
    ]
    proof = {
        "proof_version": "0.4",
        "case_id": name,
        "intake": {"status": "COMPLETE", "normalized": intake["normalized"]},
        "classification": classification,
        "formula_bindings": proof_bindings,
        "sampling": {
            "sampling_instant": "modulator input intersection",
            "sampled_variable": sampled_variable,
            "left_limit": f"{sampled_variable}(k-)",
            "right_limit": f"{sampled_variable}(k+)",
            "dirichlet_value": f"({sampled_variable}(k-)+{sampled_variable}(k+))/2",
            "dirichlet_required": True,
        },
        "Fm": {
            "type": "constant",
            "expression": parameters.get("Fm_expression", "1/((m2-m1)*Ts/2)"),
            "origin": "sampled_data_derivation",
            "depends_on": ["m1", "m2", "Ts"],
            "dirichlet_reference": "sampling.dirichlet_value",
        },
        "sideband": sideband,
        "modulator_io": {
            "input": sampled_variable,
            "output": "d" if part_family == "SAMPLED_DATA_REGISTERED_PART_I_PCM_VCM_PVM_VVM" else "dsum",
            "definition": "GPWM=-d_hat/input_hat" if target == "GPWM" else "Gm=-dsum_hat/input_hat",
            "sign_convention": "negative",
        },
        "target_mapping": {
            "available_registered_outputs": list(transfer_functions),
            "requested_target": target,
            "mapping_rule": "registered sampled-data benchmark expression from formula registry fragments",
            "mapping_status": "REGISTERED_DIRECT" if target in {"Gm", "GPWM"} else "REGISTERED_DERIVED",
        },
        "modulator": {"model_type": "sampled-data", "expression": transfer_functions[target]},
        "transfer": {"target_transfer": target, "formula_id": None, "expression": transfer_functions[target]},
        "validation": {
            "level": "SAMPLED_DATA_REGISTERED_PARTIAL",
            "completed": ["sampled-data-contract", "dirichlet-reference", "unified-plot-bode"],
            "missing": ["paper-figure-digitization", "switching-simulation"],
        },
    }
    if "PART_II" in part_family:
        t0 = "Ton" if "COT" in control_family else "Toff"
        proof["pulse_structure"] = {
            "type": "COT_TWO_PULSE_TRAINS" if "COT" in control_family else "COFT_TWO_PULSE_TRAINS",
            "d1": "narrow pulse train at sampling instant",
            "d2": f"delayed inverse pulse train by {t0}",
            "relation": f"d2(t)=-d1(t-{t0})",
            "frequency_factor": f"1-exp(-s*{t0})",
            "T0": t0,
        }
    else:
        proof["pulse_structure"] = {"type": "SINGLE_PULSE_TRAIN", "frequency_factor": "1"}
    proof = attach_workflow(proof, state="FORMULA_BINDING", intent="paper-benchmark", predecessor=classification)

    generated_case = {
        "case_version": "0.4-sampled-data",
        "name": name,
        "model_id": model_id,
        "parameters": parameters,
        "valid_frequency": {"max_hz": parameters["fs"] / 2},
        "transfer_functions": transfer_functions,
        "sideband": sideband,
    }
    formula_origin = {
        "source": "formula_registry.yaml",
        "formula_ids": formula_ids,
        "handwritten_formula_variants": False,
        "pdf_bundled": False,
        "notes": "PDFs were used during development only; benchmark artifacts are self-contained.",
    }
    _json(root / "intake.json", intake)
    _json(root / "classification.json", classification)
    _json(root / "proof_object.json", proof)
    _json(root / "formula_origin.json", formula_origin)
    _json(root / "generated_case.json", generated_case)
    _json(root / "expected_key_values.json", expected)
    if trends is not None:
        _json(root / "expected_trends.json", trends)
    (root / "notes.md").write_text(notes, encoding="utf-8")
    _run_plot_bode(root / "generated_case.json", ",".join(transfer_functions), root)
    summary = json.loads((root / "bode_summary.json").read_text(encoding="utf-8"))
    first_target = next(iter(transfer_functions))
    first_csv = root / f"{first_target}_bode.csv"
    first_png = root / f"{first_target}_bode.png"
    if first_csv.exists():
        shutil.copyfile(first_csv, root / "bode_model.csv")
    if first_png.exists():
        shutil.copyfile(first_png, root / "bode.png")
    return {"status": "SAMPLED_DATA_REGISTERED_PARTIAL", "plot_bode": summary, "formula_origin": formula_origin}


def _symbolic_context(parameters: dict[str, Any]) -> tuple[dict[str, Any], dict[sp.Symbol, sp.Expr]]:
    names = set(parameters) | {"s"}
    table: dict[str, Any] = {name: sp.Symbol(name) for name in names}
    table.update({"exp": sp.exp, "pi": sp.pi, "sqrt": sp.sqrt})
    substitutions = {
        table[name]: sp.sympify(value, locals=table) for name, value in parameters.items()
    }
    for _ in range(len(substitutions) + 1):
        updated = {key: sp.simplify(value.subs(substitutions)) for key, value in substitutions.items()}
        if updated == substitutions:
            break
        substitutions = updated
    return table, substitutions


def _evaluate(expression: str, parameters: dict[str, Any], frequencies: np.ndarray) -> np.ndarray:
    table, substitutions = _symbolic_context(parameters)
    s = table["s"]
    symbolic = sp.sympify(expression, locals=table).subs(substitutions)
    remaining = symbolic.free_symbols - {s}
    if remaining:
        raise ValueError(f"Unresolved symbols in benchmark expression: {sorted(map(str, remaining))}")
    function = sp.lambdify(s, symbolic, modules="numpy")
    values = np.asarray(function(1j * 2 * np.pi * frequencies), dtype=complex)
    if values.ndim == 0:
        values = np.full(frequencies.shape, values, dtype=complex)
    return values


def _magnitude_phase(values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    magnitude = 20 * np.log10(np.maximum(np.abs(values), np.finfo(float).tiny))
    phase = np.unwrap(np.angle(values)) * 180 / np.pi
    return magnitude, phase


def _write_csv(path: Path, columns: dict[str, np.ndarray]) -> None:
    names = list(columns)
    count = len(columns[names[0]])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(names)
        for index in range(count):
            writer.writerow([f"{float(columns[name][index]):.12g}" for name in names])


def _crossover_phase_margin(frequency: np.ndarray, values: np.ndarray) -> dict[str, float] | None:
    magnitude, phase = _magnitude_phase(values)
    crossings = np.where((magnitude[:-1] >= 0) & (magnitude[1:] < 0))[0]
    if len(crossings) == 0:
        return None
    index = int(crossings[0])
    x0, x1 = np.log10(frequency[index : index + 2])
    y0, y1 = magnitude[index : index + 2]
    fraction = float(-y0 / (y1 - y0))
    log_fc = float(x0 + fraction * (x1 - x0))
    phase_at_fc = float(phase[index] + fraction * (phase[index + 1] - phase[index]))
    while phase_at_fc > 0:
        phase_at_fc -= 360
    return {
        "crossover_hz": 10**log_fc,
        "phase_deg": phase_at_fc,
        "phase_margin_deg": 180 + phase_at_fc,
    }


def _plot_pairs(
    path: Path,
    frequency: np.ndarray,
    series: dict[str, np.ndarray],
    title: str,
    limit_hz: float | None = None,
) -> None:
    figure, axes = plt.subplots(2, 1, figsize=(8, 7), sharex=True)
    for label, values in series.items():
        magnitude, phase = _magnitude_phase(values)
        axes[0].semilogx(frequency, magnitude, label=label)
        axes[1].semilogx(frequency, phase, label=label)
    if limit_hz:
        for axis in axes:
            axis.axvline(limit_hz, color="0.35", linestyle="--", linewidth=1, label="claimed limit")
    axes[0].set_ylabel("Magnitude (dB)")
    axes[1].set_ylabel("Phase (deg)")
    axes[1].set_xlabel("Frequency (Hz)")
    axes[0].set_title(title)
    for axis in axes:
        axis.grid(True, which="both", alpha=0.25)
        axis.legend(fontsize=8)
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def _tian(root: Path) -> dict[str, Any]:
    parameters = {
        "Vin": 12.0,
        "Vo": 1.2,
        "fs": 300e3,
        "L": 300e-9,
        "C": 8 * 560e-6,
        "R": 0.1,
        "rL": 0.0,
        "rC": 6e-3 / 8,
        "Ri": 10e-3,
        "se_ratio": 1.0,
    }
    case = generate_case("cot-cm-external-ramp-tian-2015", parameters, "exact")
    frequency = np.logspace(2, math.log10(0.49 * parameters["fs"]), 500)
    exact = _evaluate(case["paper_model"]["Fc"], case["parameters"], frequency)
    low = _evaluate(case["paper_model"]["Fc_low_order"], case["parameters"], frequency)
    magnitude_error = np.max(np.abs(_magnitude_phase(exact)[0] - _magnitude_phase(low)[0]))
    phase_error = np.max(np.abs(_magnitude_phase(exact)[1] - _magnitude_phase(low)[1]))
    expected = {
        "moving_pole_hz": parameters["fs"] / (3 * math.pi),
        "stationary_zero_hz": parameters["fs"] / math.pi,
        "valid_to_hz": parameters["fs"] / 2,
    }
    results = {
        "status": "PARTIALLY_VERIFIED",
        "evidence": "Paper equations and published fs/2 validity range; no raw SIMPLIS data bundled.",
        "moving_pole_hz": case["features_hz"]["moving_pole"],
        "stationary_zero_hz": case["features_hz"]["stationary_zero"],
        "max_exact_vs_low_order_magnitude_error_db_below_0p49fs": float(magnitude_error),
        "max_exact_vs_low_order_phase_error_deg_below_0p49fs": float(phase_error),
    }
    exact_mag, exact_phase = _magnitude_phase(exact)
    low_mag, low_phase = _magnitude_phase(low)
    _write_csv(
        root / "bode_model.csv",
        {
            "frequency_hz": frequency,
            "exact_magnitude_db": exact_mag,
            "exact_phase_deg": exact_phase,
            "low_order_magnitude_db": low_mag,
            "low_order_phase_deg": low_phase,
        },
    )
    _plot_pairs(root / "bode.png", frequency, {"exact Eq.4": exact, "low-order Eq.8": low}, "Tian external-ramp control-current DF", parameters["fs"] / 2)
    notes = """# Tian external-ramp benchmark

- Source: Tian et al., DOI 10.1109/TPEL.2015.2508037, PDF pages 3 and 7.
- Parameters follow the paper's single-phase SIMPLIS case (Fig. 17); `se = sf`.
- The CSV compares the exact exponential control-current DF (Eq. 4) with Eq. 8.
- `PARTIALLY_VERIFIED` means the formulas and pole/zero features are reproducible, but the paper's raw SIMPLIS sweep is unavailable.
"""
    (root / "notes.md").write_text(notes, encoding="utf-8")
    return {"parameters": parameters, "case": case, "expected": expected, "results": results}


def _li2010(root: Path) -> dict[str, Any]:
    parameters = {
        "Vin": 12.0,
        "Vo": 1.2,
        "fs": 300e3,
        "L": 300e-9,
        "C": 8 * 560e-6,
        "R": 0.1,
        "rL": 0.0,
        "rC": 6e-3 / 8,
        "Ri": 10e-3,
    }
    exact_case = generate_case("cot-cm-li-lee-2010", parameters, "exact")
    pade_case = generate_case("cot-cm-li-lee-2010", parameters, "pade")
    frequency = np.logspace(2, math.log10(0.49 * parameters["fs"]), 500)
    exact = _evaluate(exact_case["paper_model"]["Fc"], exact_case["parameters"], frequency)
    pade = _evaluate(pade_case["paper_model"]["Fc"], pade_case["parameters"], frequency)
    exact_mag, exact_phase = _magnitude_phase(exact)
    pade_mag, pade_phase = _magnitude_phase(pade)
    expected = {
        "dc_gain_a_per_v": 1 / parameters["Ri"],
        "pade_double_pole_hz": 1 / (2 * exact_case["parameters"]["Ton"]),
        "benchmark_limit_hz": parameters["fs"] / 2,
    }
    results = {
        "status": "PARTIALLY_VERIFIED",
        "evidence": "Li/Lee Eqs. (9)-(10); no raw SIMPLIS vectors bundled.",
        "max_exact_vs_pade_magnitude_error_db_below_0p49fs": float(np.max(np.abs(exact_mag - pade_mag))),
        "max_exact_vs_pade_phase_error_deg_below_0p49fs": float(np.max(np.abs(exact_phase - pade_phase))),
    }
    _write_csv(
        root / "bode_model.csv",
        {
            "frequency_hz": frequency,
            "exact_magnitude_db": exact_mag,
            "exact_phase_deg": exact_phase,
            "pade_magnitude_db": pade_mag,
            "pade_phase_deg": pade_phase,
        },
    )
    _plot_pairs(root / "bode.png", frequency, {"exact Eq.9": exact, "Padé Eq.10": pade}, "Li/Lee 2010 COT current DF", parameters["fs"] / 2)
    notes = """# Li/Lee 2010 COT current-mode benchmark

- Source: Li and Lee, DOI 10.1109/TPEL.2010.2040123, PDF pages 5-7 and 11.
- The power-stage parameters follow the paper's 300 kHz Buck example. `Ri=10 mOhm` is stated here as a normalization parameter and is not claimed as a Fig. 20 digitized value.
- The benchmark compares paper Eq. 9 with its Eq. 10 Padé form. It does not claim a point-by-point reproduction of a SIMPLIS trace.
"""
    (root / "notes.md").write_text(notes, encoding="utf-8")
    return {"parameters": parameters, "case": exact_case, "expected": expected, "results": results}


def _li2009(root: Path) -> dict[str, Any]:
    common = {
        "Vin": 12.0,
        "Vo": 1.2,
        "fs": 300e3,
        "L": 300e-9,
        "R": 0.1,
        "rL": 0.0,
        "Ri": 10e-3,
    }
    cases = {
        "oscon": generate_case("v2-cot-li-lee-2009", common | {"C": 560e-6, "rC": 6e-3}, "pade"),
        "ceramic": generate_case("v2-cot-li-lee-2009", common | {"C": 100e-6, "rC": 1.4e-3}, "pade"),
    }
    frequency = np.logspace(2, math.log10(0.49 * common["fs"]), 500)
    values = {name: _evaluate(case["paper_model"]["Gvc"], case["parameters"], frequency) for name, case in cases.items()}
    columns: dict[str, np.ndarray] = {"frequency_hz": frequency}
    for name, response in values.items():
        magnitude, phase = _magnitude_phase(response)
        columns[f"{name}_magnitude_db"] = magnitude
        columns[f"{name}_phase_deg"] = phase
    _write_csv(root / "bode_model.csv", columns)
    _plot_pairs(root / "bode.png", frequency, values, "Li/Lee 2009 V2 COT capacitor-ripple DF", common["fs"] / 2)
    expected = {"oscon_stable": True, "ceramic_stable": False, "criterion": "rC*C > Ton/2"}
    observed = {f"{name}_stable": case["stability"]["stable_by_paper_boundary"] for name, case in cases.items()}
    results = {
        "status": "VERIFIED" if observed == {"oscon_stable": True, "ceramic_stable": False} else "PARTIALLY_VERIFIED",
        "evidence": "Published stability boundary and the two capacitor examples in the paper.",
        **observed,
        "margins_seconds": {name: case["stability"]["margin_seconds"] for name, case in cases.items()},
    }
    notes = """# Li/Lee 2009 V2 benchmark

- Source: Li and Lee, *Modeling of V2 Current-Mode Control*, PDF pages 3 and 6.
- The reproducible claim is the paper's boundary `Rco*Co > Ton/2`: the OSCON case is stable and the ceramic case is unstable.
- `VERIFIED` applies to that classification, not to pixel-level agreement with the published Bode image.
"""
    (root / "notes.md").write_text(notes, encoding="utf-8")
    combined_case = {"model_id": "v2-cot-li-lee-2009", "cases": cases}
    return {"parameters": {"common": common, "capacitors": {"oscon": {"C": 560e-6, "rC": 6e-3}, "ceramic": {"C": 100e-6, "rC": 1.4e-3}}}, "case": combined_case, "expected": expected, "results": results}


def _lu2023(root: Path) -> dict[str, Any]:
    common = {
        "Vin": 12.0,
        "Vo": 1.2,
        "fs": 400e3,
        "L": 660e-9,
        "C": 250e-6,
        "R": 0.12,
        "rL": 0.0,
    }
    esr_values = {"0p5m": 0.5e-3, "3p2m": 3.2e-3, "10m": 10e-3}
    frequency = np.logspace(3, 6, 900)
    responses: dict[str, np.ndarray] = {}
    generated: dict[str, Any] = {}
    metrics: dict[str, Any] = {}
    for label, esr in esr_values.items():
        case = generate_case("rbcot-esr-lu-2023", common | {"rC": esr}, "exact")
        generated[label] = case
        fdx = _evaluate(case["paper_model"]["Fdx"], case["parameters"], frequency)
        fodx = _evaluate(case["paper_model"]["Fodx"], case["parameters"], frequency)
        fp = _evaluate(case["paper_model"]["Fp"], case["parameters"], frequency)
        fox = -fodx - fdx
        loop = fdx * fp / (1 + fox * fp)
        responses[label] = loop
        metrics[label] = _crossover_phase_margin(frequency, loop)
    pade_case = generate_case("rbcot-esr-lu-2023", common | {"rC": esr_values["3p2m"]}, "pade")
    pade_fdx = _evaluate(pade_case["paper_model"]["Fdx"], pade_case["parameters"], frequency)
    pade_fodx = _evaluate(pade_case["paper_model"]["Fodx"], pade_case["parameters"], frequency)
    pade_fp = _evaluate(pade_case["paper_model"]["Fp"], pade_case["parameters"], frequency)
    pade_fox = -pade_fodx - pade_fdx
    pade_loop = pade_fdx * pade_fp / (1 + pade_fox * pade_fp)
    exact_3p2m_mag, exact_3p2m_phase = _magnitude_phase(responses["3p2m"])
    pade_mag, pade_phase = _magnitude_phase(pade_loop)
    within_limit = frequency <= common["fs"] / 2
    columns: dict[str, np.ndarray] = {"frequency_hz": frequency}
    for label, response in responses.items():
        magnitude, phase = _magnitude_phase(response)
        columns[f"esr_{label}_magnitude_db"] = magnitude
        columns[f"esr_{label}_phase_deg"] = phase
    columns["esr_3p2m_pade_magnitude_db"] = pade_mag
    columns["esr_3p2m_pade_phase_deg"] = pade_phase
    _write_csv(root / "bode_model.csv", columns)
    plot_series = {f"ESR {label} exact": response for label, response in responses.items()}
    plot_series["ESR 3p2m Padé"] = pade_loop
    _plot_pairs(root / "bode.png", frequency, plot_series, "Lu 2023 RBCOT loop gain", common["fs"] / 2)
    expected = {
        "paper_parameters": "Fig. 9 except RL is not reported in the caption",
        "optimum_esr_ohm": 3.2e-3,
        "optimum_phase_margin_deg_approx": 45.0,
        "valid_to_hz": common["fs"] / 2,
    }
    results = {
        "status": "PARTIALLY_VERIFIED",
        "evidence": "Exact paper Eqs. (5), (8)-(11); RL=0.12 ohm is an explicit benchmark assumption because Fig. 9 does not report RL.",
        "crossovers": metrics,
        "pade_comparison_3p2m": {
            "max_magnitude_error_db_to_fs_over_2": float(
                np.max(np.abs(exact_3p2m_mag[within_limit] - pade_mag[within_limit]))
            ),
            "max_phase_error_deg_to_fs_over_2": float(
                np.max(np.abs(exact_3p2m_phase[within_limit] - pade_phase[within_limit]))
            ),
            "pade_crossover": _crossover_phase_margin(frequency, pade_loop),
        },
    }
    notes = """# Lu 2023 RBCOT loop-gain benchmark

- Source: Lu et al., DOI 10.1109/TPEL.2023.3254906, PDF pages 4-6.
- `Vin`, `Vo`, `fs`, `C`, `L`, and ESR values follow Fig. 9. The caption does not report `RL`; this benchmark explicitly assumes `RL=0.12 ohm` and therefore remains `PARTIALLY_VERIFIED`.
- The CSV evaluates exact Eqs. (5), (8)-(11). No paper image pixels or raw SIMPLIS data are bundled.
"""
    (root / "notes.md").write_text(notes, encoding="utf-8")
    return {"parameters": {"common": common, "esr_values": esr_values}, "case": {"model_id": "rbcot-esr-lu-2023", "cases": generated}, "expected": expected, "results": results}


def _yan_part_i_pcm(root: Path) -> dict[str, Any]:
    parameters = {"fs": 100e3, "Ts": 10e-6, "m1": 1.0, "m2": 4.0, "Fm": 1 / ((4.0 - 1.0) * 10e-6 / 2)}
    result = _sampled_common_artifacts(
        root=root,
        name="yan_2022_part_i_pcm_buck",
        model_id="yan-2022-part-i-pcm-buck",
        part_family="SAMPLED_DATA_REGISTERED_PART_I_PCM_VCM_PVM_VVM",
        control_family="PCM",
        target="Gm",
        transfer_functions={"Gm": "Fm"},
        formula_ids=["yan-2022-part-i.dirichlet-value", "yan-2022-part-i.pcm-fm-zero-ramp", "yan-2022-part-i.sideband-symbolic"],
        parameters=parameters,
        sampled_variable="is",
        sideband={"mode": "PAPER_SIMPLIFIED_FORM", "numeric_evaluable": True, "expression": "Fm"},
        expected={"dirichlet_required": True, "Fm_origin": "sampled_data_derivation"},
        trends=None,
        notes="# Yan 2022 Part I PCM sampled-data benchmark\n\nContract benchmark for Dirichlet-based Fm and sampled modulator proof skeleton.\n",
    )
    return {"parameters": parameters, "case": json.loads((root / "generated_case.json").read_text(encoding="utf-8")), "expected": {"dirichlet_required": True}, "results": result}


def _yan_part_ii_ccot(root: Path) -> dict[str, Any]:
    parameters = {"fs": 98e3, "Ts": 1 / 98e3, "Ton": 3e-6, "T0": 3e-6, "m1": 1.0, "m2": 4.0, "Fm": 1 / ((4.0 - 1.0) * (1 / 98e3) / 2)}
    result = _sampled_common_artifacts(
        root=root,
        name="yan_2022_part_ii_ccot_buck_zero_ramp",
        model_id="yan-2022-part-ii-ccot-buck-zero-ramp",
        part_family="SAMPLED_DATA_REGISTERED_PART_II_CCOT_CCOFT",
        control_family="C-COT",
        target="Gm",
        transfer_functions={"Gm": "Fm*(1-exp(-s*Ton))"},
        formula_ids=["yan-2022-part-ii.ccot-gpwm-pulse-factor", "yan-2022-part-ii.ccot-ti-truncated"],
        parameters=parameters,
        sampled_variable="is",
        sideband={"mode": "TRUNCATED_SUM_M", "M": 10, "numeric_evaluable": True},
        expected={"pulse_factor": "1-exp(-s*T0)", "T0": "Ton"},
        trends=None,
        notes="# Yan 2022 Part II C-COT zero-ramp benchmark\n\nChecks the two-pulse-train factor and unified plot-bode numeric path. It is not a v0.5 external-ramp Fm(s) model.\n",
    )
    return {"parameters": parameters, "case": json.loads((root / "generated_case.json").read_text(encoding="utf-8")), "expected": {"T0": "Ton"}, "results": result}


def _yan_part_ii_vcot(root: Path) -> dict[str, Any]:
    parameters = {"fs": 98e3, "Ts": 1 / 98e3, "Ton": 3e-6, "T0": 3e-6, "Fm": 25.0, "Hv": 0.36}
    result = _sampled_common_artifacts(
        root=root,
        name="yan_2022_part_ii_vcot_buck_zero_ramp",
        model_id="yan-2022-part-ii-vcot-buck-zero-ramp",
        part_family="SAMPLED_DATA_REGISTERED_PART_II_VCOT_VCOFT",
        control_family="V-COT",
        target="GPWM",
        transfer_functions={"GPWM": "Fm*(1-exp(-s*Ton))"},
        formula_ids=["yan-2022-part-ii.vcot-gpwm-pulse-factor", "yan-2022-part-ii.vcot-tv-truncated"],
        parameters=parameters,
        sampled_variable="vfb",
        sideband={"mode": "TRUNCATED_SUM_M", "M": 10, "numeric_evaluable": True},
        expected={"pulse_factor": "1-exp(-s*T0)", "T0": "Ton"},
        trends=None,
        notes="# Yan 2022 Part II V-COT zero-ramp benchmark\n\nKeeps V-COT sampled-data path separate from Li/Lee V² COT direct-transfer and Lu RBCOT loop-gain models.\n",
    )
    return {"parameters": parameters, "case": json.loads((root / "generated_case.json").read_text(encoding="utf-8")), "expected": {"T0": "Ton"}, "results": result}


def _yan_vcot_trend(root: Path) -> dict[str, Any]:
    base = {"C": 200e-6, "rC": 0.010, "Ton": 3e-6, "T0": 3e-6}
    def margin(values: dict[str, float]) -> float:
        return values["rC"] * values["C"] - values["T0"] / 2
    margins = {
        "base": margin(base),
        "higher_rC": margin(base | {"rC": 0.012}),
        "higher_C": margin(base | {"C": 240e-6}),
        "higher_Ton": margin(base | {"Ton": 4e-6, "T0": 4e-6}),
    }
    trends = {
        "criterion": "rC*C > T0/2",
        "increase_rC": "stability_margin_increases",
        "increase_C": "stability_margin_increases",
        "increase_Ton": "stability_margin_decreases",
    }
    parameters = {"fs": 98e3, "Ts": 1 / 98e3, "Ton": base["Ton"], "T0": base["T0"], "Fm": 25.0, **base}
    result = _sampled_common_artifacts(
        root=root,
        name="yan_2022_part_ii_vcot_time_constant_trend",
        model_id="yan-2022-part-ii-vcot-buck-zero-ramp",
        part_family="SAMPLED_DATA_REGISTERED_PART_II_VCOT_VCOFT",
        control_family="V-COT",
        target="GPWM",
        transfer_functions={"GPWM": "Fm*(1-exp(-s*Ton))"},
        formula_ids=["yan-2022-part-ii.vcot-time-constant-boundary", "yan-2022-part-ii.vcot-gpwm-pulse-factor"],
        parameters=parameters,
        sampled_variable="vfb",
        sideband={"mode": "PAPER_SIMPLIFIED_FORM", "numeric_evaluable": True, "expression": "Fm*(1-exp(-s*Ton))"},
        expected={"boundary_margin_seconds": margins["base"]},
        trends=trends,
        notes="# Yan 2022 Part II V-COT time-constant trend benchmark\n\nGuards the paper boundary `rC*C > T0/2`: increasing ESR or C must improve the margin, increasing Ton/T0 must reduce it.\n",
    )
    result["trend_checks"] = {
        "increase_rC": margins["higher_rC"] > margins["base"],
        "increase_C": margins["higher_C"] > margins["base"],
        "increase_Ton": margins["higher_Ton"] < margins["base"],
    }
    result["margins_seconds"] = margins
    return {"parameters": parameters, "case": json.loads((root / "generated_case.json").read_text(encoding="utf-8")), "expected": {"criterion": trends["criterion"]}, "results": result}


BUILDERS: dict[str, Callable[[Path], dict[str, Any]]] = {
    "tian2015_external_ramp": _tian,
    "li_lee2010_cot_cm": _li2010,
    "li_lee2009_v2_rbcot": _li2009,
    "lu2023_rbcot_loopgain": _lu2023,
    "yan_2022_part_i_pcm_buck": _yan_part_i_pcm,
    "yan_2022_part_ii_ccot_buck_zero_ramp": _yan_part_ii_ccot,
    "yan_2022_part_ii_vcot_buck_zero_ramp": _yan_part_ii_vcot,
    "yan_2022_part_ii_vcot_time_constant_trend": _yan_vcot_trend,
}


def run_benchmark(name: str, output_root: Path) -> dict[str, Any]:
    root = output_root / name
    root.mkdir(parents=True, exist_ok=True)
    artifact = BUILDERS[name](root)
    _json(root / "params.json", artifact["parameters"])
    _json(root / "generated_case.json", artifact["case"])
    _json(root / "expected_key_values.json", artifact["expected"])
    _json(root / "results.json", artifact["results"])
    return artifact["results"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate offline Buck DF paper benchmarks.")
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--all", action="store_true", help="Run all bundled benchmarks.")
    selection.add_argument("--benchmark", choices=BENCHMARK_NAMES, help="Run one benchmark.")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=SKILL_DIR / "benchmarks",
        help="Destination directory (defaults to the skill's benchmarks folder).",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    names = BENCHMARK_NAMES if args.all else (args.benchmark,)
    summary = {name: run_benchmark(name, args.output_root) for name in names}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
