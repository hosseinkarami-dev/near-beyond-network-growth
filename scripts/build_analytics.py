"""Build analytics datasets from normalized project data."""

import subprocess
import sys

from analytics.dashboard import build_dashboard_metadata
from analytics.fallbacks import (
    write_empty_intents_snapshot,
    write_empty_network_snapshot,
    write_empty_protocol_snapshots,
    write_empty_tokenomics_snapshot,
)
from analytics.near_intents import build_near_intents_analytics
from analytics.network import build_network_analytics
from analytics.protocols import build_protocol_analytics
from analytics.tokenomics import build_tokenomics_analytics
from console_ui import console, error
from data_dirs import clear_directory
from paths import ANALYTICS_DATA_DIR, DATA_ROOT, PROJECT_ROOT
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

ANALYTICS_ROOT = ANALYTICS_DATA_DIR


def build_all_analytics() -> None:
    """Build every section independently so one unavailable source stays local."""
    clear_directory(ANALYTICS_ROOT, allowed_parent=DATA_ROOT)

    builders = (
        ("network", build_network_analytics, write_empty_network_snapshot),
        ("tokenomics", build_tokenomics_analytics, write_empty_tokenomics_snapshot),
        ("near_intents", build_near_intents_analytics, write_empty_intents_snapshot),
    )
    with Progress(
        SpinnerColumn(style="bright_green"), TextColumn("[bold]{task.description}"),
        BarColumn(bar_width=28), "{task.completed}/{task.total}", TimeElapsedColumn(),
        console=console, transient=False,
    ) as progress:
        task = progress.add_task("Building analytics", total=len(builders) + 3)
        for name, builder, fallback in builders:
            progress.update(task, description=f"Analytics · {name}")
            try:
                builder()
            except Exception as exc:
                console.print(
                    f"[yellow]![/yellow] {name} "
                    f"[dim]unavailable: {type(exc).__name__}: {exc}[/dim]"
                )
                fallback(ANALYTICS_ROOT)
            progress.advance(task)

        progress.update(task, description="Analytics · protocols")
        try:
            build_protocol_analytics()
        except Exception as exc:
            console.print(
                f"[yellow]![/yellow] protocols "
                f"[dim]unavailable: {type(exc).__name__}: {exc}[/dim]"
            )
            write_empty_protocol_snapshots(ANALYTICS_ROOT)
        progress.advance(task)
        progress.update(task, description="Analytics · dashboard metadata")
        build_dashboard_metadata()
        progress.advance(task)

        progress.update(task, description="Dashboard · syncing analytics data")
        command = "npm run sync:data" if sys.platform == "win32" else ["npm", "run", "sync:data"]
        try:
            subprocess.run(
                command,
                cwd=PROJECT_ROOT / "dashboard",
                check=True,
                shell=sys.platform == "win32",
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            error("Dashboard analytics data sync failed", details=f"{type(exc).__name__}: {exc}")
            raise SystemExit(1) from exc
        progress.advance(task)


if __name__ == "__main__":
    try:
        build_all_analytics()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        error("Analytics build failed", details=f"{type(exc).__name__}: {exc}")
        raise SystemExit(1) from exc
