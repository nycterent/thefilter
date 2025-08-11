"""Tests for the newsletter bot CLI."""

import pytest
from click.testing import CliRunner
from src.newsletter_bot import cli


def test_cli_group_exists():
    """Test that the CLI group is properly defined."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Newsletter automation bot CLI." in result.output


def test_cli_no_commands_yet():
    """Test CLI with no subcommands defined yet - shows help by default."""
    runner = CliRunner()
    result = runner.invoke(cli)
    # Click groups with no subcommands return exit code 2 and show usage
    assert result.exit_code == 2 or result.exit_code == 0
