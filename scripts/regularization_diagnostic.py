#!/usr/bin/env python3
"""Explicit, permanently unverified numerical diagnostics for singular v0.5 models."""

from __future__ import annotations

from typing import Any

import numpy as np

from hybrid_linearization import derive_hybrid_linearization
from hybrid_mna import build_mode_dae
from periodic_orbit import solve_periodic_orbit


def _candidate_metrics(orbit: dict[str, Any], linearization: dict[str, Any]) -> dict[str, float]:
    numerator = np.asarray(linearization["target"]["numerator"], dtype=float)
    denominator = np.asarray(linearization["target"]["denominator"], dtype=float)
    dc = complex(np.polyval(numerator, 1.0) / np.polyval(denominator, 1.0))
    return {
        "period_s": float(orbit["events"][-1]["time"]),
        "spectral_radius": float(linearization["floquet"]["spectral_radius"]),
        "dc_gain_real": float(dc.real), "dc_gain_imag": float(dc.imag),
    }

def _change(left: dict[str, float], right: dict[str, float]) -> float:
    keys = sorted(left)
    a = np.asarray([left[key] for key in keys], dtype=float)
    b = np.asarray([right[key] for key in keys], dtype=float)
    scale = np.maximum(np.maximum(np.abs(a), np.abs(b)), np.finfo(float).tiny)
    return float(np.max(np.abs(a - b) / scale))


def run_gmin_rmin_sweep(
    circuit_ir: dict[str, Any], physics_spec: dict[str, Any],
    *, schedule: tuple[float, ...] = (1e-3, 1e-4, 1e-5, 1e-6, 1e-7, 1e-8, 1e-9),
) -> dict[str, Any]:
    candidates = []
    previous = None
    for epsilon in schedule:
        try:
            mode_dae = build_mode_dae(circuit_ir, physics_spec, regularization_epsilon=epsilon)
            orbit = solve_periodic_orbit(mode_dae, physics_spec)
            linearization = derive_hybrid_linearization(mode_dae, orbit, physics_spec, include_within_cycle=False)
            metrics = _candidate_metrics(orbit, linearization)
            change = None if previous is None else _change(previous, metrics)
            candidates.append({
                "epsilon": epsilon, "status": "CANDIDATE", "metrics": metrics,
                "change_from_previous": change,
                "gmin_siemens": mode_dae["regularization"]["gmin_siemens"],
                "rmin_ohm": mode_dae["regularization"]["rmin_ohm"],
            })
            previous = metrics
        except (ValueError, np.linalg.LinAlgError) as exc:
            candidates.append({"epsilon": epsilon, "status": "NO_CANDIDATE", "error": str(exc)})
    successful = [item for item in candidates if item["status"] == "CANDIDATE"]
    last_changes = [item["change_from_previous"] for item in successful[-3:] if item["change_from_previous"] is not None]
    converged = len(last_changes) >= 2 and max(last_changes) <= 1e-3
    return {
        "diagnostic_version": "0.5", "kind": "normalised-gmin-rmin-epsilon-sweep",
        "validation_status": "REGULARIZED_DIAGNOSTIC_UNVERIFIED", "converged": converged,
        "schedule": list(schedule), "candidates": candidates,
        "selected_epsilon": successful[-1]["epsilon"] if converged else None,
        "rule": "A converged candidate remains diagnostic and can never be promoted to a verified physical model.",
    }
