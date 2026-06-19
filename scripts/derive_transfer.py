#!/usr/bin/env python3
"""CLI for the v0.4 ESSF registered derivation stage."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from artifact_workflow import WorkflowError
from formula_registry import FormulaRegistryError
from sampled_derivation import SampledDerivationError, derive_sampled_transfer
from schema_validation import ArtifactSchemaError, validate_artifact


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a hash-linked v0.4 derivation artifact.")
    parser.add_argument("--proof", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    try:
        proof = json.loads(Path(args.proof).read_text(encoding="utf-8"))
        derivation = derive_sampled_transfer(proof)
        validate_artifact(derivation, "derivation.schema.json")
        output = Path(args.out)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(derivation, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Wrote derivation artifact: {output.resolve()}")
        return 0
    except (
        OSError, json.JSONDecodeError, WorkflowError, FormulaRegistryError,
        SampledDerivationError, ArtifactSchemaError,
    ) as exc:
        print(f"ERROR: {exc}", file=__import__("sys").stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
