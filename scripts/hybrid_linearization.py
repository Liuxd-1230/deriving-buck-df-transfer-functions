#!/usr/bin/env python3
"""Saltation/Poincare linearization and lifted response reconstruction for v0.5."""

from __future__ import annotations

import copy
import math
from typing import Any

import numpy as np
import sympy as sp
from scipy import signal
from scipy.integrate import trapezoid as _TRAPEZOID

from periodic_orbit import _runtime_modes, affine_flow_matrices, reconstruct
from physics_workflow import attach_physics_workflow, verify_physics_workflow
from schema_validation import validate_artifact


class HybridLinearizationError(ValueError):
    """Raised when a periodic hybrid orbit cannot be differentiably linearized."""

    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def _complex(value: complex) -> dict[str, float]:
    return {"real": float(np.real(value)), "imag": float(np.imag(value))}


def _target_scale(physics_spec: dict[str, Any]) -> float:
    return float(physics_spec["target"].get("scale", 1.0))


def _output_gradient(
    expression: str, mode: Any, variable_names: list[str], input_names: list[str],
    state: np.ndarray, inputs: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, float]:
    symbols = {name: sp.Symbol(name) for name in [*variable_names, *input_names]}
    try:
        expr = sp.sympify(expression, locals=symbols)
    except (sp.SympifyError, TypeError) as exc:
        raise HybridLinearizationError("FAIL_OUTPUT_EXPRESSION", expression) from exc
    if expr.free_symbols - set(symbols.values()):
        raise HybridLinearizationError("FAIL_OUTPUT_UNKNOWN_SYMBOL", expression)
    full = reconstruct(mode, state, inputs)
    substitutions = {symbols[name]: value for name, value in zip(variable_names, full)}
    substitutions.update({symbols[name]: value for name, value in zip(input_names, inputs)})
    gradient_z = np.asarray([float(sp.diff(expr, symbols[name]).subs(substitutions)) for name in variable_names])
    gradient_u = np.asarray([float(sp.diff(expr, symbols[name]).subs(substitutions)) for name in input_names])
    value = float(expr.subs(substitutions))
    return gradient_z @ mode.Zx, gradient_u + gradient_z @ mode.Zu, value


def _event_matrices(
    event: dict[str, Any], current_mode: Any, next_mode: Any,
    end_before_reset: np.ndarray, end_after_reset: np.ndarray, inputs: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, dict[str, Any]]:
    R = np.asarray(event["reset_R"], dtype=float)
    S = np.asarray(event["reset_S"], dtype=float)
    if event["type"] == "fixed_duration":
        return R, S, R, S, {
            "type": "fixed_duration", "Xi": R.tolist(), "Xi_u": S.tolist(),
            "Pi": R.tolist(), "Pi_u": S.tolist(), "Fdot": None,
        }
    gx = np.asarray(event["gradient_x"], dtype=float)
    gu = np.asarray(event["gradient_u"], dtype=float)
    denominator = float(event["Fdot"])
    scale = max(1.0, np.linalg.norm(gx) * np.linalg.norm(current_mode.A @ end_before_reset + current_mode.B @ inputs + current_mode.c))
    if abs(denominator) <= 1e-10 * scale:
        raise HybridLinearizationError("FAIL_EVENT_NOT_TRANSVERSE", f"event {event['index']} Fdot={denominator}")
    f_minus = current_mode.A @ end_before_reset + current_mode.B @ inputs + current_mode.c
    f_plus = next_mode.A @ end_after_reset + next_mode.B @ inputs + next_mode.c
    jump = f_plus - R @ f_minus
    Xi = R + np.outer(jump, gx) / denominator
    Xi_u = S + np.outer(jump, gu) / denominator
    projected_flow = R @ f_minus
    Pi = R - np.outer(projected_flow, gx) / denominator
    Pi_u = S - np.outer(projected_flow, gu) / denominator
    return Pi, Pi_u, Xi, Xi_u, {
        "type": "guard", "expression": event.get("expression"), "Fdot": denominator,
        "gradient_x": gx.tolist(), "gradient_u": gu.tolist(),
        "flow_jump": jump.tolist(), "Xi": Xi.tolist(), "Xi_u": Xi_u.tolist(),
        "Pi": Pi.tolist(), "Pi_u": Pi_u.tolist(),
        "matrix_semantics": {
            "Xi": "saltation at common nominal time",
            "Pi": "event-to-event Poincare endpoint projection after reset",
        },
    }


def _compose_linearization(
    mode_dae: dict[str, Any], orbit: dict[str, Any], physics_spec: dict[str, Any]
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, list[dict[str, Any]], list[tuple[np.ndarray, np.ndarray]]]:
    modes = _runtime_modes(mode_dae)
    inputs = np.asarray([orbit["inputs"][name] for name in mode_dae["inputs"]], dtype=float)
    size = len(orbit["fixed_point"]["initial"])
    Sx = np.eye(size)
    Su = np.zeros((size, len(inputs)))
    Mx = np.eye(size)
    Mu = np.zeros((size, len(inputs)))
    event_details = []
    event_matrices = []
    for index, interval in enumerate(orbit["mode_intervals"]):
        mode = modes[interval["mode"]]
        Phi, Gamma, _ = affine_flow_matrices(mode.A, mode.B, mode.c, interval["duration"])
        Sx = Phi @ Sx
        Su = Phi @ Su + Gamma
        Mx = Phi @ Mx
        Mu = Phi @ Mu + Gamma
        event = orbit["events"][index]
        next_mode = modes[event["to_mode"]]
        before = np.asarray(interval["end_reduced_before_reset"], dtype=float)
        after = np.asarray(interval["end_reduced"], dtype=float)
        Pi, Pi_u, Xi, Xi_u, detail = _event_matrices(event, mode, next_mode, before, after, inputs)
        detail.update({"index": index, "from_mode": mode.id, "to_mode": next_mode.id, "flow_Phi": Phi.tolist(), "flow_Gamma": Gamma.tolist()})
        event_details.append(detail)
        event_matrices.append((Pi, Pi_u))
        Sx = Pi @ Sx
        Su = Pi @ Su + Pi_u
        Mx = Xi @ Mx
        Mu = Xi @ Mu + Xi_u
    return Sx, Su, Mx, Mu, event_details, event_matrices


def _state_space_outputs(
    mode_dae: dict[str, Any], orbit: dict[str, Any], physics_spec: dict[str, Any]
) -> tuple[np.ndarray, np.ndarray, list[str], list[float]]:
    first_mode_id = physics_spec["mode_sequence"][0]["mode"]
    mode = _runtime_modes(mode_dae)[first_mode_id]
    state = np.asarray(orbit["fixed_point"]["initial"], dtype=float)
    inputs = np.asarray([orbit["inputs"][name] for name in mode_dae["inputs"]], dtype=float)
    output_ports = [port for port in mode_dae["ports"] if port.get("role") in {"output", "loop_return"}]
    C, D, names, operating = [], [], [], []
    for port in output_ports:
        c_row, d_row, value = _output_gradient(port["expression"], mode, mode_dae["variables"], mode_dae["inputs"], state, inputs)
        C.append(c_row); D.append(d_row); names.append(port["name"]); operating.append(value)
    if not C:
        raise HybridLinearizationError("FAIL_NO_OUTPUT_PORT", "Circuit IR declares no output port")
    return np.asarray(C), np.asarray(D), names, operating


def _target_model(
    Ad: np.ndarray, Bd: np.ndarray, Cd: np.ndarray, Dd: np.ndarray,
    mode_dae: dict[str, Any], physics_spec: dict[str, Any], output_names: list[str]
) -> tuple[dict[str, Any], int, int]:
    target = physics_spec["target"]
    try:
        input_index = mode_dae["inputs"].index(target["input"])
        output_index = output_names.index(target["output"])
    except ValueError as exc:
        raise HybridLinearizationError("FAIL_TARGET_PORT_NOT_IN_STATE_SPACE", f"{target['input']}->{target['output']}") from exc
    numerator, denominator = signal.ss2tf(Ad, Bd, Cd[[output_index]], Dd[[output_index]], input=input_index)
    numerator = np.trim_zeros(np.asarray(numerator[0], dtype=float), "f")
    denominator = np.trim_zeros(np.asarray(denominator, dtype=float), "f")
    if numerator.size == 0:
        numerator = np.asarray([0.0])
    scale = _target_scale(physics_spec)
    numerator = numerator * scale
    z = sp.Symbol("z")
    z_expr = sp.simplify(
        scale * (sp.Matrix(Cd[[output_index]]) * (z * sp.eye(Ad.shape[0]) - sp.Matrix(Ad)).inv() * sp.Matrix(Bd[:, [input_index]]))[0]
        + scale * Dd[output_index, input_index]
    )
    poles = np.roots(denominator) if denominator.size > 1 else np.asarray([])
    zeros = np.roots(numerator) if numerator.size > 1 else np.asarray([])
    return {
        "name": target["name"], "response_kind": target["response_kind"],
        "input": target["input"], "output": target["output"], "z_expression": str(z_expr),
        "numerator": numerator.tolist(), "denominator": denominator.tolist(),
        "poles": [_complex(value) for value in poles], "zeros": [_complex(value) for value in zeros],
        "authoritative_domain": "z", "scale": scale,
    }, output_index, input_index


def _frequency_response(target: dict[str, Any], period: float, analysis: dict[str, Any]) -> list[dict[str, float]]:
    fs = 1.0 / period
    minimum = float(analysis.get("min_hz", max(1.0, fs / 1000.0)))
    maximum = min(float(analysis.get("max_hz", fs / 2.0)), fs / 2.0)
    points = int(analysis.get("points", 121))
    frequencies = np.geomspace(minimum, maximum, points)
    numerator = np.asarray(target["numerator"], dtype=float)
    denominator = np.asarray(target["denominator"], dtype=float)
    rows = []
    for frequency in frequencies:
        z = np.exp(1j * 2.0 * np.pi * frequency * period)
        response = np.polyval(numerator, z) / np.polyval(denominator, z)
        rows.append({"frequency_hz": float(frequency), "magnitude_db": float(20 * np.log10(max(abs(response), 1e-300))), "phase_deg": float(np.degrees(np.angle(response)))})
    return rows


def _within_cycle_harmonics(
    Ad: np.ndarray, Bd: np.ndarray, mode_dae: dict[str, Any], orbit: dict[str, Any],
    physics_spec: dict[str, Any], output_index: int, input_index: int,
    output_names: list[str], event_matrices: list[tuple[np.ndarray, np.ndarray]],
) -> dict[str, Any]:
    modes = _runtime_modes(mode_dae)
    inputs = np.asarray([orbit["inputs"][name] for name in mode_dae["inputs"]], dtype=float)
    period = float(orbit["events"][-1]["time"])
    fs = 1.0 / period
    analysis = physics_spec.get("analysis") or {}
    probes = np.geomspace(max(1.0, fs / 1000), min(float(analysis.get("max_hz", fs / 2)), fs / 2), int(analysis.get("sideband_probe_points", 9)))
    output_port = next(port for port in mode_dae["ports"] if port.get("name") == output_names[output_index])
    target_scale = _target_scale(physics_spec)
    maximum_m = min(64, int(analysis.get("sideband_max_m", 64)))
    results = []
    overall_converged = True
    selected_max = 3
    for frequency in probes:
        z_cycle = np.exp(1j * 2 * np.pi * frequency * period)
        rhs = Bd[:, input_index]
        state_start = np.linalg.solve(z_cycle * np.eye(Ad.shape[0]) - Ad, rhs).astype(complex)
        times: list[float] = []
        values: list[complex] = []
        elapsed = 0.0
        current = state_start
        for index, interval in enumerate(orbit["mode_intervals"]):
            mode = modes[interval["mode"]]
            nominal_state = np.asarray(interval["start_reduced"], dtype=float)
            c_row, d_row, _ = _output_gradient(output_port["expression"], mode, mode_dae["variables"], mode_dae["inputs"], nominal_state, inputs)
            local_grid = np.linspace(0.0, float(interval["duration"]), 129, endpoint=index == len(orbit["mode_intervals"]) - 1)
            for local in local_grid:
                Phi, Gamma, _ = affine_flow_matrices(mode.A, mode.B, mode.c, float(local))
                perturbation = Phi @ current + Gamma[:, input_index]
                values.append(target_scale * complex(c_row @ perturbation + d_row[input_index]))
                times.append(elapsed + float(local))
            Phi, Gamma, _ = affine_flow_matrices(mode.A, mode.B, mode.c, float(interval["duration"]))
            before_event = Phi @ current + Gamma[:, input_index]
            Xi, Xi_u = event_matrices[index]
            current = Xi @ before_event + Xi_u[:, input_index]
            elapsed += float(interval["duration"])
        t = np.asarray(times)
        h = np.asarray(values)
        coefficients = {}
        for harmonic in range(-maximum_m, maximum_m + 1):
            sideband_angular_frequency = 2 * np.pi * frequency + harmonic * 2 * np.pi / period
            coefficients[harmonic] = _TRAPEZOID(
                h * np.exp(-1j * sideband_angular_frequency * t), t
            ) / period
        previous_sum = None
        selected = maximum_m
        converged = False
        delta_db = float("inf")
        delta_phase = float("inf")
        for candidate in (3, 6, 12, 24, 48, 64):
            if candidate > maximum_m:
                break
            aggregate = sum(coefficients[index] for index in range(-candidate, candidate + 1))
            if previous_sum is not None:
                delta_db = abs(20 * np.log10(max(abs(aggregate), 1e-300) / max(abs(previous_sum), 1e-300)))
                delta_phase = abs(np.degrees(np.angle(aggregate / previous_sum))) if previous_sum != 0 else float("inf")
                if delta_db <= 0.1 and delta_phase <= 1.0:
                    selected, converged = candidate, True
                    break
            previous_sum = aggregate
            selected = candidate
        overall_converged &= converged
        selected_max = max(selected_max, selected)
        baseband = coefficients[0]
        results.append({
            "frequency_hz": float(frequency), "selected_M": selected, "converged": converged,
            "delta_magnitude_db": float(delta_db), "delta_phase_deg": float(delta_phase),
            "baseband": _complex(baseband),
            "baseband_magnitude_db": float(20 * np.log10(max(abs(baseband), 1e-300))),
            "baseband_phase_deg": float(np.degrees(np.angle(baseband))),
            "coefficients": {str(index): _complex(coefficients[index]) for index in range(-selected, selected + 1)},
            "sideband_frequency_hz": {str(index): float(frequency + index * fs) for index in range(-selected, selected + 1)},
        })
    return {
        "method": "piecewise variational reconstruction and Fourier projection",
        "sampling_model_remains_stability_authority": True, "selected_max_M": selected_max,
        "limits": {"magnitude_db": 0.1, "phase_deg": 1.0, "max_M": maximum_m},
        "converged": overall_converged, "probes": results,
    }


def _modal_interpretation(
    Ad: np.ndarray, Bd: np.ndarray, Cd: np.ndarray, mode_dae: dict[str, Any],
    physics_spec: dict[str, Any], output_index: int, input_index: int,
) -> dict[str, Any]:
    values, right = np.linalg.eig(Ad)
    try:
        left_rows = np.linalg.inv(right)
    except np.linalg.LinAlgError:
        return {"status": "UNAVAILABLE_DEFECTIVE_EIGENBASIS", "modes": [], "zeros": []}
    scale = _target_scale(physics_spec)
    first_mode_id = physics_spec["mode_sequence"][0]["mode"]
    first_mode = next(item for item in mode_dae["modes"] if item["id"] == first_mode_id)
    Zx = np.asarray(first_mode["reduced"]["Zx"], dtype=float)
    energy_variables = [
        item.get("variable") for item in mode_dae.get("energy_states", [])
        if item.get("variable") in mode_dae["variables"]
    ]
    rows = []
    for index, value in enumerate(values):
        participation = np.abs(right[:, index] * left_rows[index, :])
        participation /= max(float(np.sum(participation)), np.finfo(float).tiny)
        residue = scale * (Cd[output_index] @ right[:, index]) * (left_rows[index, :] @ Bd[:, input_index])
        physical_amplitudes = {}
        for variable in energy_variables:
            row = mode_dae["variables"].index(str(variable))
            physical_amplitudes[str(variable)] = float(abs(Zx[row] @ right[:, index]))
        normalizer = max(sum(physical_amplitudes.values()), np.finfo(float).tiny)
        physical_amplitudes = {name: value / normalizer for name, value in physical_amplitudes.items()}
        rows.append({
            "multiplier": _complex(value), "magnitude": float(abs(value)),
            "angle_deg": float(np.degrees(np.angle(value))), "residue": _complex(residue),
            "reduced_state_participation": {
                f"x_reduced_{state}": float(participation[state]) for state in range(len(participation))
            },
            "physical_energy_state_amplitude": physical_amplitudes,
            "interpretation_rule": "use participation, residue, and parameter sensitivity together; do not name by pole appearance",
        })
    zero_evidence = physics_spec.get("zero_path_evidence") or []
    return {
        "status": "AVAILABLE", "modes": rows,
        "zero_attribution_policy": "attribute only from an explicit path decomposition",
        "zero_path_evidence": zero_evidence,
        "default_zero_attribution": "UNATTRIBUTED_PATH_EVIDENCE_INSUFFICIENT" if not zero_evidence else "SEE_EXPLICIT_PATH_EVIDENCE",
    }


def derive_hybrid_linearization(
    mode_dae: dict[str, Any], orbit: dict[str, Any], physics_spec: dict[str, Any],
    *, parameter_sensitivities: list[dict[str, Any]] | None = None,
    include_within_cycle: bool = True,
) -> dict[str, Any]:
    verify_physics_workflow(orbit, expected_state="PERIODIC_ORBIT", predecessor=mode_dae)
    validate_artifact(orbit, "periodic_orbit.schema.json")
    Ad, Bd, monodromy_A, monodromy_B, event_details, event_matrices = _compose_linearization(mode_dae, orbit, physics_spec)
    Cd, Dd, output_names, output_operating = _state_space_outputs(mode_dae, orbit, physics_spec)
    target, output_index, input_index = _target_model(Ad, Bd, Cd, Dd, mode_dae, physics_spec, output_names)
    multipliers = np.linalg.eigvals(Ad)
    common_time_multipliers = np.linalg.eigvals(monodromy_A)
    spectral_radius = float(max(abs(multipliers))) if multipliers.size else 0.0
    period = float(orbit["events"][-1]["time"])
    sampled_frequency = _frequency_response(target, period, physics_spec.get("analysis") or {})
    within_cycle = (
        _within_cycle_harmonics(Ad, Bd, mode_dae, orbit, physics_spec, output_index, input_index, output_names, event_matrices)
        if include_within_cycle else {
            "method": "skipped for local parameter perturbation", "converged": None,
            "selected_max_M": None, "limits": {}, "probes": [],
        }
    )
    continuous_baseband = [
        {
            "frequency_hz": item["frequency_hz"],
            "magnitude_db": item["baseband_magnitude_db"],
            "phase_deg": item["baseband_phase_deg"],
            "response": item["baseband"],
        }
        for item in within_cycle.get("probes", [])
    ]
    modal = _modal_interpretation(Ad, Bd, Cd, mode_dae, physics_spec, output_index, input_index)
    z, s = sp.symbols("z s")
    try:
        expression = sp.sympify(target["z_expression"], locals={"z": z})
        low_series = sp.series(expression.subs(z, sp.exp(s * period)), s, 0, 3).removeO()
        low_expression = str(sp.simplify(low_series))
    except (sp.SympifyError, ValueError, NotImplementedError, TypeError, ZeroDivisionError):
        low_expression = "NOT_AVAILABLE"
    artifact = {
        "linearization_version": "0.5", "case_id": mode_dae["case_id"],
        "periodic_orbit_sha256": orbit["workflow"]["artifact_sha256"],
        "physical_provenance": {
            "mode_dae_sha256": mode_dae["workflow"]["artifact_sha256"],
            "physics_spec_sha256": mode_dae["physics_spec_sha256"],
            "variables": copy.deepcopy(mode_dae["variables"]),
            "inputs": copy.deepcopy(mode_dae["inputs"]),
            "ports": copy.deepcopy(mode_dae["ports"]),
            "component_inventory": copy.deepcopy(mode_dae["component_inventory"]),
        },
        "state_space": {"Ad": Ad.tolist(), "Bd": Bd.tolist(), "Cd": Cd.tolist(), "Dd": Dd.tolist(), "inputs": mode_dae["inputs"], "outputs": output_names, "output_operating_point": output_operating, "poincare_section": physics_spec["poincare_section"], "authority": "event-to-event Poincare map"},
        "saltation_monodromy": {
            "A": monodromy_A.tolist(), "B": monodromy_B.tolist(),
            "multipliers": [_complex(value) for value in common_time_multipliers],
            "authority": "common-nominal-time saltation composition; retained as hybrid-event evidence",
        },
        "floquet": {
            "multipliers": [_complex(value) for value in multipliers], "spectral_radius": spectral_radius,
            "stable": spectral_radius < 1.0, "unstable_is_not_derivation_failure": True,
            "stability_authority": "event-to-event Poincare map",
            "ambient_section_projection_may_add_zero_multiplier": True,
        },
        "event_linearization": event_details, "target": target,
        "frequency_response": continuous_baseband if include_within_cycle else sampled_frequency,
        "sampled_frequency_response": sampled_frequency,
        "continuous_baseband_response": continuous_baseband,
        "frequency_response_semantics": {
            "sampled": "target rational response evaluated exactly on z=exp(j*omega*T)",
            "continuous_baseband": "z-resolvent state response lifted through piecewise variational flow and projected at omega",
            "requested_analog_transfer": "continuous_baseband",
        },
        "within_cycle_response": within_cycle,
        "modal_interpretation": modal,
        "low_frequency_approximation": {"method": "z=exp(s*T) Taylor series", "order": 2, "expression": low_expression, "authoritative": False, "valid_frequency": "must be declared below switching-scale dynamics"},
        "parameter_sensitivities": parameter_sensitivities or [],
    }
    artifact = attach_physics_workflow(artifact, state="HYBRID_LINEARIZATION", predecessor=orbit)
    validate_artifact(artifact, "hybrid_linearization.schema.json")
    return artifact
