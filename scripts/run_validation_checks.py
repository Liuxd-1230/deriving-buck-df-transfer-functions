#!/usr/bin/env python3
"""Aggregate v0.4.4 validation checks into one checker_result artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from check_forbidden_claims import scan_forbidden_claims
from check_power_stage_dynamics import diagnose_expression
from check_rc_memory_factor import check_rc_memory_factor
from model_applicability import check_model_applicability
from formula_registry import model_specs
from validation_policy import check_reference_claims, normalization_decision, validate_power_stage_claim


REQUIRED_CHECKS = (
    "preflight_intake",
    "model_classification",
    "model_applicability",
    "proof_object_check",
    "formula_consistency",
    "normalization_check",
    "power_stage_dynamics_check",
    "mismatch_report_check",
    "forbidden_claim_check",
    "rc_memory_factor_check",
    "validation_policy_check",
)


def _check(status: str, reason: str, *, blocking: bool, artifact: str) -> dict[str, Any]:
    return {"status": status, "reason": reason, "blocking": blocking, "artifact": artifact}


def _validation_level(classification: dict[str, Any] | None, proof: dict[str, Any] | None) -> str | None:
    if isinstance(classification, dict) and classification.get("validation_level"):
        return str(classification["validation_level"])
    validation = proof.get("validation") if isinstance(proof, dict) else None
    if isinstance(validation, dict):
        return validation.get("level")
    return None


def _overall(checks: dict[str, dict[str, Any]]) -> tuple[str, bool]:
    blocking = any(item.get("status") == "FAIL" and item.get("blocking") for item in checks.values())
    if blocking:
        return "FAIL", True
    if any(item.get("status") == "WARN" for item in checks.values()):
        return "WARN", False
    return "PASS", False


def build_unified_checker_result(
    *,
    intake: dict[str, Any] | None = None,
    classification: dict[str, Any] | None = None,
    proof: dict[str, Any] | None = None,
    derivation: dict[str, Any] | None = None,
    mismatch_report: dict[str, Any] | None = None,
    report_text: str | None = None,
    derivation_check: dict[str, Any] | None = None,
    formula_metadata: dict[str, Any] | None = None,
    target_semantics: dict[str, Any] | None = None,
    claims: list[str] | None = None,
) -> dict[str, Any]:
    intake = intake or {}
    classification = classification or {}
    proof = proof or {}
    derivation = derivation or {}
    claims = claims or []
    checks: dict[str, dict[str, Any]] = {}

    intake_status = intake.get("status")
    if intake_status == "INCOMPLETE":
        checks["preflight_intake"] = _check("FAIL", "incomplete intake cannot enter derivation", blocking=True, artifact="intake_status.json")
    elif intake_status:
        checks["preflight_intake"] = _check("PASS", "intake artifact is complete or intentionally supplied", blocking=True, artifact="intake_status.json")
    else:
        checks["preflight_intake"] = _check("NOT_APPLICABLE", "intake artifact not provided", blocking=False, artifact="intake_status.json")

    path = classification.get("path")
    checks["model_classification"] = _check(
        "PASS" if path else "NOT_APPLICABLE",
        f"classification path={path}" if path else "classification artifact not provided",
        blocking=bool(path),
        artifact="classification.json",
    )

    model_id = classification.get("model_id")
    normalized = intake.get("normalized") if isinstance(intake.get("normalized"), dict) else {}
    if model_id in model_specs():
        applicability = check_model_applicability(normalized or proof.get("intake", {}).get("normalized", {}), model_specs()[model_id])
        checks["model_applicability"] = _check(
            applicability["status"],
            "; ".join(applicability.get("errors") or ["registered model applicability checked"]),
            blocking=bool(applicability.get("blocking")),
            artifact="classification.json",
        )
    else:
        checks["model_applicability"] = _check("NOT_APPLICABLE", "no registered model selected", blocking=False, artifact="classification.json")

    if derivation_check:
        status = "PASS" if derivation_check.get("status") == "PASS" else "FAIL"
        checks["proof_object_check"] = _check(status, "; ".join(derivation_check.get("errors") or ["proof and derivation checks passed"]), blocking=status == "FAIL", artifact="proof_object.json")
        checks["formula_consistency"] = _check(status, "; ".join(derivation_check.get("errors") or ["formula consistency passed"]), blocking=status == "FAIL", artifact="checker_result.json")
    else:
        checks["proof_object_check"] = _check("NOT_APPLICABLE", "proof checker artifact not provided", blocking=False, artifact="proof_object.json")
        checks["formula_consistency"] = _check("NOT_APPLICABLE", "formula checker artifact not provided", blocking=False, artifact="formula_origin.json")

    normalization = normalization_decision(formula_metadata=formula_metadata or {}, target_semantics=target_semantics or {})
    checks["normalization_check"] = _check(
        "FAIL" if normalization["status"] == "NORMALIZATION_AMBIGUOUS" else "PASS",
        normalization["reason"],
        blocking=bool(normalization["blocking"]),
        artifact="formula_origin.json",
    )

    expression = str(derivation.get("expanded_target_expression") or (proof.get("transfer") or {}).get("expression") or "")
    target = str(derivation.get("target_transfer") or (proof.get("transfer") or {}).get("target_transfer") or "")
    if expression and target:
        diagnosis = diagnose_expression(target, expression, approximation_declared="LOW_ORDER_APPROXIMATION" in str(derivation))
        power = validate_power_stage_claim(diagnosis | {"claims": claims})
        checks["power_stage_dynamics_check"] = _check(power["status"], "; ".join(power.get("errors") or [diagnosis["diagnosis"]]), blocking=bool(power["blocking"]), artifact="derivation.json")
    else:
        checks["power_stage_dynamics_check"] = _check("NOT_APPLICABLE", "no target expression provided", blocking=False, artifact="derivation.json")

    mismatch_policy = check_reference_claims({
        "final_classification": (mismatch_report or {}).get("final_classification"),
        "claims": claims + list((mismatch_report or {}).get("forbidden_claims") or []),
    })
    checks["mismatch_report_check"] = _check(
        mismatch_policy["status"],
        "; ".join(mismatch_policy.get("errors") or ["mismatch semantics do not block claims"]),
        blocking=bool(mismatch_policy["blocking"]),
        artifact="mismatch_report.json",
    )

    forbidden = scan_forbidden_claims(report_text or "", validation_level=_validation_level(classification, proof))
    checks["forbidden_claim_check"] = _check(
        forbidden["status"],
        "; ".join(forbidden.get("matches") or ["no forbidden wording at current validation level"]),
        blocking=bool(forbidden["blocking"]),
        artifact="report.md",
    )

    rc_source = normalized or proof
    rc = check_rc_memory_factor(rc_source)
    checks["rc_memory_factor_check"] = _check(rc["status"], rc["reason"], blocking=bool(rc["blocking"]), artifact=rc["artifact"])

    checks["validation_policy_check"] = _check(
        "PASS",
        "validation downgrade and claim policy applied",
        blocking=False,
        artifact="classification.json",
    )

    status, blocking = _overall(checks)
    errors = [f"{name}: {item['reason']}" for name, item in checks.items() if item["status"] == "FAIL"]
    warnings = [f"{name}: {item['reason']}" for name, item in checks.items() if item["status"] == "WARN"]
    return {
        "checker_version": "0.4.4",
        "status": status,
        "blocking": blocking,
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
    }


def _load(path: str | None) -> dict[str, Any] | None:
    if not path:
        return None
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run unified v0.4.4 validation checks.")
    parser.add_argument("--intake-status")
    parser.add_argument("--classification")
    parser.add_argument("--proof-object")
    parser.add_argument("--derivation")
    parser.add_argument("--mismatch-report")
    parser.add_argument("--report")
    parser.add_argument("--out")
    args = parser.parse_args()
    result = build_unified_checker_result(
        intake=_load(args.intake_status),
        classification=_load(args.classification),
        proof=_load(args.proof_object),
        derivation=_load(args.derivation),
        mismatch_report=_load(args.mismatch_report),
        report_text=Path(args.report).read_text(encoding="utf-8") if args.report else None,
    )
    if args.out:
        Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
