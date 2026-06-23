#!/usr/bin/env python3
"""Scan reports for claims forbidden at downgraded validation levels."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from validation_policy import claim_restricted


FORBIDDEN_CLAIMS = [
    "final transfer function",
    "correct transfer function",
    "verified transfer function",
    "paper-grounded",
    "figure reproduced",
    "最终传函",
    "正确传函",
    "已验证传函",
    "论文验证",
    "图像复现",
    "完全正确",
]


def scan_forbidden_claims(text: str, *, validation_level: str | None) -> dict[str, Any]:
    if not claim_restricted(validation_level):
        return {"status": "PASS", "matches": [], "blocking": False}
    lower = text.lower()
    matches = [claim for claim in FORBIDDEN_CLAIMS if claim.lower() in lower]
    return {"status": "PASS" if not matches else "FAIL", "matches": matches, "blocking": bool(matches)}


def _block_math_segments(text: str) -> list[str]:
    return [match.group(1).strip() for match in re.finditer(r"\$\$\s*\n?(.*?)\n?\s*\$\$", text, flags=re.S)]


def _without_block_math(text: str) -> str:
    return re.sub(r"\$\$\s*\n?.*?\n?\s*\$\$", "", text, flags=re.S)


def scan_report_formula_rendering(
    text: str,
    *,
    derivation_steps: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Check that core report formulas are tracked and rendered as Typora block math."""

    derivation_steps = derivation_steps or []
    blocks = _block_math_segments(text)
    matches: list[str] = []
    for step in derivation_steps:
        if not isinstance(step, dict):
            continue
        latex = str(step.get("latex", "")).strip()
        if not latex:
            continue
        if step.get("latex_origin") in {"solver_generated", "registry_binding"} and latex not in blocks:
            return {
                "status": "FAIL",
                "code": "FAIL_FORMULA_NOT_BLOCK_MATH",
                "matches": [latex],
                "blocking": True,
                "reason": "derivation_steps[].latex must be rendered as $$...$$ block math",
            }
    body = _without_block_math(text)
    bare_pattern = re.compile(
        r"(?<![$`])\b(?:Gvc|GVC|Tloop|TLOOP|d_hat|vo_hat)\s*(?:\(\s*s\s*\))?\s*=",
        flags=re.ASCII,
    )
    matches.extend(match.group(0) for match in bare_pattern.finditer(body))
    if matches:
        return {
            "status": "FAIL",
            "code": "FAIL_REPORT_CONTAINS_UNTRACKED_FORMULA",
            "matches": matches,
            "blocking": True,
            "reason": "report contains untracked core formulas outside derivation_steps block math",
        }
    return {
        "status": "PASS",
        "code": "PASS",
        "matches": [],
        "blocking": False,
        "reason": "all tracked core formulas are block-rendered and no untracked bare formulas were found",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan a Markdown report for forbidden validation claims.")
    parser.add_argument("--report", required=True)
    parser.add_argument("--validation-level", required=True)
    args = parser.parse_args()
    result = scan_forbidden_claims(Path(args.report).read_text(encoding="utf-8"), validation_level=args.validation_level)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
