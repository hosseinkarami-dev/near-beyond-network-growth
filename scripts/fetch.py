"""Fetch all configured raw API and BigQuery sources."""

from common import fetch_all


def main() -> int:
    """Run the raw data collection phase."""

    return 0 if fetch_all() else 1


if __name__ == "__main__":
    raise SystemExit(main())
