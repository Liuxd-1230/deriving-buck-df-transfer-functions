#!/usr/bin/env python3
"""v0.4.5 Typora block-math and derivation-step format checks."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from check_forbidden_claims import scan_report_formula_rendering


class ReportFormatError(ValueError):
    """Raised when report math rendering violates the v0.4.5 contract."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"{code}: {message}")


NATURAL_LANGUAGE_PREFIXES = (
    "Valley comparison:",
    "valley comparison:",
    "Movable",
    "movable",
    "When ",
    "when ",
)


def _looks_like_math(latex: str) -> bool:
    text = latex.strip()
    if not text:
        return False
    if any(text.startswith(prefix) for prefix in NATURAL_LANGUAGE_PREFIXES):
        return False
    if re.search(r"[=+\-*/\\^_{}]", text):
        return True
    if re.search(r"\b(?:frac|hat|sum|prod|int|Delta|delta|omega|Omega)\b", text):
        return True
    return False


def validate_derivation_steps(derivation: dict[str, Any]) -> None:
    steps = derivation.get("derivation_steps")
    if not isinstance(steps, list):
        raise ReportFormatError("FAIL_DERIVATION_STEP_LATEX_NOT_MATH", "derivation_steps must be a list")
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            raise ReportFormatError("FAIL_DERIVATION_STEP_LATEX_NOT_MATH", f"derivation_steps[{index}] must be an object")
        latex = str(step.get("latex", ""))
        if not _looks_like_math(latex):
            raise ReportFormatError(
                "FAIL_DERIVATION_STEP_LATEX_NOT_MATH",
                f"derivation_steps[{index}].latex is not a mathematical expression",
            )
        if step.get("latex_origin") in {"solver_generated", "registry_binding"} and not step.get("source_artifact"):
            raise ReportFormatError(
                "FAIL_DERIVATION_STEP_LATEX_NOT_MATH",
                f"derivation_steps[{index}] lacks source_artifact",
            )


def check_report_markdown_format(text: str, derivation: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    try:
        validate_derivation_steps(derivation)
    except ReportFormatError as exc:
        errors.append(exc.code)
    rendering = scan_report_formula_rendering(
        text,
        derivation_steps=derivation.get("derivation_steps") if isinstance(derivation, dict) else [],
    )
    if rendering.get("status") != "PASS":
        errors.append(str(rendering.get("code", "FAIL_REPORT_CONTAINS_UNTRACKED_FORMULA")))
        bare_formula_scan = scan_report_formula_rendering(text, derivation_steps=[])
        if bare_formula_scan.get("status") != "PASS":
            code = str(bare_formula_scan.get("code", "FAIL_REPORT_CONTAINS_UNTRACKED_FORMULA"))
            if code not in errors:
                errors.append(code)
    return {
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "blocking": bool(errors),
        "rendering": rendering,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check v0.4.5 report Markdown math rendering.")
    parser.add_argument("--report", required=True)
    parser.add_argument("--derivation", required=True)
    args = parser.parse_args()
    try:
        text = Path(args.report).read_text(encoding="utf-8")
        derivation = json.loads(Path(args.derivation).read_text(encoding="utf-8"))
        result = check_report_markdown_format(text, derivation)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["status"] == "PASS" else 1
    except (OSError, json.JSONDecodeError, ReportFormatError) as exc:
        print(json.dumps({"status": "FAIL", "errors": [str(exc)], "blocking": True}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
