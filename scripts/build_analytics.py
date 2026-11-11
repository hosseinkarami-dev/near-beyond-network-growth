"""Build analytics datasets from normalized project data."""

import os

from common import PROJECT_ROOT
from data_dirs import clear_directory
from analytics.network import build_network_analytics
from analytics.dashboard import build_dashboard_metadata
from analytics.near_intents import build_near_intents_analytics
from analytics.protocols import build_protocol_analytics
from analytics.tokenomics import build_tokenomics_analytics

ANALYTICS_ROOT = PROJECT_ROOT / "data" / "analytics"


def build_all_analytics() -> None:
    """Rebuild every analytics output after clearing the previous snapshot."""
    clear_directory(ANALYTICS_ROOT, allowed_parent=PROJECT_ROOT / "data")
    build_network_analytics()
    include_synthetic_demo = os.environ.get("NEAR_INCLUDE_SYNTHETIC_DATA", "").lower() in {
        "1", "true", "yes",
    }
    build_tokenomics_analytics(include_synthetic_demo=include_synthetic_demo)
    build_near_intents_analytics()
    build_protocol_analytics()
    build_dashboard_metadata()


if __name__ == "__main__":
    try:
        build_all_analytics()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"network analytics: failure: {exc}")
        raise SystemExit(1) from exc
