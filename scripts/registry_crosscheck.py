#!/usr/bin/env python3
"""Independent paper-registry cross-checks for v0.5 physical derivations."""

from __future__ import annotations

import copy
from typing import Any

import numpy as np
import sympy as sp
from scipy.integrate import trapezoid as _TRAPEZOID

from df_buck_sympy import derive_model
from df_model_library import generate_case
from formula_registry import load_registry
from physics_workflow import attach_physics_workflow, verify_physics_workflow
from schema_validation import validate_artifact


class RegistryCrosscheckError(ValueError):
    """Raised when a declared registry comparison is malformed."""


def _component_value(component: dict[str, Any]) -> float:
    value = component.get("value")
    return float(value["magnitude"] if isinstance(value, dict) else value)


def _unique_component(
    inventory: list[dict[str, Any]], *, parameter: str, kind: str,
    role: str | None = None,
) -> dict[str, Any] | None:
    candidates = [item for item in inventory if item.get("type") == kind]
    if role is not None:
        candidates = [
            item for item in candidates
            if str((item.get("parameters") or {}).get("role", "")).lower() == role.lower()
        ]
    if not candidates:
        return None
    if len(candidates) != 1:
        raise RegistryCrosscheckError(
            f"cannot bind registry parameter {parameter}: expected one {kind}"
            + (f" with role {role}" if role else "")
            + f", found {[item.get('id') for item in candidates]}"
        )
    return candidates[0]


def _input_source_voltage(
    inventory: list[dict[str, Any]], physics_spec: dict[str, Any]
) -> float | None:
    sources = []
    for item in inventory:
        if item.get("type") != "voltage_source":
            continue
        parameters = item.get("parameters") or {}
        input_name = parameters.get("input")
        positive_net = str((item.get("terminals") or {}).get("p", "")).lower()
        component_id = str(item.get("id", "")).lower()
        if input_name in {"vg", "vin"} or positive_net in {"vin", "vg"} or component_id in {"vg", "vin"}:
            sources.append(item)
    if len(sources) > 1:
        raise RegistryCrosscheckError(
            f"cannot bind registry Vin: multiple input sources {[item.get('id') for item in sources]}"
        )
    if not sources:
        return None
    source = sources[0]
    source_parameters = source.get("parameters") or {}
    input_name = source_parameters.get("input")
    dc = (
        float(source_parameters["dc"])
        if "dc" in source_parameters else _component_value(source)
    )
    gain = float(source_parameters.get("gain", 1.0))
    if input_name is None:
        return dc
    if input_name not in physics_spec["inputs"]:
        raise RegistryCrosscheckError(f"input source {source.get('id')} references missing operating input {input_name}")
    return dc + gain * float(physics_spec["inputs"][input_name])


def _average_output_voltage(
    provenance: dict[str, Any], physics_spec: dict[str, Any], orbit: dict[str, Any]
) -> float | None:
    target_output = physics_spec["target"]["output"]
    matches = [item for item in provenance["ports"] if item.get("name") == target_output]
    if len(matches) != 1:
        return None
    expression_text = str(matches[0].get("expression", ""))
    variable_names = list(provenance["variables"])
    input_names = list(provenance["inputs"])
    symbols = {name: sp.Symbol(name) for name in variable_names + input_names}
    expression = sp.sympify(expression_text, locals=symbols)
    unresolved = expression.free_symbols - set(symbols.values())
    if unresolved:
        raise RegistryCrosscheckError(
            f"cannot evaluate output port {target_output}; unresolved symbols {sorted(map(str, unresolved))}"
        )
    function = sp.lambdify([symbols[name] for name in variable_names + input_names], expression, modules="numpy")
    integral = 0.0
    sample_count = 0
    for interval in orbit["mode_intervals"]:
        samples = interval.get("samples", [])
        if len(samples) < 2:
            continue
        local_time = np.asarray(
            [item["time"] - interval["start_time"] for item in samples], dtype=float
        )
        full = np.asarray([item["full"] for item in samples], dtype=float)
        arguments: list[Any] = [full[:, index] for index in range(len(variable_names))]
        arguments.extend(
            np.full(len(samples), float(physics_spec["inputs"][name]), dtype=float)
            for name in input_names
        )
        values = np.asarray(function(*arguments), dtype=float)
        if values.ndim == 0:
            values = np.full(len(samples), float(values), dtype=float)
        integral += float(_TRAPEZOID(values, local_time))
        sample_count += len(samples)
    if sample_count == 0:
        return None
    return integral / float(orbit["events"][-1]["time"])


def _validate_parameter_match(
    parameters: dict[str, Any], provenance: dict[str, Any],
    physics_spec: dict[str, Any], orbit: dict[str, Any],
) -> dict[str, Any]:
    inventory = provenance["component_inventory"]
    inductor = (
        _unique_component(inventory, parameter="L/rL", kind="inductor")
        if {"L", "rL"} & set(parameters) else None
    )
    capacitor = (
        _unique_component(inventory, parameter="C", kind="capacitor")
        if "C" in parameters else None
    )
    load = (
        _unique_component(inventory, parameter="R", kind="resistor", role="load")
        if "R" in parameters else None
    )
    esr = (
        _unique_component(inventory, parameter="rC", kind="resistor", role="ESR")
        if "rC" in parameters else None
    )
    expected: dict[str, float] = {"fs": 1.0 / float(orbit["events"][-1]["time"])}
    vin = _input_source_voltage(inventory, physics_spec) if "Vin" in parameters else None
    if vin is not None:
        expected["Vin"] = vin
    if inductor is not None:
        expected["L"] = _component_value(inductor)
        expected["rL"] = float((inductor.get("parameters") or {}).get("series_resistance", 0.0))
    if capacitor is not None:
        expected["C"] = _component_value(capacitor)
    if load is not None:
        expected["R"] = _component_value(load)
    if esr is not None:
        expected["rC"] = _component_value(esr)
    output_voltage = (
        _average_output_voltage(provenance, physics_spec, orbit)
        if "Vo" in parameters else None
    )
    if output_voltage is not None:
        expected["Vo"] = output_voltage
    required_physical = sorted(set(parameters) & {"Vin", "Vo", "fs", "L", "C", "R", "rC", "rL"})
    missing = sorted(set(required_physical) - set(expected))
    if missing:
        raise RegistryCrosscheckError(
            f"cannot verify registry parameters against Confirmed Circuit IR/Periodic Orbit: {missing}"
        )
    mismatches = []
    for name, expected_value in expected.items():
        if name not in parameters:
            continue
        tolerance = 0.03 if name == "fs" else (0.1 if name == "Vo" else 1e-9)
        if not np.isclose(float(parameters[name]), expected_value, rtol=tolerance, atol=1e-15):
            mismatches.append({"parameter": name, "registry": float(parameters[name]), "physics": expected_value, "relative_tolerance": tolerance})
    if mismatches:
        raise RegistryCrosscheckError(f"registry working point does not match physical model: {mismatches}")
    return {
        "status": "MATCH", "physics_values": expected,
        "checked_parameters": required_physical,
        "tolerances": {"fs_relative": 0.03, "Vo_relative": 0.1, "component_relative": 1e-9},
        "source": "Confirmed Circuit IR component inventory plus Periodic Orbit",
    }


def _evaluate(expression: str, parameters: dict[str, Any], frequencies: np.ndarray) -> np.ndarray:
    names = set(parameters) | {"s"}
    table: dict[str, Any] = {name: sp.Symbol(name) for name in names}
    table.update({"exp": sp.exp, "pi": sp.pi, "sqrt": sp.sqrt})
    substitutions = {table[name]: sp.sympify(value, locals=table) for name, value in parameters.items()}
    for _ in range(len(substitutions) + 1):
        updated = {key: sp.simplify(value.subs(substitutions)) for key, value in substitutions.items()}
        if updated == substitutions:
            break
        substitutions = updated
    symbolic = sp.sympify(expression, locals=table).subs(substitutions)
    remaining = symbolic.free_symbols - {table["s"]}
    if remaining:
        raise RegistryCrosscheckError(f"unresolved registry symbols: {sorted(map(str, remaining))}")
    function = sp.lambdify(table["s"], symbolic, modules="numpy")
    values = np.asarray(function(1j * 2 * np.pi * frequencies), dtype=complex)
    return np.full(frequencies.shape, values, dtype=complex) if values.ndim == 0 else values


def _physics_values(linearization: dict[str, Any], frequencies: np.ndarray, period: float) -> np.ndarray:
    numerator = np.asarray(linearization["target"]["numerator"], dtype=float)
    denominator = np.asarray(linearization["target"]["denominator"], dtype=float)
    z = np.exp(1j * 2.0 * np.pi * frequencies * period)
    return np.polyval(numerator, z) / np.polyval(denominator, z)


def _yan_structural_check(model_id: str, linearization: dict[str, Any]) -> dict[str, Any]:
    formula_ids = sorted(
        formula_id for formula_id, formula in load_registry()["formulas"].items()
        if formula.get("source_model_id") == model_id
    )
    sideband = linearization["within_cycle_response"]
    status = "PASS" if formula_ids and sideband.get("converged") else "FAIL"
    return {
        "code": "REGISTRY_TREND_SIDEBAND_STRUCTURE", "status": status,
        "comparison_kind": "formula-trend-valid-band-and-sideband-structure",
        "formula_ids": formula_ids, "sideband_converged": sideband.get("converged"),
        "selected_max_M": sideband.get("selected_max_M"),
        "note": "Yan formulas are structural cross-check evidence; the physical Poincare model remains authoritative.",
    }


def run_registry_crosscheck(
    checker: dict[str, Any], linearization: dict[str, Any], orbit: dict[str, Any],
    physics_spec: dict[str, Any],
) -> dict[str, Any]:
    verify_physics_workflow(checker, expected_state="PHYSICS_CHECKERS", predecessor=linearization)
    verify_physics_workflow(physics_spec, expected_state="PHYSICS_SPEC_CONFIRMED")
    physical_provenance = linearization["physical_provenance"]
    if physical_provenance["physics_spec_sha256"] != physics_spec["workflow"]["artifact_sha256"]:
        raise RegistryCrosscheckError("physics spec does not match the Hybrid Linearization provenance")
    config = physics_spec.get("registry_crosscheck")
    checks: list[dict[str, Any]] = []
    provenance: dict[str, Any] = {"authority": "cross-check-only", "may_replace_physics_model": False}
    comparison_rows: list[dict[str, Any]] = []
    if not config:
        status = "NOT_APPLICABLE"
        checks.append({"code": "REGISTRY_CROSSCHECK", "status": "NOT_APPLICABLE", "reason": "no matched registry model declared"})
    else:
        model_id = str(config["model_id"])
        provenance["model_id"] = model_id
        if model_id.startswith("yan-2022-"):
            checks.append(_yan_structural_check(model_id, linearization))
        else:
            parameters = copy.deepcopy(config["parameters"])
            approximation = str(config.get("approximation", "exact"))
            case = generate_case(model_id, parameters, approximation)
            parameter_match = _validate_parameter_match(
                case["parameters"], physical_provenance, physics_spec, orbit
            )
            target = physics_spec["target"]["name"]
            if case.get("interface") == "direct-transfer-function":
                if target not in case.get("paper_model", {}):
                    raise RegistryCrosscheckError(f"{model_id} does not register target {target}")
                expression = case["paper_model"][target]
            else:
                case["targets"] = [target]
                if config.get("feedback") is not None:
                    case["feedback"] = copy.deepcopy(config["feedback"])
                model = derive_model(case)
                if target not in model["evaluated"]:
                    raise RegistryCrosscheckError(f"{model_id} does not derive target {target}")
                expression = str(model["evaluated"][target])
            period = float(orbit["events"][-1]["time"])
            fs = 1.0 / period
            registered_max = float(case.get("valid_frequency", {}).get("max_hz", fs / 2.0))
            minimum = float(config.get("valid_min_hz", max(1.0, fs / 1000.0)))
            maximum = min(float(config.get("valid_max_hz", registered_max)), registered_max, fs / 2.0)
            if maximum <= minimum:
                raise RegistryCrosscheckError("registry comparison frequency band is empty")
            baseband_rows = [
                row for row in linearization["continuous_baseband_response"]
                if minimum <= float(row["frequency_hz"]) <= maximum
            ]
            if len(baseband_rows) < 2:
                raise RegistryCrosscheckError("at least two continuous-baseband probes must overlap the registry band")
            frequencies = np.asarray([row["frequency_hz"] for row in baseband_rows], dtype=float)
            physical = np.asarray([
                complex(row["response"]["real"], row["response"]["imag"]) for row in baseband_rows
            ], dtype=complex)
            registered = _evaluate(expression, case["parameters"], frequencies)
            comparison_kind = str(config.get("comparison_kind", "absolute-transfer"))
            normalization = None
            if comparison_kind == "normalised-trend":
                if abs(physical[0]) <= np.finfo(float).tiny or abs(registered[0]) <= np.finfo(float).tiny:
                    raise RegistryCrosscheckError("trend normalisation reference is zero")
                normalization = {
                    "frequency_hz": float(frequencies[0]),
                    "physics_reference": {"real": float(physical[0].real), "imag": float(physical[0].imag)},
                    "registry_reference": {"real": float(registered[0].real), "imag": float(registered[0].imag)},
                }
                physical = physical / physical[0]
                registered = registered / registered[0]
            elif comparison_kind != "absolute-transfer":
                raise RegistryCrosscheckError(f"unknown comparison_kind {comparison_kind}")
            ratio = physical / registered
            magnitude_error = np.abs(20.0 * np.log10(np.maximum(np.abs(ratio), np.finfo(float).tiny)))
            phase_error = np.abs(np.degrees(np.angle(ratio)))
            max_db, max_phase = float(np.max(magnitude_error)), float(np.max(phase_error))
            for index, frequency in enumerate(frequencies):
                comparison_rows.append({
                    "frequency_hz": float(frequency),
                    "physics_magnitude_db": float(20 * np.log10(max(abs(physical[index]), np.finfo(float).tiny))),
                    "registry_magnitude_db": float(20 * np.log10(max(abs(registered[index]), np.finfo(float).tiny))),
                    "magnitude_error_db": float(magnitude_error[index]),
                    "phase_error_deg": float(phase_error[index]),
                })
            checks.append({
                "code": "REGISTRY_BENCHMARK_DEVIATION",
                "status": "PASS" if max_db <= 3.0 and max_phase <= 15.0 else "FAIL",
                "max_magnitude_error_db": max_db, "max_phase_error_deg": max_phase,
                "limits": {"magnitude_db": 3.0, "phase_deg": 15.0},
                "valid_frequency_hz": [minimum, maximum], "points": len(frequencies),
                "comparison_kind": comparison_kind, "normalization": normalization,
            })
            provenance.update({
                "approximation": approximation, "expression": expression,
                "formula_bindings": case.get("formula_bindings", []),
                "registry_valid_frequency": case.get("valid_frequency"),
                "comparison_kind": comparison_kind,
                "parameter_match": parameter_match,
            })
        status = "PASS" if all(item.get("status") in {"PASS", "NOT_APPLICABLE"} for item in checks) else "FAIL"

    overrides = []
    override_map = {item["check_code"]: item for item in physics_spec.get("overrides", [])}
    for check in checks:
        if check.get("status") == "FAIL" and check.get("code") == "REGISTRY_BENCHMARK_DEVIATION":
            override = override_map.get("REGISTRY_BENCHMARK_DEVIATION")
            if override:
                check["status"] = "OVERRIDDEN"
                check["override"] = copy.deepcopy(override)
                overrides.append(copy.deepcopy(override))
    if overrides:
        status = "PASS"
        validation_status = "FORCED_PHYSICS_OVERRIDE_UNVERIFIED"
    else:
        validation_status = checker["validation_status"]
    artifact = {
        "crosscheck_version": "0.5", "case_id": checker["case_id"],
        "physics_checker_sha256": checker["workflow"]["artifact_sha256"],
        "status": status, "validation_status": validation_status,
        "checks": checks, "comparison": comparison_rows, "provenance": provenance,
        "overrides": overrides,
        "authority_statement": "Registered formulas independently cross-check formula, trend, band, or sideband behaviour; they never replace the confirmed-circuit physical derivation.",
    }
    artifact = attach_physics_workflow(artifact, state="REGISTRY_CROSSCHECK", predecessor=checker)
    validate_artifact(artifact, "registry_crosscheck.schema.json")
    return artifact
