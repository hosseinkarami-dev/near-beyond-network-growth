"""Validation helpers for generated JSON output."""

import json
import re
from decimal import Decimal
from uuid import uuid4


def validate_json(document):
    """Serialize a document and verify the result is strict, parseable JSON."""
    try:
        prefix = f"__VALIDATE_DECIMAL_{uuid4().hex}_"
        numbers = {}

        def prepare(value):
            if isinstance(value, Decimal):
                if not value.is_finite():
                    raise ValueError("Decimal values must be finite")
                token = f"{prefix}{len(numbers)}__"
                numbers[token] = format(value, "f")
                return token
            if isinstance(value, dict):
                return {key: prepare(item) for key, item in value.items()}
            if isinstance(value, (list, tuple)):
                return [prepare(item) for item in value]
            return value

        serialized = json.dumps(prepare(document), ensure_ascii=False, indent=2, allow_nan=False)
        pattern = re.compile('"' + re.escape(prefix) + r"\d+__\"")
        serialized = pattern.sub(lambda match: numbers[match.group()[1:-1]], serialized)
        json.loads(serialized, parse_float=Decimal)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid normalized JSON document: {exc}") from exc
    return serialized + "\n"
