"""Run the complete data pipeline: fetch, normalize, then build analytics."""

from time import perf_counter

from console_ui import banner, console, error, stage, success, warning
from fetch import fetch_all
from normalize import normalize_all
from build_analytics import build_all_analytics


def main() -> int:
    """Run stages in order; fetch failures are warnings, later failures are fatal."""

    banner("NEARscope data pipeline", "Fetch  /  Normalize  /  Analytics")
    started = perf_counter()
    stage("Fetch raw data", "downloading and updating sources")
    fetch_ok = fetch_all()
    stage("Normalize", "validating and shaping raw data")
    normalize_all()
    stage("Build analytics", "aggregating dashboard datasets")
    try:
        build_all_analytics()
    except Exception as exc:
        error(f"Analytics stopped: {type(exc).__name__}: {exc}")
        return 1
    elapsed = perf_counter() - started
    if fetch_ok:
        success(f"Pipeline completed in {elapsed:.1f}s")
    else:
        warning(f"Pipeline completed in {elapsed:.1f}s with fetch warnings; available data was processed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
