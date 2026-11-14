"""Shared terminal presentation for the data pipeline."""

from datetime import datetime, timezone
import sys
from threading import Lock
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from paths import PROJECT_ROOT

for stream in (sys.stdout, sys.stderr):
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass

console = Console()
ERROR_LOG_PATH = PROJECT_ROOT / "logs" / "errors.log"
_ERROR_LOG_LOCK = Lock()


def banner(title: str, subtitle: str | None = None) -> None:
    body = Text(title, style="bold bright_white")
    if subtitle:
        body.append(f"\n{subtitle}", style="dim")
    console.print(Panel(body, border_style="bright_green", padding=(0, 2)))
    console.print("[dim]First run can take longer while history is collected.[/dim]")


def stage(title: str, detail: str | None = None) -> None:
    label = Text(">  ", style="bright_green")
    label.append(title, style="bold")
    if detail:
        label.append(f"  {detail}", style="dim")
    console.print(label)


def success(message: str) -> None:
    console.print(f"[green]OK[/green] {message}")


def warning(message: str) -> None:
    console.print(f"[yellow]![/yellow] {message}")


def error(message: str, *, details: str | None = None) -> None:
    """Show a concise error and append its full details to the local error log."""

    console.print(f"[red]✗[/red] [bold]{message}[/bold]")
    try:
        timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        with _ERROR_LOG_LOCK:
            ERROR_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with ERROR_LOG_PATH.open("a", encoding="utf-8") as log_file:
                log_file.write(f"[{timestamp}] {message}\n")
                if details:
                    log_file.write(f"{details.rstrip()}\n")
                log_file.write("\n")
        console.print("  [dim]Full error details saved to logs/errors.log[/dim]")
    except OSError as exc:
        console.print(f"  [dim]Could not write error log: {exc}[/dim]")


def dataset_saved(name: str, count: int, path: Path) -> None:
    """Report a saved dataset using a compact repository-relative path."""

    try:
        location = path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        location = path.name
    unit = "record" if count == 1 else "records"
    console.print(
        f"[green]✓[/green] [bold]{name.replace('_', ' ').title()}[/bold] "
        f"[dim]+{count:,} new {unit} · {location}[/dim]"
    )


def dataset_up_to_date(name: str, through: object) -> None:
    """Report that an incremental dataset needs no new request."""

    console.print(
        f"[cyan]↻[/cyan] [bold]{name.replace('_', ' ').title()}[/bold] "
        f"[dim]up to date through {through}; request skipped[/dim]"
    )


def dataset_skipped(name: str, reason: str) -> None:
    """Report an intentional request skip in the shared terminal style."""

    console.print(
        f"[cyan]↷[/cyan] [bold]{name}[/bold] "
        f"[dim]{reason} · request skipped[/dim]"
    )
