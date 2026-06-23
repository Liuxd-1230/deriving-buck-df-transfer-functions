#!/usr/bin/env python3
"""Diagnose whether target expressions include full power-stage dynamics."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


def diagnose_expression(target: str, expression: str, *, approximation_declared: bool = False) -> dict[str, Any]:
    compact = expression.replace(" ", "")
    contains_l = bool(re.search(r"\bL\b", expression))
    second_order = "s**2" in compact and "L" in compact and "C" in compact
    low_order = target in {"Gvc", "Gvg", "Zout", "Tloop"} and not second_order
    if second_order:
        diagnosis = "FULL_POWER_STAGE"
    elif low_order:
        diagnosis = "LOW_ORDER_POWER_STAGE"
    else:
        diagnosis = "UNKNOWN"
    return {
        "target": target,
        "contains_L": contains_l,
        "contains_second_order_power_stage": second_order,
        "uses_low_order_output_impedance": low_order,
        "approximation_declared": approximation_declared,
        "diagnosis": diagnosis,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose power-stage dynamics in a target expression.")
    parser.add_argument("--artifact", required=True)
    args = parser.parse_args()
    artifact = json.loads(Path(args.artifact).read_text(encoding="utf-8"))
    transfer = artifact.get("transfer") or {}
    result = diagnose_expression(
        str(transfer.get("target_transfer", "unknown")),
        str(transfer.get("expression", "")),
        approximation_declared="LOW_ORDER_APPROXIMATION" in str(artifact),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
