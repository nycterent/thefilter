"""Command line interface for newsletter bot."""

import click


@click.group()
def cli() -> None:
    """Entry point for the newsletter bot CLI."""


if __name__ == "__main__":
    cli()
