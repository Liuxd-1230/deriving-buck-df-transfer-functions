#!/usr/bin/env python3
"""Validate one JSON artifact or every bundled v0.4 benchmark artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from schema_validation import ArtifactSchemaError, validate_artifact
from artifact_workflow import WorkflowError, verify_workflow


def _validate_formula_origin_consistency(formula_origin: dict) -> None:
    ids = formula_origin.get("formula_ids")
    formulas = formula_origin.get("formulas")
    if not isinstance(ids, list) or not isinstance(formulas, list):
        return
    formula_ids = [item.get("formula_id") for item in formulas if isinstance(item, dict)]
    if ids != formula_ids:
        raise ArtifactSchemaError("formula_origin formula_ids must match formulas[].formula_id order")


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
            for benchmark in root.glob("yan_2022_*"):
                intake = json.loads((benchmark / "intake.json").read_text(encoding="utf-8"))
                classification = json.loads((benchmark / "classification.json").read_text(encoding="utf-8"))
                proof = json.loads((benchmark / "proof_object.json").read_text(encoding="utf-8"))
                derivation = json.loads((benchmark / "derivation.json").read_text(encoding="utf-8"))
                checker = json.loads((benchmark / "checker_result.json").read_text(encoding="utf-8"))
                formula_origin = json.loads((benchmark / "formula_origin.json").read_text(encoding="utf-8"))
                report = json.loads((benchmark / "report_manifest.json").read_text(encoding="utf-8"))
                artifacts = (
                    (intake, "intake.schema.json"),
                    (classification, "classification.schema.json"),
                    (proof, "proof_object.schema.json"),
                    (derivation, "derivation.schema.json"),
                    (checker, "checker_result.schema.json"),
                    (formula_origin, "formula_origin.schema.json"),
                    (report, "report_manifest.schema.json"),
                )
                for artifact, schema in artifacts:
                    validate_artifact(artifact, schema)
                    if schema == "formula_origin.schema.json":
                        _validate_formula_origin_consistency(artifact)
                    checked += 1
                verify_workflow(classification, expected_state="MODEL_CLASSIFY", predecessor=intake)
                verify_workflow(proof, expected_state="FORMULA_BINDING", predecessor=classification)
                verify_workflow(derivation, expected_state="DERIVATION", predecessor=proof)
                verify_workflow(checker, expected_state="CHECKERS", predecessor=derivation)
                verify_workflow(report, expected_state="REPORT", predecessor=checker)
            print(json.dumps({"status": "PASS", "checked": checked}, indent=2))
            return 0
        if not args.schema or not args.artifact:
            raise ArtifactSchemaError("--schema and --artifact are required")
        artifact = json.loads(Path(args.artifact).read_text(encoding="utf-8"))
        validate_artifact(artifact, args.schema)
        if args.schema == "formula_origin.schema.json":
            _validate_formula_origin_consistency(artifact)
        print(json.dumps({"status": "PASS", "schema": args.schema}, indent=2))
        return 0
    except (OSError, json.JSONDecodeError, ArtifactSchemaError, WorkflowError) as exc:
        print(json.dumps({"status": "FAIL", "errors": [str(exc)]}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
