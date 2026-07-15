from __future__ import annotations

import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Any

from derive_physics_model import derive_physics_case
from hybrid_linearization import derive_hybrid_linearization
from hybrid_mna import build_mode_dae
from periodic_orbit import solve_periodic_orbit
from physics_checker import run_physics_checkers
from registry_crosscheck import run_registry_crosscheck
from v05_golden_cases import build_golden_case


ROOT = Path(__file__).resolve().parents[1]


@lru_cache(maxsize=1)
def full_v2() -> dict[str, Any]:
    image = ROOT / "examples" / "v05-v2-cot" / "schematic.svg"
    _, circuit, spec = build_golden_case(
        "v2-cot", image_path=image, include_registry_crosscheck=True
    )
    output = Path(tempfile.mkdtemp(prefix="v05-full-v2-"))
    artifacts = derive_physics_case(circuit, spec, output)
    artifacts["output_dir"] = output
    return artifacts


@lru_cache(maxsize=4)
def golden_core(family: str) -> dict[str, Any]:
    if family == "v2-cot":
        return full_v2()
    _, circuit, spec = build_golden_case(family, include_registry_crosscheck=True)
    mode_dae = build_mode_dae(circuit, spec)
    orbit = solve_periodic_orbit(mode_dae, spec)
    dummy_sensitivity = [{
        "parameter": "golden-core-fixture", "category": "test-fixture", "nominal": 1.0,
        "status": "PASS", "normalised_local_sensitivity": {},
    }]
    linearization = derive_hybrid_linearization(
        mode_dae, orbit, spec, parameter_sensitivities=dummy_sensitivity
    )
    checker = run_physics_checkers(mode_dae, orbit, linearization, spec)
    crosscheck = run_registry_crosscheck(checker, linearization, orbit, spec)
    return {
        "circuit_ir": circuit, "physics_spec": spec, "mode_dae": mode_dae,
        "periodic_orbit": orbit, "hybrid_linearization": linearization,
        "physics_checker_result": checker, "registry_crosscheck": crosscheck,
    }
