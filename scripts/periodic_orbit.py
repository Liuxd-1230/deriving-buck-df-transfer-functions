#!/usr/bin/env python3
"""Periodic-orbit shooting for component-derived v0.5 Hybrid MNA models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import sympy as sp
from scipy.linalg import expm
from scipy.integrate import simpson
from scipy.optimize import brentq, root

from physics_workflow import attach_physics_workflow, verify_physics_workflow
from schema_validation import validate_artifact


class PeriodicOrbitError(ValueError):
    """Raised when a confirmed hybrid model has no computable periodic orbit."""

    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass
class RuntimeMode:
    id: str
    A: np.ndarray
    B: np.ndarray
    c: np.ndarray
    Zx: np.ndarray
    Zu: np.ndarray
    z0: np.ndarray
    E: np.ndarray
    descriptor_A: np.ndarray
    descriptor_B: np.ndarray
    descriptor_b: np.ndarray
    basis: np.ndarray


def _runtime_modes(mode_dae: dict[str, Any]) -> dict[str, RuntimeMode]:
    result = {}
    for item in mode_dae["modes"]:
        reduced = item["reduced"]
        result[item["id"]] = RuntimeMode(
            id=item["id"], A=np.asarray(reduced["A"], dtype=float),
            B=np.asarray(reduced["B"], dtype=float), c=np.asarray(reduced["c"], dtype=float),
            Zx=np.asarray(reduced["Zx"], dtype=float), Zu=np.asarray(reduced["Zu"], dtype=float),
            z0=np.asarray(reduced["z0"], dtype=float), E=np.asarray(item["E"], dtype=float),
            descriptor_A=np.asarray(item["A"], dtype=float), descriptor_B=np.asarray(item["B"], dtype=float),
            descriptor_b=np.asarray(item["b"], dtype=float),
            basis=np.asarray(reduced["basis"], dtype=float),
        )
    return result


def affine_flow_matrices(A: np.ndarray, B: np.ndarray, c: np.ndarray, duration: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    n, m = B.shape
    augmented = np.zeros((n + m + 1, n + m + 1), dtype=float)
    augmented[:n, :n] = A
    augmented[:n, n:n + m] = B
    augmented[:n, -1] = c
    transition = expm(augmented * float(duration))
    return transition[:n, :n], transition[:n, n:n + m], transition[:n, -1]


def flow(mode: RuntimeMode, state: np.ndarray, inputs: np.ndarray, duration: float) -> np.ndarray:
    Phi, Gamma, q = affine_flow_matrices(mode.A, mode.B, mode.c, duration)
    return Phi @ state + Gamma @ inputs + q


def reconstruct(mode: RuntimeMode, state: np.ndarray, inputs: np.ndarray) -> np.ndarray:
    return mode.Zx @ state + mode.Zu @ inputs + mode.z0


def _guard_function(
    expression: str, mode: RuntimeMode, variable_names: list[str], input_names: list[str],
    initial: np.ndarray, inputs: np.ndarray,
):
    symbols = {name: sp.Symbol(name) for name in [*variable_names, *input_names, "t"]}
    try:
        symbolic = sp.sympify(expression, locals=symbols)
    except (sp.SympifyError, TypeError) as exc:
        raise PeriodicOrbitError("FAIL_EVENT_EXPRESSION", expression) from exc
    unknown = symbolic.free_symbols - set(symbols.values())
    if unknown:
        raise PeriodicOrbitError("FAIL_EVENT_UNKNOWN_SYMBOL", ",".join(sorted(map(str, unknown))))
    ordered = [symbols[name] for name in [*variable_names, *input_names, "t"]]
    evaluator = sp.lambdify(ordered, symbolic, modules="numpy")

    def evaluate(time: float) -> float:
        state = flow(mode, initial, inputs, time)
        full = reconstruct(mode, state, inputs)
        value = evaluator(*full.tolist(), *inputs.tolist(), float(time))
        return float(np.asarray(value))

    return symbolic, symbols, evaluate


def _guard_time(
    termination: dict[str, Any], mode: RuntimeMode, variable_names: list[str],
    input_names: list[str], initial: np.ndarray, inputs: np.ndarray,
) -> tuple[float, dict[str, Any]]:
    minimum = max(float(termination.get("min_duration", 0.0)), 1e-15)
    maximum = float(termination.get("max_duration", 0.0))
    if maximum <= minimum:
        raise PeriodicOrbitError("FAIL_EVENT_SEARCH_WINDOW", f"{minimum}..{maximum}")
    symbolic, symbols, evaluate = _guard_function(
        str(termination.get("expression", "")), mode, variable_names, input_names, initial, inputs
    )
    direction = int(termination.get("direction", 0))
    times = np.linspace(minimum, maximum, 513)
    previous_t = float(times[0])
    previous = evaluate(previous_t)
    bracket = None
    for current_t in times[1:]:
        current_t = float(current_t)
        current = evaluate(current_t)
        crossed = (previous == 0.0 or current == 0.0 or previous * current < 0.0)
        if direction > 0:
            crossed = crossed and current > previous
        elif direction < 0:
            crossed = crossed and current < previous
        if crossed:
            bracket = (previous_t, current_t)
            break
        previous_t, previous = current_t, current
    if bracket is None:
        raise PeriodicOrbitError("FAIL_EVENT_NOT_FOUND", f"{mode.id}:{termination.get('expression')}")
    event_time = float(brentq(evaluate, bracket[0], bracket[1], xtol=1e-14, rtol=1e-12))
    event_state = flow(mode, initial, inputs, event_time)
    full = reconstruct(mode, event_state, inputs)
    substitutions = {symbols[name]: value for name, value in zip(variable_names, full)}
    substitutions.update({symbols[name]: value for name, value in zip(input_names, inputs)})
    substitutions[symbols["t"]] = event_time
    gradient_z = np.asarray([float(sp.diff(symbolic, symbols[name]).subs(substitutions)) for name in variable_names])
    gradient_u = np.asarray([float(sp.diff(symbolic, symbols[name]).subs(substitutions)) for name in input_names])
    gradient_t = float(sp.diff(symbolic, symbols["t"]).subs(substitutions))
    gradient_x = gradient_z @ mode.Zx
    gradient_u_total = gradient_u + gradient_z @ mode.Zu
    vector = mode.A @ event_state + mode.B @ inputs + mode.c
    denominator = float(gradient_x @ vector + gradient_t)
    return event_time, {
        "expression": str(symbolic), "direction": direction,
        "gradient_x": gradient_x.tolist(), "gradient_u": gradient_u_total.tolist(),
        "gradient_t": gradient_t, "Fdot": denominator,
    }


def _apply_reset(
    state: np.ndarray, inputs: np.ndarray, reset: Any, *, current_mode: RuntimeMode,
    next_mode: RuntimeMode, variable_names: list[str], input_names: list[str],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    n, m = state.size, inputs.size
    if not isinstance(reset, dict) or not reset:
        return state, np.eye(n), np.zeros((n, m)), np.zeros(n)
    assignments = reset.get("assignments")
    if isinstance(assignments, dict):
        size = len(variable_names)
        P = np.eye(size)
        Sfull = np.zeros((size, m))
        rfull = np.zeros(size)
        for name, assignment in assignments.items():
            if name not in variable_names:
                raise PeriodicOrbitError("FAIL_RESET_UNKNOWN_VARIABLE", str(name))
            row = variable_names.index(name)
            if np.linalg.norm(next_mode.basis[row]) <= 1e-12:
                raise PeriodicOrbitError("FAIL_RESET_ALGEBRAIC_ASSIGNMENT", str(name))
            P[row, :] = 0.0
            if isinstance(assignment, dict):
                input_name = assignment.get("input")
                if input_name not in input_names:
                    raise PeriodicOrbitError("FAIL_RESET_UNKNOWN_INPUT", str(input_name))
                Sfull[row, input_names.index(str(input_name))] = float(assignment.get("gain", 1.0))
                rfull[row] = float(assignment.get("offset", 0.0))
            else:
                rfull[row] = float(assignment)
        projection = next_mode.basis.T
        R = projection @ P @ current_mode.Zx
        S = projection @ (P @ current_mode.Zu + Sfull)
        r = projection @ (P @ current_mode.z0 + rfull)
        return R @ state + S @ inputs + r, R, S, r
    R = np.asarray(reset.get("R", np.eye(n)), dtype=float)
    S = np.asarray(reset.get("S", np.zeros((n, m))), dtype=float)
    r = np.asarray(reset.get("r", np.zeros(n)), dtype=float)
    if R.shape != (n, n) or S.shape != (n, m) or r.shape != (n,):
        raise PeriodicOrbitError("FAIL_RESET_SHAPE", f"R{R.shape} S{S.shape} r{r.shape}")
    return R @ state + S @ inputs + r, R, S, r


def simulate_cycle(
    initial: np.ndarray, inputs: np.ndarray, mode_dae: dict[str, Any], physics_spec: dict[str, Any],
    *, keep_samples: bool = False,
) -> tuple[np.ndarray, list[dict[str, Any]], list[dict[str, Any]]]:
    modes = _runtime_modes(mode_dae)
    variable_names = mode_dae["variables"]
    input_names = mode_dae["inputs"]
    state = np.asarray(initial, dtype=float)
    intervals: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    elapsed = 0.0
    sequence = physics_spec["mode_sequence"]
    for index, entry in enumerate(sequence):
        mode = modes[entry["mode"]]
        termination = entry["termination"]
        start = state.copy()
        if termination["type"] == "fixed_duration":
            duration = float(termination["duration"])
            event_meta = {"type": "fixed_duration", "Fdot": None}
        else:
            duration, event_meta = _guard_time(termination, mode, variable_names, input_names, start, inputs)
            event_meta["type"] = "guard"
        end_before_reset = flow(mode, start, inputs, duration)
        next_mode_id = sequence[(index + 1) % len(sequence)]["mode"]
        next_mode = modes[next_mode_id]
        state, R, S, r = _apply_reset(
            end_before_reset, inputs, termination.get("reset"), current_mode=mode,
            next_mode=next_mode, variable_names=variable_names, input_names=input_names,
        )
        left_limit = reconstruct(mode, end_before_reset, inputs)
        right_limit = reconstruct(next_mode, state, inputs)
        samples = []
        if keep_samples:
            for local_time in np.linspace(0.0, duration, 65):
                reduced = flow(mode, start, inputs, float(local_time))
                samples.append({"time": elapsed + float(local_time), "reduced": reduced.tolist(), "full": reconstruct(mode, reduced, inputs).tolist()})
        intervals.append({
            "mode": mode.id, "start_time": elapsed, "duration": duration,
            "start_reduced": start.tolist(), "end_reduced_before_reset": end_before_reset.tolist(),
            "end_reduced": state.tolist(), **({"samples": samples} if keep_samples else {}),
        })
        events.append({
            "index": index, "from_mode": mode.id, "to_mode": next_mode_id,
            "time": elapsed + duration, "local_time": duration, "reset_R": R.tolist(),
            "reset_S": S.tolist(), "reset_offset": r.tolist(),
            "left_limit": left_limit.tolist(), "right_limit": right_limit.tolist(), **event_meta,
        })
        elapsed += duration
    return state, intervals, events


def _initial_reduced_state(mode_dae: dict[str, Any], physics_spec: dict[str, Any]) -> np.ndarray:
    first_mode_id = physics_spec["mode_sequence"][0]["mode"]
    mode = _runtime_modes(mode_dae)[first_mode_id]
    input_names = mode_dae["inputs"]
    inputs = np.asarray([physics_spec["inputs"][name] for name in input_names], dtype=float)
    supplied = physics_spec.get("initial_state") or {}
    variable_names = mode_dae["variables"]
    rows, values = [], []
    offset = mode.Zu @ inputs + mode.z0
    for name, value in supplied.items():
        if name not in variable_names:
            raise PeriodicOrbitError("FAIL_INITIAL_STATE_UNKNOWN_VARIABLE", str(name))
        row = variable_names.index(name)
        rows.append(mode.Zx[row])
        values.append(float(value) - offset[row])
    rank = mode.A.shape[0]
    if len(rows) < rank or np.linalg.matrix_rank(np.asarray(rows)) < rank:
        raise PeriodicOrbitError("ASK_USER_ONLY:INITIAL_STATE", f"need {rank} independent physical state values")
    solution, *_ = np.linalg.lstsq(np.asarray(rows), np.asarray(values), rcond=None)
    return solution


def _descriptor_residual(mode: RuntimeMode, state: np.ndarray, inputs: np.ndarray) -> float:
    full = reconstruct(mode, state, inputs)
    derivative = mode.Zx @ (mode.A @ state + mode.B @ inputs + mode.c)
    residual = mode.E @ derivative - mode.descriptor_A @ full - mode.descriptor_B @ inputs - mode.descriptor_b
    scale = max(1.0, float(np.linalg.norm(mode.E @ derivative)), float(np.linalg.norm(mode.descriptor_A @ full)), float(np.linalg.norm(mode.descriptor_B @ inputs)), float(np.linalg.norm(mode.descriptor_b)))
    return float(np.linalg.norm(residual) / scale)


def _quantity(value: Any, default: float = 0.0) -> float:
    if isinstance(value, dict):
        value = value.get("magnitude", default)
    return float(default if value is None else value)


def _physical_balances(
    mode_dae: dict[str, Any], intervals: list[dict[str, Any]], initial: np.ndarray,
    final: np.ndarray, inputs: np.ndarray,
) -> dict[str, Any]:
    modes = _runtime_modes(mode_dae)
    variables = mode_dae["variables"]
    var_index = {name: index for index, name in enumerate(variables)}
    input_index = {name: index for index, name in enumerate(mode_dae["inputs"])}
    ground = mode_dae["ground_net"]
    components = mode_dae.get("component_inventory", [])

    def node_voltage(full: np.ndarray, net: str) -> float:
        return 0.0 if net == ground else float(full[var_index[f"v_{net}"]])

    def voltage(full: np.ndarray, component: dict[str, Any], p: str = "p", n: str = "n") -> float:
        terminals = component.get("terminals") or {}
        return node_voltage(full, str(terminals[p])) - node_voltage(full, str(terminals[n]))

    first_mode = modes[intervals[0]["mode"]]
    start_full = reconstruct(first_mode, initial, inputs)
    final_full = reconstruct(first_mode, final, inputs)
    stored_start = stored_final = 0.0
    for component in components:
        cid, kind = component.get("id"), component.get("type")
        if kind == "inductor":
            current = var_index.get(f"i_{cid}")
            if current is not None:
                inductance = _quantity(component.get("value"))
                stored_start += 0.5 * inductance * start_full[current] ** 2
                stored_final += 0.5 * inductance * final_full[current] ** 2
        elif kind == "capacitor":
            capacitance = _quantity(component.get("value"))
            stored_start += 0.5 * capacitance * voltage(start_full, component) ** 2
            stored_final += 0.5 * capacitance * voltage(final_full, component) ** 2

    volt_seconds = {component["id"]: 0.0 for component in components if component.get("type") == "inductor"}
    volt_seconds_abs = dict.fromkeys(volt_seconds, 0.0)
    capacitor_charge = {component["id"]: 0.0 for component in components if component.get("type") == "capacitor"}
    capacitor_charge_abs = dict.fromkeys(capacitor_charge, 0.0)
    dissipated_energy = 0.0
    source_absorbed_energy = 0.0
    ideal_switch_energy = 0.0
    mode_energy: list[dict[str, Any]] = []
    for interval in intervals:
        mode = modes[interval["mode"]]
        start = np.asarray(interval["start_reduced"], dtype=float)
        duration = float(interval["duration"])
        grid = np.linspace(0.0, duration, 257)
        series: dict[str, list[float]] = {
            "dissipation": [], "source_absorbed": [], "switch_absorbed": []
        }
        for cid in volt_seconds:
            series[f"vl:{cid}"] = []
        for cid in capacitor_charge:
            series[f"ic:{cid}"] = []
        for local in grid:
            state = flow(mode, start, inputs, float(local))
            full = reconstruct(mode, state, inputs)
            state_dot = mode.A @ state + mode.B @ inputs + mode.c
            full_dot = mode.Zx @ state_dot
            dissipation = source_absorbed = switch_absorbed = 0.0
            for component in components:
                cid, kind = component.get("id"), component.get("type")
                params = component.get("parameters") or {}
                if kind == "resistor":
                    resistance = _quantity(component.get("value"))
                    dissipation += voltage(full, component) ** 2 / resistance
                elif kind == "inductor":
                    current = float(full[var_index[f"i_{cid}"]])
                    resistance = _quantity(params.get("series_resistance"), 0.0)
                    ideal_voltage = voltage(full, component) - resistance * current
                    series[f"vl:{cid}"].append(ideal_voltage)
                    dissipation += resistance * current ** 2
                elif kind == "capacitor":
                    capacitance = _quantity(component.get("value"))
                    terminals = component["terminals"]
                    vp_dot = 0.0 if terminals["p"] == ground else float(full_dot[var_index[f"v_{terminals['p']}"]])
                    vn_dot = 0.0 if terminals["n"] == ground else float(full_dot[var_index[f"v_{terminals['n']}"]])
                    series[f"ic:{cid}"].append(capacitance * (vp_dot - vn_dot))
                elif kind == "current_source":
                    current = _quantity(params.get("dc"), 0.0)
                    input_name = params.get("input")
                    if input_name is not None:
                        current += _quantity(params.get("gain"), 1.0) * inputs[input_index[str(input_name)]]
                    source_absorbed += voltage(full, component) * current
                elif kind in {"voltage_source", "vcvs", "ramp", "lti_block"}:
                    source_absorbed += voltage(full, component) * float(full[var_index[f"i_{cid}"]])
                elif kind == "vccs":
                    terminals = component["terminals"]
                    control = node_voltage(full, terminals["cp"]) - node_voltage(full, terminals["cn"])
                    source_absorbed += voltage(full, component) * _quantity(params.get("gain")) * control
                elif kind in {"ideal_switch", "diode"}:
                    switch_absorbed += voltage(full, component) * float(full[var_index[f"i_{cid}"]])
            series["dissipation"].append(dissipation)
            series["source_absorbed"].append(source_absorbed)
            series["switch_absorbed"].append(switch_absorbed)
        dissipated = float(simpson(series["dissipation"], x=grid))
        source_absorbed = float(simpson(series["source_absorbed"], x=grid))
        switch_absorbed = float(simpson(series["switch_absorbed"], x=grid))
        dissipated_energy += dissipated
        source_absorbed_energy += source_absorbed
        ideal_switch_energy += switch_absorbed
        mode_energy.append({
            "mode": interval["mode"], "duration": duration, "dissipated_j": dissipated,
            "source_absorbed_j": source_absorbed, "ideal_switch_absorbed_j": switch_absorbed,
        })
        for cid in volt_seconds:
            values = np.asarray(series[f"vl:{cid}"])
            volt_seconds[cid] += float(simpson(values, x=grid))
            volt_seconds_abs[cid] += float(simpson(np.abs(values), x=grid))
        for cid in capacitor_charge:
            values = np.asarray(series[f"ic:{cid}"])
            capacitor_charge[cid] += float(simpson(values, x=grid))
            capacitor_charge_abs[cid] += float(simpson(np.abs(values), x=grid))

    stored_delta = stored_final - stored_start
    power_residual = stored_delta + dissipated_energy + source_absorbed_energy + ideal_switch_energy
    power_scale = max(
        abs(stored_delta) + abs(dissipated_energy) + abs(source_absorbed_energy) + abs(ideal_switch_energy),
        np.finfo(float).tiny,
    )
    volt_rows = [{
        "component_id": cid, "volt_seconds": value,
        "scaled_residual": abs(value) / max(volt_seconds_abs[cid], np.finfo(float).tiny),
    } for cid, value in volt_seconds.items()]
    charge_rows = [{
        "component_id": cid, "net_charge_coulomb": value,
        "scaled_residual": abs(value) / max(capacitor_charge_abs[cid], np.finfo(float).tiny),
    } for cid, value in capacitor_charge.items()]
    return {
        "stored_energy_start_j": stored_start, "stored_energy_final_j": stored_final,
        "stored_energy_delta_j": stored_delta, "dissipated_energy_j": dissipated_energy,
        "source_absorbed_energy_j": source_absorbed_energy,
        "ideal_switch_absorbed_energy_j": ideal_switch_energy,
        "power_balance_residual_j": power_residual,
        "power_balance_scaled_residual": abs(power_residual) / power_scale,
        "inductor_volt_second": volt_rows, "capacitor_net_charge": charge_rows,
        "mode_energy": mode_energy,
    }


def solve_periodic_orbit(mode_dae: dict[str, Any], physics_spec: dict[str, Any]) -> dict[str, Any]:
    verify_physics_workflow(mode_dae, expected_state="MODE_DAE", predecessor=physics_spec)
    validate_artifact(mode_dae, "mode_dae.schema.json")
    input_names = mode_dae["inputs"]
    inputs = np.asarray([physics_spec["inputs"][name] for name in input_names], dtype=float)
    guess = _initial_reduced_state(mode_dae, physics_spec)

    def residual(candidate: np.ndarray) -> np.ndarray:
        final, _, _ = simulate_cycle(candidate, inputs, mode_dae, physics_spec)
        return final - candidate

    solved = root(residual, guess, method="hybr", options={"xtol": 1e-11, "maxfev": 1000})
    if not solved.success:
        raise PeriodicOrbitError("FAIL_PERIODIC_ORBIT_NOT_FOUND", str(solved.message))
    initial = np.asarray(solved.x, dtype=float)
    final, intervals, events = simulate_cycle(initial, inputs, mode_dae, physics_spec, keep_samples=True)
    scaled_residual = float(np.linalg.norm(final - initial) / max(1.0, np.linalg.norm(initial)))
    runtime = _runtime_modes(mode_dae)
    dae_residual = max(
        _descriptor_residual(runtime[interval["mode"]], np.asarray(sample["reduced"]), inputs)
        for interval in intervals for sample in interval["samples"]
    )
    variable_names = mode_dae["variables"]
    inductor_indices = [variable_names.index(item["variable"]) for item in mode_dae["energy_states"] if item.get("kind") == "magnetic" and item.get("variable") in variable_names]
    minimum_current = min(
        (sample["full"][index] for interval in intervals for sample in interval["samples"] for index in inductor_indices),
        default=float("nan"),
    )
    physical_balances = _physical_balances(mode_dae, intervals, initial, final, inputs)
    volt_second_residual = max((item["scaled_residual"] for item in physical_balances["inductor_volt_second"]), default=0.0)
    charge_residual = max((item["scaled_residual"] for item in physical_balances["capacitor_net_charge"]), default=0.0)
    power_residual = float(physical_balances["power_balance_scaled_residual"])
    checks = [
        {"code": "PERIODIC_FIXED_POINT_RESIDUAL", "status": "PASS" if scaled_residual <= 1e-7 else "FAIL", "value": scaled_residual, "limit": 1e-7},
        {"code": "SCALED_KCL_KVL_RESIDUAL", "status": "PASS" if dae_residual <= 1e-7 else "FAIL", "value": dae_residual, "limit": 1e-7},
        {"code": "CCM_MINIMUM_CURRENT", "status": "PASS" if np.isnan(minimum_current) or minimum_current > 0 else "FAIL", "value": minimum_current, "limit": 0.0},
        {"code": "INDUCTOR_VOLT_SECOND_BALANCE", "status": "PASS" if volt_second_residual <= 1e-7 else "FAIL", "value": volt_second_residual, "limit": 1e-7},
        {"code": "CAPACITOR_CHARGE_BALANCE", "status": "PASS" if charge_residual <= 1e-7 else "FAIL", "value": charge_residual, "limit": 1e-7},
        {"code": "POWER_ENERGY_BALANCE", "status": "PASS" if power_residual <= 1e-7 else "FAIL", "value": power_residual, "limit": 1e-7},
    ]
    artifact = {
        "orbit_version": "0.5", "case_id": mode_dae["case_id"],
        "mode_dae_sha256": mode_dae["workflow"]["artifact_sha256"],
        "inputs": {name: float(value) for name, value in zip(input_names, inputs)},
        "reduced_state_names": [f"x_reduced_{index}" for index in range(initial.size)],
        "fixed_point": {"initial": initial.tolist(), "final": final.tolist(), "scaled_residual": scaled_residual, "solver_success": True},
        "mode_intervals": intervals, "events": events,
        "balances": {"scaled_kcl_kvl_residual": dae_residual, "minimum_inductor_current": minimum_current, **physical_balances},
        "checks": checks,
    }
    artifact = attach_physics_workflow(artifact, state="PERIODIC_ORBIT", predecessor=mode_dae)
    validate_artifact(artifact, "periodic_orbit.schema.json")
    return artifact
