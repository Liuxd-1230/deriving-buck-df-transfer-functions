#!/usr/bin/env python3
"""Render a checked ESSF derivation; Markdown is presentation, not evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from artifact_workflow import WorkflowError, attach_workflow, verify_workflow


class ReportError(ValueError):
    """Raised when report rendering is attempted before a passing checker."""


def build_report_artifacts(
    derivation: dict[str, Any], checker: dict[str, Any]
) -> tuple[dict[str, Any], str]:
    verify_workflow(derivation, expected_state="DERIVATION")
    verify_workflow(checker, expected_state="CHECKERS", predecessor=derivation)
    if checker.get("status") != "PASS":
        raise ReportError("REPORT requires a passing CHECKERS artifact")

    lines = [
        f"# ESSF sampled-data derivation: {derivation['case_id']}",
        "",
        "> This Markdown is a rendering of hash-linked proof and derivation artifacts; it is not evidence by itself.",
        "",
        "## Registered reasoning chain",
        "",
        "The chain enforces sampling event → left/right limits → Dirichlet sampled value → Fm → pulse/sideband modulator → power-stage coupling → loop/closed-loop target.",
        "",
        "## 12-step Yan sampled-data reasoning",
        "",
        "### Independent derivation path",
        "",
    ]
    for item in derivation.get("reasoning_method", {}).get("independent_derivation_path", []):
        lines.append(f"- {item}")
    lines.extend([
        "",
        "### Registry formula path",
        "",
    ])
    for formula_id in derivation.get("reasoning_method", {}).get("registry_formula_path", []):
        lines.append(f"- `{formula_id}`")
    lines.extend([
        "",
        f"Dual-path check: {derivation.get('reasoning_method', {}).get('dual_path_check', 'not recorded')}.",
        "",
    ])
    for step in derivation["steps"]:
        lines.extend([
            f"### {step['index']}. {step['object']}",
            "",
            f"- `formula_id`: `{step['formula_id']}`",
            f"- Expression: `${step['expression']}$`",
            f"- Provenance: {step['source_equation']}",
            f"- Approximation: `{step['approximation']}`",
            f"- Dimension: `{step['dimension_signature']}`",
            "",
        ])
    target_object = "GPWM" if derivation["target_transfer"] == "Gm" else derivation["target_transfer"]
    lines.extend([
        "## Requested result",
        "",
        f"- Target: `{derivation['target_transfer']}`",
        f"- Response kind: `{derivation.get('response_kind', 'unknown')}`",
        f"- Selected return ratio: `{derivation['selected_loop']}`",
        f"- Target mapping: `{derivation['target_transfer']}={derivation['expressions'][target_object]}`",
        f"- Registered relation: `${derivation['expressions'][target_object]}$`",
        f"- Expanded engineering expression: `${derivation['expanded_target_expression']}$`",
        "",
        "## Approximation and validity",
        "",
        f"Approximation set: `{', '.join(derivation['approximation_policy']['items'])}`.",
        f"Sideband policy: `{json.dumps(derivation['approximation_policy'].get('sideband', {}), ensure_ascii=False, sort_keys=True)}`.",
        f"Validity statement: {derivation['approximation_policy']['valid_frequency']}.",
        "",
        f"Validation level: `{derivation['validation']['level']}`.",
    ])
    markdown = "\n".join(lines) + "\n"
    manifest = {
        "report_version": "0.4",
        "case_id": derivation["case_id"],
        "format": "markdown",
        "markdown_sha256": hashlib.sha256(markdown.encode("utf-8")).hexdigest(),
        "source_derivation_sha256": derivation["workflow"]["artifact_sha256"],
        "source_checker_sha256": checker["workflow"]["artifact_sha256"],
    }
    return (
        attach_workflow(
            manifest,
            state="REPORT",
            intent=derivation["workflow"]["intent"],
            predecessor=checker,
        ),
        markdown,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a checked v0.4 ESSF derivation report.")
    parser.add_argument("--derivation", required=True)
    parser.add_argument("--checker", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args()
    try:
        derivation = json.loads(Path(args.derivation).read_text(encoding="utf-8"))
        checker = json.loads(Path(args.checker).read_text(encoding="utf-8"))
        manifest, markdown = build_report_artifacts(derivation, checker)
        Path(args.out).write_text(markdown, encoding="utf-8")
        Path(args.manifest).write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Wrote report: {Path(args.out).resolve()}")
        return 0
    except (OSError, json.JSONDecodeError, WorkflowError, ReportError, KeyError) as exc:
        print(f"ERROR: {exc}", file=__import__("sys").stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
