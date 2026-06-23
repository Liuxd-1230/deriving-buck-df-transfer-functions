#!/usr/bin/env python3
"""Scan reports for claims forbidden at downgraded validation levels."""

from __future__ import annotations

import argparse
import json
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
