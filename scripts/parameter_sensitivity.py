#!/usr/bin/env python3
"""Normalised local sensitivities for the confirmed v0.5 physical model."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

import numpy as np

from circuit_ir import circuit_content_hash
from hybrid_linearization import derive_hybrid_linearization
from hybrid_mna import build_mode_dae, physics_spec_content_hash
from periodic_orbit import solve_periodic_orbit
from physics_workflow import canonical_hash


@dataclass(frozen=True)
class ParameterRef:
    name: str
    source: str
    component_id: str | None = None
    sequence_index: int | None = None
    field: str = "value"
    category: str = "declared-parameter"


def _component_number(component: dict[str, Any], field: str) -> float:
    if field == "value":
        value = component.get("value")
        return float(value["magnitude"] if isinstance(value, dict) else value)
    current: Any = component
    for part in field.split("."):
        current = current[part]
    return float(current)


def _set_component_number(component: dict[str, Any], field: str, value: float) -> None:
    if field == "value":
        if isinstance(component.get("value"), dict):
            component["value"]["magnitude"] = value
        else:
            component["value"] = value
        return
    current: Any = component
    parts = field.split(".")
    for part in parts[:-1]:
        current = current[part]
    current[parts[-1]] = value


def _automatic_parameters(circuit_ir: dict[str, Any], physics_spec: dict[str, Any]) -> list[ParameterRef]:
    refs: list[ParameterRef] = []
    for component in circuit_ir["components"]:
        cid, kind = component["id"], component["type"]
        if kind in {"inductor", "capacitor", "resistor"}:
            category = {"inductor": "inductance", "capacitor": "capacitance", "resistor": "resistance"}[kind]
            role = str((component.get("parameters") or {}).get("role", ""))
            if role:
                category = role
            refs.append(ParameterRef(f"{cid}.value", "component", cid, field="value", category=category))
        if kind == "inductor" and "series_resistance" in (component.get("parameters") or {}):
            refs.append(ParameterRef(f"{cid}.series_resistance", "component", cid, field="parameters.series_resistance", category="DCR"))
        if kind == "ramp" and "slope" in (component.get("parameters") or {}):
            refs.append(ParameterRef(f"{cid}.slope", "component", cid, field="parameters.slope", category="ramp"))
        if kind in {"vccs", "vcvs"} and "gain" in (component.get("parameters") or {}):
            refs.append(ParameterRef(f"{cid}.gain", "component", cid, field="parameters.gain", category="sampling-gain"))
    for index, entry in enumerate(physics_spec["mode_sequence"]):
        termination = entry["termination"]
        if termination["type"] == "fixed_duration":
            name = str(termination.get("parameter_name") or ("Ton" if index == 0 else f"duration_{index}"))
            category = "delay" if "delay" in name.lower() else ("Ton" if name == "Ton" else "timing")
            refs.append(ParameterRef(name, "mode_sequence", sequence_index=index, field="termination.duration", category=category))
    return refs


def _explicit_parameters(physics_spec: dict[str, Any]) -> list[ParameterRef]:
    refs = []
    for item in physics_spec.get("sensitivity_parameters", []):
        refs.append(ParameterRef(
            name=str(item["name"]), source=str(item["source"]),
            component_id=item.get("component_id"), sequence_index=item.get("sequence_index"),
            field=str(item.get("field", "value")), category=str(item.get("category", "declared-parameter")),
        ))
    return refs


def discover_parameters(circuit_ir: dict[str, Any], physics_spec: dict[str, Any]) -> list[ParameterRef]:
    explicit = _explicit_parameters(physics_spec)
    refs = explicit or _automatic_parameters(circuit_ir, physics_spec)
    unique = {}
    for ref in refs:
        unique[(ref.source, ref.component_id, ref.sequence_index, ref.field)] = ref
    return list(unique.values())


def _read(ref: ParameterRef, circuit_ir: dict[str, Any], physics_spec: dict[str, Any]) -> float:
    if ref.source == "component":
        component = next(item for item in circuit_ir["components"] if item["id"] == ref.component_id)
        return _component_number(component, ref.field)
    if ref.source == "mode_sequence":
        current: Any = physics_spec["mode_sequence"][int(ref.sequence_index)]
        for part in ref.field.split("."):
            current = current[part]
        return float(current)
    if ref.source == "input":
        return float(physics_spec["inputs"][ref.name])
    raise ValueError(f"unsupported sensitivity source {ref.source}")


def _write(ref: ParameterRef, value: float, circuit_ir: dict[str, Any], physics_spec: dict[str, Any]) -> None:
    if ref.source == "component":
        component = next(item for item in circuit_ir["components"] if item["id"] == ref.component_id)
        _set_component_number(component, ref.field, value)
    elif ref.source == "mode_sequence":
        current: Any = physics_spec["mode_sequence"][int(ref.sequence_index)]
        parts = ref.field.split(".")
        for part in parts[:-1]:
            current = current[part]
        current[parts[-1]] = value
    elif ref.source == "input":
        physics_spec["inputs"][ref.name] = value
    else:
        raise ValueError(f"unsupported sensitivity source {ref.source}")


def _rebind(circuit_ir: dict[str, Any], physics_spec: dict[str, Any]) -> None:
    circuit_ir["confirmation"]["confirmed_content_sha256"] = circuit_content_hash(circuit_ir)
    circuit_ir["workflow"]["artifact_sha256"] = canonical_hash(circuit_ir)
    physics_spec["circuit_ir_sha256"] = circuit_ir["workflow"]["artifact_sha256"]
    physics_spec["workflow"]["predecessor"]["sha256"] = circuit_ir["workflow"]["artifact_sha256"]
    physics_spec["confirmation"]["confirmed_content_sha256"] = physics_spec_content_hash(physics_spec)
    physics_spec["workflow"]["artifact_sha256"] = canonical_hash(physics_spec)


def _metrics(orbit: dict[str, Any], linearization: dict[str, Any]) -> dict[str, Any]:
    numerator = np.asarray(linearization["target"]["numerator"], dtype=float)
    denominator = np.asarray(linearization["target"]["denominator"], dtype=float)
    dc_gain = complex(np.polyval(numerator, 1.0) / np.polyval(denominator, 1.0))
    multipliers = sorted(
        (complex(item["real"], item["imag"]) for item in linearization["floquet"]["multipliers"]),
        key=abs, reverse=True,
    )
    return {
        "period_s": float(orbit["events"][-1]["time"]),
        "spectral_radius": float(linearization["floquet"]["spectral_radius"]),
        "dc_gain": dc_gain,
        "multiplier_magnitudes": np.asarray([abs(value) for value in multipliers], dtype=float),
    }


def _normalised(plus: float, minus: float, baseline: float, relative_step: float) -> float | None:
    if abs(baseline) <= np.finfo(float).tiny:
        return None
    return float((plus - minus) / (2.0 * relative_step * baseline))


def _derive_perturbed(circuit_ir: dict[str, Any], physics_spec: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    mode_dae = build_mode_dae(circuit_ir, physics_spec)
    orbit = solve_periodic_orbit(mode_dae, physics_spec)
    linearization = derive_hybrid_linearization(mode_dae, orbit, physics_spec, include_within_cycle=False)
    return orbit, linearization


def derive_parameter_sensitivities(
    circuit_ir: dict[str, Any], physics_spec: dict[str, Any], baseline_orbit: dict[str, Any],
    baseline_linearization: dict[str, Any], *, relative_step: float = 1e-4,
) -> list[dict[str, Any]]:
    baseline = _metrics(baseline_orbit, baseline_linearization)
    results = []
    for ref in discover_parameters(circuit_ir, physics_spec):
        nominal = _read(ref, circuit_ir, physics_spec)
        if nominal == 0.0:
            results.append({
                "parameter": ref.name, "category": ref.category, "nominal": nominal,
                "status": "NOT_APPLICABLE_ZERO_NOMINAL", "normalised_local_sensitivity": {},
            })
            continue
        derived = []
        failure = None
        for sign in (1.0, -1.0):
            varied_ir, varied_spec = copy.deepcopy(circuit_ir), copy.deepcopy(physics_spec)
            _write(ref, nominal * (1.0 + sign * relative_step), varied_ir, varied_spec)
            _rebind(varied_ir, varied_spec)
            try:
                orbit, linearization = _derive_perturbed(varied_ir, varied_spec)
                derived.append(_metrics(orbit, linearization))
            except (ValueError, np.linalg.LinAlgError) as exc:
                failure = str(exc)
                break
        if failure is not None:
            results.append({
                "parameter": ref.name, "category": ref.category, "nominal": nominal,
                "status": "FAIL_PERTURBATION_SOLVE", "detail": failure,
                "normalised_local_sensitivity": {},
            })
            continue
        plus, minus = derived
        dc_plus, dc_minus, dc_base = plus["dc_gain"], minus["dc_gain"], baseline["dc_gain"]
        count = min(len(plus["multiplier_magnitudes"]), len(minus["multiplier_magnitudes"]), len(baseline["multiplier_magnitudes"]))
        multiplier = [
            _normalised(
                float(plus["multiplier_magnitudes"][index]), float(minus["multiplier_magnitudes"][index]),
                float(baseline["multiplier_magnitudes"][index]), relative_step,
            ) for index in range(count)
        ]
        results.append({
            "parameter": ref.name, "category": ref.category, "nominal": nominal,
            "relative_step": relative_step, "status": "PASS",
            "normalised_local_sensitivity": {
                "period": _normalised(plus["period_s"], minus["period_s"], baseline["period_s"], relative_step),
                "spectral_radius": _normalised(plus["spectral_radius"], minus["spectral_radius"], baseline["spectral_radius"], relative_step),
                "dc_gain_real": _normalised(dc_plus.real, dc_minus.real, dc_base.real, relative_step),
                "dc_gain_imag": _normalised(dc_plus.imag, dc_minus.imag, dc_base.imag, relative_step),
                "floquet_multiplier_magnitudes": multiplier,
            },
            "provenance": {"source": ref.source, "component_id": ref.component_id, "sequence_index": ref.sequence_index, "field": ref.field},
        })
    return results
