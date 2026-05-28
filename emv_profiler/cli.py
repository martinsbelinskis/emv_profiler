"""CLI entry point for emv_profiler."""

import sys
from pathlib import Path

import click

from emv_profiler.parser import export_csv, parse_profile


def _resolve_profile(path: str) -> str:
    """Return the .profile file path, accepting either a file or a directory."""
    p = Path(path)
    if p.is_dir():
        profiles = sorted(p.glob("*.profile"))
        if not profiles:
            raise click.BadParameter(f"No .profile file found in directory: {path}")
        if len(profiles) > 1:
            names = ", ".join(f.name for f in profiles)
            raise click.BadParameter(f"Multiple .profile files found, specify one: {names}")
        return str(profiles[0])
    return path


@click.group()
@click.version_option()
def main():
    """Parse and inspect MC profiles."""


@main.command()
@click.argument("profile", type=click.Path(exists=True))
@click.option(
    "--output", "-o",
    default="-",
    type=click.Path(),
    help="Output CSV file path (default: stdout).",
)
def parse(profile: str, output: str) -> None:
    """Parse a .profile ZIP (or directory containing one) and export dataElements with non-empty values to CSV."""
    profile = _resolve_profile(profile)
    rows = parse_profile(profile)
    if output == "-":
        export_csv(rows, sys.stdout)
    else:
        with open(output, "w", newline="", encoding="utf-8") as f:
            export_csv(rows, f)
        click.echo(f"Exported {len(rows)} rows to {output}")


@main.command()
def gui() -> None:
    """Launch the graphical interface."""
    from emv_profiler.gui import run_gui
    run_gui()



