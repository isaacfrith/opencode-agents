"""Point the ``@champion`` alias at a registered model version.

Promotion is an explicit, reversible step (see
``docs/adr/0002-serving-via-mlflow-champion-alias.md``).

Usage:
    uv run python promote.py                 # promote the latest version
    uv run python promote.py --version 3
"""

from __future__ import annotations

import typer

from churnlib import config, registry

app = typer.Typer(help="Promote a model version to @champion.")


@app.command()
def main(
    version: int = typer.Option(None, help="Version to promote; defaults to latest."),
) -> None:
    target = version if version is not None else registry.latest_version()
    registry.promote(target)
    typer.secho(
        f"@{config.CHAMPION_ALIAS} -> {config.REGISTERED_MODEL} v{target}",
        fg=typer.colors.GREEN,
    )


if __name__ == "__main__":
    app()
