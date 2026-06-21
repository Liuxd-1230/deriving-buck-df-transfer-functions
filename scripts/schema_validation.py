#!/usr/bin/env python3
"""Runtime JSON Schema validation for ESSF artifacts."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas"


class ArtifactSchemaError(ValueError):
    """Raised when an ESSF artifact does not satisfy its schema."""


@lru_cache(maxsize=None)
def load_schema(schema_name: str) -> dict[str, Any]:
    path = SCHEMA_DIR / schema_name
    if path.parent != SCHEMA_DIR or not path.is_file():
        raise ArtifactSchemaError(f"unknown schema {schema_name!r}")
    schema = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return schema


def validate_artifact(artifact: dict[str, Any], schema_name: str) -> None:
    errors = sorted(Draft202012Validator(load_schema(schema_name)).iter_errors(artifact), key=lambda e: list(e.path))
    if errors:
        details = []
        for error in errors[:8]:
            location = ".".join(str(item) for item in error.absolute_path) or "<root>"
            details.append(f"{location}: {error.message}")
        raise ArtifactSchemaError("; ".join(details))

