"""End-to-end integration tests that run the installed `hack` entry point as a subprocess.

These guard against packaging regressions (missing entry-point, broken imports,
template not bundled) that pure unit tests cannot catch.

`--help` is used throughout because Typer handles it before the app callback runs,
so no user config file is required.
"""

import subprocess
import sys

import pytest


@pytest.mark.integration
class TestMainkEntryPoint:
    """Verify the installed CLI entry point boots correctly without a configured environment."""

    def test_help_flag_exits_cleanly(self) -> None:
        """`hack --help` exits 0 — confirms the package is importable and the entry point is wired."""
        result = subprocess.run(
            [sys.executable, '-c', 'from rebelist.hack.console import main; main()', '--help'],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )

        assert result.returncode == 0, f'stderr: {result.stderr}'

    def test_help_output_lists_subcommands(self) -> None:
        """`hack --help` shows the jira and git subcommands — confirms Typer wiring is intact."""
        result = subprocess.run(
            [sys.executable, '-c', 'from rebelist.hack.console import main; main()', '--help'],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )

        assert 'jira' in result.stdout
        assert 'git' in result.stdout
