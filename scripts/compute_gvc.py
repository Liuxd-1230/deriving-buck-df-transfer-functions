#!/usr/bin/env python3
"""Plot/compute unverified Gvc only from derivation.json and typed coefficients."""

from __future__ import annotations

import argparse
import csv
import cmath
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

class PlotBindingError(ValueError):
    """Raised when plotting would diverge from the derivation artifact."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"{code}: {message}")


FUNCTIONS = {"exp": cmath.exp, "sin": cmath.sin, "cos": cmath.cos, "sqrt": cmath.sqrt, "log": cmath.log}
DEFAULT_PARAMS = {
    "Vin": 12.0,
    "L": 300e-9,
    "C": 400e-6,
    "R": 0.1,
    "rC": 1.5e-3,
    "rL": 1e-3,
    "D": 0.1,
    "p": 0.8,
    "sf": 1.0e6,
    "Tsw": 2.0e-6,
    "Ts": 2.0e-6,
}
LOW_FREQUENCY_S = 1e-30


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _coefficient_definitions(derivation: dict[str, Any]) -> dict[str, dict[str, Any]]:
    system = derivation.get("linear_equation_system")
    if not isinstance(system, dict):
        raise PlotBindingError("FAIL_PLOT_EXPRESSION_MISMATCH", "derivation lacks linear_equation_system")
    definitions = system.get("coefficient_definitions")
    if not isinstance(definitions, list) or not definitions:
        raise PlotBindingError("FAIL_PLOT_EXPRESSION_MISMATCH", "derivation lacks coefficient_definitions")
    result: dict[str, dict[str, Any]] = {}
    for definition in definitions:
        if isinstance(definition, dict) and definition.get("symbol"):
            result[str(definition["symbol"])] = definition
    return result


def _parameter_units(derivation: dict[str, Any]) -> dict[str, str]:
    system = derivation.get("linear_equation_system")
    units = system.get("parameter_units") if isinstance(system, dict) else None
    return {str(key): str(value) for key, value in (units or {}).items()} if isinstance(units, dict) else {}


def _validate_dcr_dimension(definitions: dict[str, dict[str, Any]], parameter_units: dict[str, str]) -> None:
    rL_is_ohm = parameter_units.get("rL", "").lower() in {"ohm", "ω", "r", "resistance"}
    if not rL_is_ohm and "rL" in parameter_units:
        return
    for symbol, definition in definitions.items():
        expression = str(definition.get("expression", ""))
        compact = expression.replace(" ", "")
        if re.search(r"(?:s\*rL|rL\*s|s\*\([^)]*\brL\b[^)]*\))", compact):
            raise PlotBindingError(
                "FAIL_DIMENSION_SIGNATURE_MISMATCH",
                f"{symbol} expression treats DCR rL as inductance: {expression}",
            )


def _coefficient_expression(definitions: dict[str, dict[str, Any]], symbol: str) -> str | None:
    definition = definitions.get(symbol)
    if not definition:
        return None
    expression = definition.get("expression")
    return str(expression) if expression not in (None, "") else None


def _low_frequency_value(expression: str, params: dict[str, float]) -> complex:
    return _safe_eval_expression(expression, s_value=complex(LOW_FREQUENCY_S, 0.0), params=params)


def _relative_close(actual: float, expected: float, *, rel: float = 5e-3, abs_tol: float = 1e-9) -> bool:
    return abs(actual - expected) <= max(abs_tol, rel * max(abs(expected), 1.0))


def _validate_gvd_dc_gain(definitions: dict[str, dict[str, Any]], params: dict[str, float]) -> dict[str, float]:
    expression = _coefficient_expression(definitions, "Gvd")
    if expression is None:
        return {}
    required = ("Vin", "R", "rL")
    if any(name not in params for name in required):
        return {}
    try:
        value = _low_frequency_value(expression, params)
    except PlotBindingError:
        return {}
    actual = float(value.real)
    expected = params["Vin"] * params["R"] / (params["R"] + params["rL"])
    if not _relative_close(actual, expected):
        raise PlotBindingError(
            "FAIL_POWER_STAGE_GVD_DC_GAIN_MISMATCH",
            f"Gvd(0)={actual:g}, expected Vin*R/(R+rL)={expected:g}",
        )
    return {"Gvd_dc_gain": actual}


def _validate_kmod_dc_gain(definitions: dict[str, dict[str, Any]], params: dict[str, float]) -> dict[str, float | str]:
    expression = _coefficient_expression(definitions, "Kmod")
    definition = definitions.get("Kmod") or {}
    if expression is None:
        return {}
    if definition.get("block_type") != "closed_equivalent_block":
        return {}
    if str(definition.get("from")) != "vc_hat" or str(definition.get("to")) != "d_hat":
        return {}
    Ts = params.get("Ts", params.get("Tsw"))
    if Ts is None or any(name not in params for name in ("D", "p", "sf")):
        return {}
    try:
        value = _low_frequency_value(expression, params)
    except PlotBindingError:
        return {}
    actual = float(value.real)
    expected = params["D"] * (1.0 - params["p"]) / (params["sf"] * Ts)
    missing_d = (1.0 - params["p"]) / (params["sf"] * Ts)
    if not _relative_close(abs(actual), abs(expected)):
        code = "FAIL_KMOD_DC_GAIN_MISSING_D_FACTOR" if _relative_close(abs(actual), abs(missing_d)) else "FAIL_KMOD_DC_GAIN_MISSING_D_FACTOR"
        raise PlotBindingError(
            code,
            f"Kmod(0)={actual:g}, expected D*(1-p)/(sf*Ts)={expected:g}",
        )
    sign = "positive" if actual >= 0 else "negative"
    return {"Kmod_dc_gain": actual, "Kmod_dc_gain_abs": abs(actual), "Kmod_dc_gain_sign": sign}


def _validate_non_return_ratio_margins(derivation: dict[str, Any]) -> None:
    target = derivation.get("target") if isinstance(derivation.get("target"), dict) else {}
    response_kind = str(derivation.get("response_kind") or target.get("response_kind") or "")
    if response_kind == "return_ratio":
        return
    metrics = derivation.get("plot_metrics") if isinstance(derivation.get("plot_metrics"), dict) else {}
    forbidden = {
        "phase_margin_deg",
        "gain_margin_db",
        "PM",
        "GM",
        "phase margin",
        "gain margin",
    }
    present = sorted(str(key) for key, value in metrics.items() if key in forbidden and value is not None)
    if present:
        raise PlotBindingError(
            "FAIL_MARGIN_ON_NON_RETURN_RATIO",
            f"non-return-ratio target cannot report stability margins: {', '.join(present)}",
        )


def _low_frequency_sanity(
    expression: str,
    definitions: dict[str, dict[str, Any]],
    params: dict[str, float],
) -> dict[str, Any]:
    sanity: dict[str, Any] = {}
    sanity.update(_validate_gvd_dc_gain(definitions, params))
    sanity.update(_validate_kmod_dc_gain(definitions, params))
    try:
        value = _low_frequency_value(expression, params)
        gain = abs(value)
        sanity["Gvc_dc_gain"] = float(gain)
        sanity["Gvc_dc_gain_db"] = 20.0 * math.log10(gain) if gain > 0 else -300.0
    except PlotBindingError:
        pass
    return sanity


def _expanded_expression(derivation: dict[str, Any], definitions: dict[str, dict[str, Any]]) -> str:
    generated_text = derivation.get("generated_expression")
    if not generated_text:
        raise PlotBindingError("FAIL_PLOT_EXPRESSION_MISMATCH", "derivation lacks generated_expression")
    expression = str(generated_text)
    for symbol in sorted(definitions, key=len, reverse=True):
        replacement = f"({definitions[symbol].get('expression', '')})"
        expression = re.sub(rf"\b{re.escape(symbol)}\b", replacement, expression)
    return expression


def _check_plot_expression_mismatch(derivation: dict[str, Any]) -> None:
    plot_expression = derivation.get("plot_expression")
    if plot_expression in (None, ""):
        return
    if str(plot_expression).replace(" ", "") != str(derivation.get("generated_expression", "")).replace(" ", ""):
        raise PlotBindingError(
            "FAIL_PLOT_EXPRESSION_MISMATCH",
            "plot_expression differs from derivation.generated_expression",
        )


def _numeric_parameters(derivation: dict[str, Any]) -> dict[str, float]:
    params = dict(DEFAULT_PARAMS)
    system = derivation.get("linear_equation_system") if isinstance(derivation.get("linear_equation_system"), dict) else {}
    supplied = system.get("parameters")
    if isinstance(supplied, dict):
        for key, value in supplied.items():
            try:
                params[str(key)] = float(value)
            except (TypeError, ValueError):
                pass
    return params


def _safe_eval_expression(expression: str, *, s_value: complex, params: dict[str, float]) -> complex:
    env: dict[str, Any] = {"__builtins__": {}}
    env.update(FUNCTIONS)
    env.update(params)
    env["s"] = s_value
    env["pi"] = math.pi
    try:
        return complex(eval(expression, env, {}))
    except Exception as exc:  # pragma: no cover
        raise PlotBindingError("FAIL_PLOT_EXPRESSION_PARSE", f"cannot evaluate plot expression: {exc}") from exc


def _logspace(start_exp: float, stop_exp: float, count: int) -> list[float]:
    if count <= 1:
        return [10 ** start_exp]
    step = (stop_exp - start_exp) / (count - 1)
    return [10 ** (start_exp + index * step) for index in range(count)]


def _write_bode_csv(path: Path, expression: str, params: dict[str, float]) -> None:
    frequencies = _logspace(1, 6, 80)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["frequency_hz", "magnitude_db", "phase_deg"])
        writer.writeheader()
        for frequency in frequencies:
            value = _safe_eval_expression(expression, s_value=1j * 2 * math.pi * frequency, params=params)
            magnitude = 20 * math.log10(abs(value)) if abs(value) > 0 else -300.0
            phase = math.degrees(math.atan2(value.imag, value.real))
            writer.writerow({"frequency_hz": frequency, "magnitude_db": magnitude, "phase_deg": phase})


def build_plot_artifacts(derivation_path: Path, out_dir: Path) -> dict[str, Any]:
    derivation = json.loads(derivation_path.read_text(encoding="utf-8"))
    definitions = _coefficient_definitions(derivation)
    _validate_dcr_dimension(definitions, _parameter_units(derivation))
    _check_plot_expression_mismatch(derivation)
    _validate_non_return_ratio_margins(derivation)
    expression = _expanded_expression(derivation, definitions)
    params = _numeric_parameters(derivation)
    low_frequency = _low_frequency_sanity(expression, definitions, params)
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_bode_csv(out_dir / "bode_model.csv", expression, params)
    coefficient_hashes = {
        symbol: _sha256_text(str(definition.get("expression", "")))
        for symbol, definition in sorted(definitions.items())
    }
    manifest = {
        "status": "PASS",
        "case_id": derivation.get("case_id", "unknown"),
        "target": derivation.get("target_transfer", "Gvc"),
        "source_derivation": "derivation.json",
        "source_expression": "derivation.generated_expression",
        "generated_expression_sha256": derivation.get("generated_expression_sha256") or _sha256_text(str(derivation.get("generated_expression", ""))),
        "derivation_sha256": hashlib.sha256(derivation_path.read_bytes()).hexdigest(),
        "coefficient_expression_sha256": coefficient_hashes,
        "plot_expression": str(expression),
        "plot_expression_sha256": _sha256_text(str(expression)),
        "matches_derivation": True,
        "validation_level": (derivation.get("validation") or {}).get("level", "PROTOCOL_DERIVED_UNVERIFIED"),
        "low_frequency_sanity": low_frequency,
        "stability_margins_status": "APPLICABLE_RETURN_RATIO" if derivation.get("response_kind") == "return_ratio" else "NOT_APPLICABLE_NON_RETURN_RATIO",
        "magnitude_crossing_note": "not a loop stability margin",
        "bode_csv": "bode_model.csv",
    }
    (out_dir / "plot_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Compute Gvc Bode data from derivation.json without redefining coefficients.")
    parser.add_argument("--derivation", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()
    try:
        manifest = build_plot_artifacts(Path(args.derivation), Path(args.out_dir))
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return 0
    except (OSError, json.JSONDecodeError, PlotBindingError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
