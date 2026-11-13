"""Shared terminal presentation for the data pipeline."""

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()


def banner(title: str, subtitle: str | None = None) -> None:
    body = Text(title, style="bold bright_white")
    if subtitle:
        body.append(f"\n{subtitle}", style="dim")
    console.print(Panel(body, border_style="bright_green", padding=(0, 2)))
    console.print("[dim]First run can take longer while history is collected. Daily API sources current through yesterday are skipped.[/dim]")


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


def error(message: str) -> None:
    console.print(f"[red]ERROR[/red] {message}")
