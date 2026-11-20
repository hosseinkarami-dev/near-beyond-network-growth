"""Run the complete data pipeline: fetch, normalize, then build analytics."""

from time import perf_counter

from console_ui import banner, error, stage, success, warning
from fetch import fetch_all, report_fetch_failures
from normalize import normalize_all
from build_analytics import build_all_analytics


def main() -> int:
    """Run stages in order; fetch failures are warnings, later failures are fatal."""

    try:
        banner("Data pipeline", "Fetch  /  Normalize  /  Analytics")
        started = perf_counter()
        stage("Fetch raw data", "downloading and updating sources")
        fetch_failures: list[str] = []
        fetch_ok = fetch_all(failures=fetch_failures)
        stage("Normalize", "validating and shaping raw data")
        normalize_all()
        stage("Build analytics", "aggregating dashboard datasets")
        build_all_analytics()
        elapsed = perf_counter() - started
        report_fetch_failures(fetch_failures)
        if fetch_ok:
            success(f"Pipeline completed in {elapsed:.1f}s")
        else:
            warning(f"Pipeline completed in {elapsed:.1f}s with fetch warnings; available data was processed")
    except KeyboardInterrupt:
        warning("Interrupted by Ctrl+C. Successfully saved data is preserved; run py scripts/main.py again to resume.")
        return 130
    except Exception as exc:
        error("Pipeline stopped unexpectedly", details=f"{type(exc).__name__}: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
