#!/usr/bin/env python3
"""Independent switched-time validation and hard gates for v0.5 physics artifacts."""

from __future__ import annotations

import copy
import csv
import json
from pathlib import Path
from typing import Any, Callable

import numpy as np
import sympy as sp
from scipy.integrate import solve_ivp

from periodic_orbit import _runtime_modes, reconstruct
from physics_workflow import attach_physics_workflow, verify_physics_workflow
from schema_validation import validate_artifact


class PhysicsCheckerError(ValueError):
    """Raised when the independent switching simulation cannot execute."""

    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


OVERRIDABLE_INTERNAL_CHECKS = {
    "PERIODIC_FIXED_POINT_RESIDUAL", "SCALED_KCL_KVL_RESIDUAL", "CCM_MINIMUM_CURRENT",
    "INDUCTOR_VOLT_SECOND_BALANCE", "CAPACITOR_CHARGE_BALANCE", "POWER_ENERGY_BALANCE",
    "POINCARE_JACOBIAN_FD", "POINCARE_INPUT_FD", "SIDEBAND_CONVERGENCE",
    "EXTERNAL_SWITCHING_CROSSCHECK",
}


def _compile_guard(
    expression: str, mode: Any, variable_names: list[str], input_names: list[str],
    inputs: np.ndarray,
) -> Callable[[float, np.ndarray], float]:
    symbols = {name: sp.Symbol(name) for name in [*variable_names, *input_names, "t"]}
    try:
        symbolic = sp.sympify(expression, locals=symbols)
    except (sp.SympifyError, TypeError) as exc:
        raise PhysicsCheckerError("FAIL_EVENT_EXPRESSION", expression) from exc
    if symbolic.free_symbols - set(symbols.values()):
        raise PhysicsCheckerError("FAIL_EVENT_UNKNOWN_SYMBOL", expression)
    ordered = [symbols[name] for name in [*variable_names, *input_names, "t"]]
    evaluator = sp.lambdify(ordered, symbolic, modules="numpy")

    def event(local_time: float, state: np.ndarray) -> float:
        full = reconstruct(mode, np.asarray(state, dtype=float), inputs)
        return float(np.asarray(evaluator(*full.tolist(), *inputs.tolist(), float(local_time))))

    return event


def _integrate(
    mode: Any, state: np.ndarray, inputs: np.ndarray, start: float, stop: float,
    *, event: Callable[[float, np.ndarray], float] | None = None, direction: int = 0,
) -> tuple[np.ndarray, float, bool]:
    def rhs(_: float, value: np.ndarray) -> np.ndarray:
        return mode.A @ value + mode.B @ inputs + mode.c

    events = None
    if event is not None:
        event.direction = direction  # type: ignore[attr-defined]
        event.terminal = True  # type: ignore[attr-defined]
        events = event
    duration = max(stop - start, np.finfo(float).eps)
    solved = solve_ivp(
        rhs, (start, stop), np.asarray(state, dtype=float), method="DOP853", events=events,
        rtol=2e-12, atol=2e-14, max_step=duration / 64.0,
    )
    if not solved.success:
        raise PhysicsCheckerError("FAIL_IVP_INTEGRATION", str(solved.message))
    if event is not None and solved.t_events and solved.t_events[0].size:
        return np.asarray(solved.y_events[0][0]), float(solved.t_events[0][0]), True
    return np.asarray(solved.y[:, -1]), float(solved.t[-1]), False


def simulate_cycle_ivp(
    initial: np.ndarray, inputs: np.ndarray, mode_dae: dict[str, Any], physics_spec: dict[str, Any],
) -> np.ndarray:
    """Evaluate one Poincare map using solve_ivp, independently of exact affine flow code."""
    modes = _runtime_modes(mode_dae)
    state = np.asarray(initial, dtype=float)
    sequence = physics_spec["mode_sequence"]
    for entry_index, entry in enumerate(sequence):
        mode = modes[entry["mode"]]
        termination = entry["termination"]
        if termination["type"] == "fixed_duration":
            state, _, _ = _integrate(mode, state, inputs, 0.0, float(termination["duration"]))
        else:
            minimum = max(float(termination.get("min_duration", 0.0)), 1e-15)
            maximum = float(termination["max_duration"])
            state, _, _ = _integrate(mode, state, inputs, 0.0, minimum)
            event = _compile_guard(
                str(termination["expression"]), mode, mode_dae["variables"], mode_dae["inputs"], inputs
            )
            state, _, found = _integrate(
                mode, state, inputs, minimum, maximum, event=event,
                direction=int(termination.get("direction", 0)),
            )
            if not found:
                raise PhysicsCheckerError("FAIL_EVENT_NOT_FOUND_IVP", f"{mode.id}:{termination['expression']}")
        reset = termination.get("reset") or {}
        if reset:
            n, m = state.size, inputs.size
            assignments = reset.get("assignments")
            if isinstance(assignments, dict):
                next_entry = sequence[(entry_index + 1) % len(sequence)]
                next_mode = modes[next_entry["mode"]]
                size = len(mode_dae["variables"])
                P = np.eye(size); Sfull = np.zeros((size, m)); rfull = np.zeros(size)
                for name, assignment in assignments.items():
                    row = mode_dae["variables"].index(name)
                    P[row, :] = 0.0
                    if isinstance(assignment, dict):
                        input_name = assignment["input"]
                        Sfull[row, mode_dae["inputs"].index(input_name)] = float(assignment.get("gain", 1.0))
                        rfull[row] = float(assignment.get("offset", 0.0))
                    else:
                        rfull[row] = float(assignment)
                projection = next_mode.basis.T
                R = projection @ P @ mode.Zx
                S = projection @ (P @ mode.Zu + Sfull)
                r = projection @ (P @ mode.z0 + rfull)
            else:
                R = np.asarray(reset.get("R", np.eye(n)), dtype=float)
                S = np.asarray(reset.get("S", np.zeros((n, m))), dtype=float)
                r = np.asarray(reset.get("r", np.zeros(n)), dtype=float)
            state = R @ state + S @ inputs + r
    return state


def finite_difference_poincare(
    fixed_point: np.ndarray, inputs: np.ndarray, mode_dae: dict[str, Any], physics_spec: dict[str, Any],
    *, relative_step: float = 1e-6,
) -> tuple[np.ndarray, np.ndarray]:
    n, m = fixed_point.size, inputs.size
    Ad = np.zeros((n, n))
    Bd = np.zeros((n, m))
    for index in range(n):
        step = relative_step * max(1.0, abs(float(fixed_point[index])))
        plus, minus = fixed_point.copy(), fixed_point.copy()
        plus[index] += step; minus[index] -= step
        Ad[:, index] = (
            simulate_cycle_ivp(plus, inputs, mode_dae, physics_spec)
            - simulate_cycle_ivp(minus, inputs, mode_dae, physics_spec)
        ) / (2.0 * step)
    for index in range(m):
        step = relative_step * max(1.0, abs(float(inputs[index])))
        plus, minus = inputs.copy(), inputs.copy()
        plus[index] += step; minus[index] -= step
        Bd[:, index] = (
            simulate_cycle_ivp(fixed_point, plus, mode_dae, physics_spec)
            - simulate_cycle_ivp(fixed_point, minus, mode_dae, physics_spec)
        ) / (2.0 * step)
    return Ad, Bd


def _relative_matrix_error(analytic: np.ndarray, numerical: np.ndarray) -> float:
    return float(np.linalg.norm(analytic - numerical) / max(np.linalg.norm(analytic), np.linalg.norm(numerical), np.finfo(float).tiny))


def load_external_validation(csv_path: Path, metadata_path: Path, physics_spec: dict[str, Any]) -> dict[str, Any]:
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    required = {"target", "input_port", "output_port", "sign_convention", "operating_point", "source"}
    missing = sorted(required - set(metadata))
    if missing:
        raise PhysicsCheckerError("ASK_USER_ONLY:EXTERNAL_METADATA", ",".join(missing))
    target = physics_spec["target"]
    if metadata["target"] != target["name"] or metadata["input_port"] != target["input"] or metadata["output_port"] != target["output"]:
        raise PhysicsCheckerError("FAIL_EXTERNAL_PORT_SEMANTICS", "target or port mismatch")
    if target["name"] == "Tloop" and not metadata.get("loop_break"):
        raise PhysicsCheckerError("ASK_USER_ONLY:EXTERNAL_LOOP_BREAK", "Tloop dataset")
    operating_point = metadata.get("operating_point")
    if not isinstance(operating_point, dict):
        raise PhysicsCheckerError("ASK_USER_ONLY:EXTERNAL_WORKING_POINT", "operating_point must be an object")
    mismatched = [
        name for name, value in physics_spec["inputs"].items()
        if name not in operating_point or not np.isclose(float(operating_point[name]), float(value), rtol=1e-9, atol=0.0)
    ]
    if mismatched:
        raise PhysicsCheckerError("FAIL_EXTERNAL_WORKING_POINT", ",".join(mismatched))
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    columns = {"frequency_hz", "magnitude_db", "phase_deg"}
    if not rows or not columns.issubset(rows[0]):
        raise PhysicsCheckerError("ASK_USER_ONLY:EXTERNAL_COLUMNS", ",".join(sorted(columns)))
    numeric_rows = [{key: float(row[key]) for key in columns} for row in rows]
    frequencies = [row["frequency_hz"] for row in numeric_rows]
    if any(not np.isfinite(list(row.values())).all() for row in numeric_rows):
        raise PhysicsCheckerError("FAIL_EXTERNAL_NONFINITE_DATA", "frequency/magnitude/phase")
    if any(value <= 0 for value in frequencies) or frequencies != sorted(set(frequencies)):
        raise PhysicsCheckerError("FAIL_EXTERNAL_FREQUENCY_AXIS", "frequencies must be positive, unique, and increasing")
    return {
        "metadata": metadata,
        "rows": numeric_rows,
        "csv_sha256": __import__("hashlib").sha256(csv_path.read_bytes()).hexdigest(),
    }


def _external_check(dataset: dict[str, Any], linearization: dict[str, Any]) -> dict[str, Any]:
    model = linearization["continuous_baseband_response"]
    model_frequency = np.asarray([row["frequency_hz"] for row in model], dtype=float)
    model_magnitude = np.asarray([row["magnitude_db"] for row in model], dtype=float)
    model_phase = np.unwrap(np.radians([row["phase_deg"] for row in model]))
    errors = []
    for row in dataset["rows"]:
        frequency = row["frequency_hz"]
        if frequency < model_frequency[0] or frequency > model_frequency[-1]:
            continue
        coordinate = np.log10(frequency)
        grid = np.log10(model_frequency)
        magnitude = float(np.interp(coordinate, grid, model_magnitude))
        phase = float(np.degrees(np.interp(coordinate, grid, model_phase)))
        phase_error = abs(((phase - row["phase_deg"] + 180.0) % 360.0) - 180.0)
        errors.append((abs(magnitude - row["magnitude_db"]), phase_error))
    if not errors:
        return {"code": "EXTERNAL_SWITCHING_CROSSCHECK", "status": "FAIL", "detail": "no overlapping frequency rows"}
    max_db = max(item[0] for item in errors); max_phase = max(item[1] for item in errors)
    return {
        "code": "EXTERNAL_SWITCHING_CROSSCHECK",
        "status": "PASS" if max_db <= 3.0 and max_phase <= 15.0 else "FAIL",
        "max_magnitude_error_db": max_db, "max_phase_error_deg": max_phase,
        "limits": {"magnitude_db": 3.0, "phase_deg": 15.0}, "points_compared": len(errors),
        "provenance": dataset,
    }


def _apply_overrides(checks: list[dict[str, Any]], physics_spec: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    overrides = {item["check_code"]: item for item in physics_spec.get("overrides", [])}
    used = []
    result = copy.deepcopy(checks)
    for check in result:
        if check.get("status") != "FAIL":
            continue
        code = str(check.get("code"))
        override = overrides.get(code)
        if override is None:
            continue
        if code not in OVERRIDABLE_INTERNAL_CHECKS:
            raise PhysicsCheckerError("FAIL_OVERRIDE_NOT_ALLOWED", code)
        check["status"] = "OVERRIDDEN"
        check["override"] = copy.deepcopy(override)
        used.append(copy.deepcopy(override))
    return result, used


def run_physics_checkers(
    mode_dae: dict[str, Any], orbit: dict[str, Any], linearization: dict[str, Any],
    physics_spec: dict[str, Any], *, external_dataset: dict[str, Any] | None = None,
) -> dict[str, Any]:
    verify_physics_workflow(linearization, expected_state="HYBRID_LINEARIZATION", predecessor=orbit)
    fixed = np.asarray(orbit["fixed_point"]["initial"], dtype=float)
    inputs = np.asarray([orbit["inputs"][name] for name in mode_dae["inputs"]], dtype=float)
    fd_step = float((physics_spec.get("analysis") or {}).get("finite_difference_step", 1e-6))
    fd_Ad, fd_Bd = finite_difference_poincare(fixed, inputs, mode_dae, physics_spec, relative_step=fd_step)
    analytic_Ad = np.asarray(linearization["state_space"]["Ad"], dtype=float)
    analytic_Bd = np.asarray(linearization["state_space"]["Bd"], dtype=float)
    ad_error = _relative_matrix_error(analytic_Ad, fd_Ad)
    bd_error = _relative_matrix_error(analytic_Bd, fd_Bd)
    checks = copy.deepcopy(orbit["checks"])
    checks.extend([
        {"code": "POINCARE_JACOBIAN_FD", "status": "PASS" if ad_error <= 1e-3 else "FAIL", "value": ad_error, "limit": 1e-3},
        {"code": "POINCARE_INPUT_FD", "status": "PASS" if bd_error <= 1e-3 else "FAIL", "value": bd_error, "limit": 1e-3},
        {"code": "SIDEBAND_CONVERGENCE", "status": "PASS" if linearization["within_cycle_response"].get("converged") else "FAIL", "value": linearization["within_cycle_response"].get("selected_max_M"), "limit": linearization["within_cycle_response"].get("limits")},
        {"code": "FLOQUET_STABILITY_OBSERVATION", "status": "INFO", "stable": linearization["floquet"]["stable"], "spectral_radius": linearization["floquet"]["spectral_radius"], "blocking": False},
        {"code": "PARAMETER_SENSITIVITY_COMPLETENESS", "status": "PASS" if linearization.get("parameter_sensitivities") and all(item.get("status") in {"PASS", "NOT_APPLICABLE_ZERO_NOMINAL"} for item in linearization["parameter_sensitivities"]) else "FAIL", "value": len(linearization.get("parameter_sensitivities", [])), "blocking": True},
    ])
    external_passed = False
    if external_dataset is not None:
        external = _external_check(external_dataset, linearization)
        checks.append(external)
        external_passed = external["status"] == "PASS"
    checks, overrides = _apply_overrides(checks, physics_spec)
    blocking = [item for item in checks if item.get("status") == "FAIL"]
    if overrides:
        validation_status = "FORCED_PHYSICS_OVERRIDE_UNVERIFIED"
    elif blocking:
        validation_status = "PHYSICS_DERIVED_INTERNAL_FAILED"
    elif external_passed:
        validation_status = "PHYSICS_DERIVED_EXTERNAL_CROSSCHECKED"
    else:
        validation_status = "PHYSICS_DERIVED_INTERNAL_VALIDATED"
    artifact = {
        "checker_version": "0.5", "case_id": mode_dae["case_id"],
        "hybrid_linearization_sha256": linearization["workflow"]["artifact_sha256"],
        "status": "PASS" if not blocking else "FAIL", "validation_status": validation_status,
        "checks": checks, "overrides": overrides,
        "independent_poincare": {
            "method": "DOP853 solve_ivp switching simulation plus central finite differences",
            "does_not_reuse_affine_flow_or_guard_root": True, "relative_step": fd_step,
            "Ad": fd_Ad.tolist(), "Bd": fd_Bd.tolist(),
            "Ad_relative_error": ad_error, "Bd_relative_error": bd_error,
        },
    }
    artifact = attach_physics_workflow(artifact, state="PHYSICS_CHECKERS", predecessor=linearization)
    validate_artifact(artifact, "physics_checker_result.schema.json")
    return artifact


def secant_poincare_sweep(
    mode_dae: dict[str, Any], orbit: dict[str, Any], physics_spec: dict[str, Any],
    *, schedule: tuple[float, ...] = (1e-3, 1e-4, 1e-5, 1e-6, 1e-7, 1e-8, 1e-9),
) -> dict[str, Any]:
    fixed = np.asarray(orbit["fixed_point"]["initial"], dtype=float)
    inputs = np.asarray([orbit["inputs"][name] for name in mode_dae["inputs"]], dtype=float)
    rows = []
    previous = None
    for step in schedule:
        Ad, Bd = finite_difference_poincare(fixed, inputs, mode_dae, physics_spec, relative_step=step)
        change = None if previous is None else _relative_matrix_error(previous, Ad)
        rows.append({"relative_step": step, "Ad": Ad.tolist(), "Bd": Bd.tolist(), "change_from_previous": change})
        previous = Ad
    finite_changes = [row["change_from_previous"] for row in rows[-3:] if row["change_from_previous"] is not None]
    converged = bool(finite_changes) and max(finite_changes) <= 1e-3
    return {
        "diagnostic_version": "0.5", "kind": "near-grazing-secant-poincare",
        "status": "REGULARIZED_DIAGNOSTIC_UNVERIFIED", "converged": converged,
        "no_saltation_denominator_epsilon": True, "schedule": rows,
    }
