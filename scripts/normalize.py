"""Run registered parsers against available raw files."""
import json
from decimal import Decimal

from common import PROJECT_ROOT, get_source, raw_path
from atomic_io import atomic_write_text
from data_dirs import clear_directory
from normalization.registry import NORMALIZED_DATA_DIR, PARSER_REGISTRATIONS
from validation import validate_json


def normalize_all():
    clear_directory(NORMALIZED_DATA_DIR, allowed_parent=PROJECT_ROOT / "data")
    success = True
    for registration in PARSER_REGISTRATIONS:
        source = get_source(registration.source)
        source_path = raw_path(source)
        try:
            with source_path.open(encoding=registration.raw_encoding) as raw_file:
                if registration.parse_float_as_decimal:
                    raw_data = json.load(raw_file, parse_float=Decimal)
                else:
                    raw_data = json.load(raw_file)
            outputs = registration.parser(raw_data)
            serialized_outputs = {
                filename: validate_json(document)
                for filename, document in outputs.items()
            }
            for filename, serialized in serialized_outputs.items():
                destination = registration.normalized_directory / filename
                atomic_write_text(destination, serialized)
                print(f"{registration.source}: normalized -> {destination}")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            print(f"{registration.source}: normalization failed: {exc}")
            success = False
    return success


if __name__ == "__main__":
    raise SystemExit(0 if normalize_all() else 1)
