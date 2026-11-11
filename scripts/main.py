"""Run the complete data pipeline: fetch, normalize, then build analytics."""

import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PIPELINE_STEPS = (
    ("Fetch raw data", "fetch.py"),
    ("Normalize data", "normalize.py"),
    ("Build analytics", "build_analytics.py"),
)


def main() -> int:
    """Run stages in order; fetch failures are warnings, later failures are fatal."""

    fetch_warnings = False
    for label, script_name in PIPELINE_STEPS:
        script_path = SCRIPT_DIR / script_name
        print(f"\n=== {label} ===", flush=True)
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=SCRIPT_DIR.parent,
            check=False,
        )
        if result.returncode != 0:
            if script_name == "fetch.py":
                fetch_warnings = True
                print(
                    "Fetch completed with source failures; continuing with available raw data."
                )
                continue
            print(f"Pipeline stopped: {label} failed with exit code {result.returncode}.")
            return result.returncode

    if fetch_warnings:
        print("\nPipeline completed with fetch warnings.")
    else:
        print("\nPipeline completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
