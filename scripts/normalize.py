"""Run registered parsers against available raw files."""

import json
from collections import defaultdict
from decimal import Decimal

from atomic_io import atomic_write_text
from console_ui import console
from data_dirs import clear_directory
from normalization.registry import NORMALIZED_DATA_DIR, PARSER_REGISTRATIONS
from paths import DATA_ROOT
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from sources import get_source, raw_path
from validation import validate_json


def normalize_all() -> bool:
    clear_directory(NORMALIZED_DATA_DIR, allowed_parent=DATA_ROOT)
    registrations_by_source = defaultdict(list)
    for registration in PARSER_REGISTRATIONS:
        registrations_by_source[registration.source].append(registration)

    skipped_sources = 0
    with Progress(
        SpinnerColumn(style="bright_green"), TextColumn("[bold]{task.description}"),
        BarColumn(bar_width=28), "{task.completed}/{task.total}", TimeElapsedColumn(),
        console=console, transient=False,
    ) as progress:
        task = progress.add_task("Normalizing sources", total=len(registrations_by_source))
        for source_name, registrations in registrations_by_source.items():
            progress.update(task, description=f"Normalizing {source_name}")
            source = get_source(source_name)
            source_path = raw_path(source)
            if not source_path.exists():
                console.print(f"[yellow]![/yellow] {source_name} [dim]raw file unavailable[/dim]")
                skipped_sources += 1
                progress.advance(task)
                continue

            pending_writes = []
            try:
                for registration in registrations:
                    with source_path.open(encoding=registration.raw_encoding) as raw_file:
                        if registration.parse_float_as_decimal:
                            raw_data = json.load(raw_file, parse_float=Decimal)
                        else:
                            raw_data = json.load(raw_file)
                    outputs = registration.parser(raw_data)
                    for filename, document in outputs.items():
                        pending_writes.append((
                            registration.normalized_directory / filename,
                            validate_json(document),
                        ))
            except Exception as exc:
                console.print(
                    f"[yellow]![/yellow] {source_name} "
                    f"[dim]{type(exc).__name__}: {exc}[/dim]"
                )
                skipped_sources += 1
                progress.advance(task)
                continue

            try:
                for destination, serialized in pending_writes:
                    atomic_write_text(destination, serialized)
                    console.print(f"[green]✓[/green] {source_name} [dim]→ {destination.name}[/dim]")
            except OSError as exc:
                console.print(f"[yellow]![/yellow] {source_name} [dim]write failed: {exc}[/dim]")
                skipped_sources += 1
            progress.advance(task)

    console.print(f"[bold]Normalize[/bold] [dim]completed · {skipped_sources} source(s) unavailable[/dim]")
    return True


if __name__ == "__main__":
    raise SystemExit(0 if normalize_all() else 1)
