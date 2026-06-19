#!/usr/bin/env python3
"""Validate one JSON artifact or every bundled v0.4 benchmark artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from schema_validation import ArtifactSchemaError, validate_artifact


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate ESSF artifacts with Draft 2020-12 schemas.")
    parser.add_argument("--schema")
    parser.add_argument("--artifact")
    parser.add_argument("--all-benchmarks", action="store_true")
    args = parser.parse_args()
    try:
        if args.all_benchmarks:
            root = Path(__file__).resolve().parents[1] / "benchmarks"
            checked = 0
            for proof in root.glob("yan_2022_*/proof_object.json"):
                validate_artifact(json.loads(proof.read_text(encoding="utf-8")), "proof_object.schema.json")
                checked += 1
            print(json.dumps({"status": "PASS", "checked": checked}, indent=2))
            return 0
        if not args.schema or not args.artifact:
            raise ArtifactSchemaError("--schema and --artifact are required")
        artifact = json.loads(Path(args.artifact).read_text(encoding="utf-8"))
        validate_artifact(artifact, args.schema)
        print(json.dumps({"status": "PASS", "schema": args.schema}, indent=2))
        return 0
    except (OSError, json.JSONDecodeError, ArtifactSchemaError) as exc:
        print(json.dumps({"status": "FAIL", "errors": [str(exc)]}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

