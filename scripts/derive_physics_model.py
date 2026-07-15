#!/usr/bin/env python3
"""End-to-end v0.5 confirmed-circuit physical derivation CLI."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from hybrid_linearization import HybridLinearizationError, derive_hybrid_linearization
from hybrid_mna import HybridMNAError, build_mode_dae, validate_physics_spec
from parameter_sensitivity import derive_parameter_sensitivities
from periodic_orbit import solve_periodic_orbit
from physics_checker import load_external_validation, run_physics_checkers, secant_poincare_sweep
from physics_report import render_physics_report
from registry_crosscheck import run_registry_crosscheck
from regularization_diagnostic import run_gmin_rmin_sweep


class PhysicsDerivationError(ValueError):
    """Raised when a hard gate intentionally stops the v0.5 state machine."""


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def derive_physics_case(
    circuit_ir: dict[str, Any], physics_spec: dict[str, Any], output_dir: Path,
    *, external_csv: Path | None = None, external_metadata: Path | None = None,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "circuit_ir.json", circuit_ir)
    _write_json(output_dir / "physics_spec.json", physics_spec)
    validate_physics_spec(physics_spec, circuit_ir)
    try:
        mode_dae = build_mode_dae(circuit_ir, physics_spec)
    except HybridMNAError as exc:
        regularization = physics_spec.get("regularization") or {}
        if exc.code == "FAIL_MODE_DAE_INDEX_OR_TOPOLOGY" and regularization.get("enabled"):
            diagnostic = run_gmin_rmin_sweep(circuit_ir, physics_spec)
            _write_json(output_dir / "regularized_diagnostic.json", diagnostic)
            raise PhysicsDerivationError(
                "nominal MNA is singular; an unverified gmin/rmin diagnostic was written and the authoritative chain stopped"
            ) from exc
        raise
    _write_json(output_dir / "mode_dae.json", mode_dae)
    orbit = solve_periodic_orbit(mode_dae, physics_spec)
    _write_json(output_dir / "periodic_orbit.json", orbit)
    try:
        baseline_linearization = derive_hybrid_linearization(
            mode_dae, orbit, physics_spec, include_within_cycle=False
        )
    except HybridLinearizationError as exc:
        if exc.code == "FAIL_EVENT_NOT_TRANSVERSE":
            diagnostic = secant_poincare_sweep(mode_dae, orbit, physics_spec)
            _write_json(output_dir / "near_grazing_diagnostic.json", diagnostic)
            raise PhysicsDerivationError(
                "near-grazing event: secant Poincare diagnostic written; no epsilon was added to the saltation denominator"
            ) from exc
        raise
    sensitivity_step = float((physics_spec.get("analysis") or {}).get("sensitivity_step", 1e-4))
    sensitivities = derive_parameter_sensitivities(
        circuit_ir, physics_spec, orbit, baseline_linearization, relative_step=sensitivity_step
    )
    linearization = derive_hybrid_linearization(
        mode_dae, orbit, physics_spec, parameter_sensitivities=sensitivities,
        include_within_cycle=True,
    )
    _write_json(output_dir / "hybrid_linearization.json", linearization)
    if (external_csv is None) != (external_metadata is None):
        raise PhysicsDerivationError("external validation requires both CSV data and metadata JSON")
    external = None
    if external_csv is not None and external_metadata is not None:
        external = load_external_validation(external_csv, external_metadata, physics_spec)
    checker = run_physics_checkers(
        mode_dae, orbit, linearization, physics_spec, external_dataset=external
    )
    _write_json(output_dir / "physics_checker_result.json", checker)
    if checker["status"] != "PASS":
        raise PhysicsDerivationError("physics hard gate failed; inspect physics_checker_result.json")
    crosscheck = run_registry_crosscheck(checker, linearization, orbit, physics_spec)
    _write_json(output_dir / "registry_crosscheck.json", crosscheck)
    if crosscheck["status"] == "FAIL":
        raise PhysicsDerivationError("registry benchmark hard gate failed; inspect registry_crosscheck.json or record an explicit override")
    report, manifest = render_physics_report(
        circuit_ir, physics_spec, mode_dae, orbit, linearization, checker, crosscheck
    )
    (output_dir / "report.md").write_text(report, encoding="utf-8")
    _write_json(output_dir / "physics_report_manifest.json", manifest)
    return {
        "circuit_ir": circuit_ir, "physics_spec": physics_spec, "mode_dae": mode_dae,
        "periodic_orbit": orbit, "hybrid_linearization": linearization,
        "physics_checker_result": checker, "registry_crosscheck": crosscheck,
        "report_manifest": manifest,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Derive the v0.5 Hybrid MNA/Poincare Buck model.")
    parser.add_argument("--circuit-ir", required=True)
    parser.add_argument("--physics-spec", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--external-csv")
    parser.add_argument("--external-metadata")
    args = parser.parse_args()
    try:
        circuit_ir = json.loads(Path(args.circuit_ir).read_text(encoding="utf-8"))
        physics_spec = json.loads(Path(args.physics_spec).read_text(encoding="utf-8"))
        result = derive_physics_case(
            circuit_ir, physics_spec, Path(args.out),
            external_csv=Path(args.external_csv) if args.external_csv else None,
            external_metadata=Path(args.external_metadata) if args.external_metadata else None,
        )
        print(json.dumps({
            "status": "PASS", "validation_status": result["registry_crosscheck"]["validation_status"],
            "report": str((Path(args.out) / "report.md").resolve()),
        }, ensure_ascii=False))
        return 0
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=__import__("sys").stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
