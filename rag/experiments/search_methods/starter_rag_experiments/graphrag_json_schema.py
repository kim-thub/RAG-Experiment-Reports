"""Validate Microsoft GraphRAG wrapper result envelopes and extract response text."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

GRAPHRAG_RESULT_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
        "method": {"enum": ["local", "global"]},
        "query": {"type": "string", "minLength": 1},
        "response": {"type": "string", "minLength": 1},
    },
    "required": ["method", "query", "response"],
    "additionalProperties": False,
}
Draft202012Validator.check_schema(GRAPHRAG_RESULT_SCHEMA)
_GRAPHRAG_VALIDATOR = Draft202012Validator(GRAPHRAG_RESULT_SCHEMA)


def extract_graphrag_response(payload: object) -> str:
    """Return response text only after validating the GraphRAG result envelope."""
    errors = sorted(_GRAPHRAG_VALIDATOR.iter_errors(payload), key=lambda error: list(error.path))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise ValueError(f"invalid GraphRAG result: {details}")
    response = payload["response"]  # type: ignore[index]
    return response


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="starter-rag-graphrag-extract")
    parser.add_argument("input", type=Path, help="GraphRAG query result JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        print(extract_graphrag_response(payload))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"GraphRAG extraction failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
