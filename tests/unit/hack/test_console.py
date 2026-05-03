"""Tests for the Typer console entry point and the top-level error handler.

The DI Container is replaced at module level with a `create_autospec(Container)`
class mock whose `return_value` is a real `Container(settings)` whose command
attributes have been overridden with autospec'd command instances. This keeps
every mock built via `create_autospec` (single source of truth) while letting
the production cached_property mechanism stay out of the test path.

Autospec'd callable instances have a stdlib quirk: `assert_called_once_with('x')`
fails even when the recorded args match, because autospec records calls under
the bound `__call__` signature. We sidestep this by asserting on
`mock.call_args.args` directly — same intent, no workaround in production code.
"""

import sys
from dataclasses import dataclass
from typing import Any
from unittest.mock import create_autospec

import pytest
from pydantic import ValidationError
from pytest_mock import MockerFixture
from typer import Exit, Typer
from typer.testing import CliRunner

from rebelist.hack import console as console_module
from rebelist.hack.commands.git import CheckoutBranchCommand, CommitCommand
from rebelist.hack.commands.jira import CreateJiraTicketCommand
from rebelist.hack.config.container import Container
from rebelist.hack.config.settings import GeneralSettings, Settings, SettingsError
from rebelist.hack.console import Application
from rebelist.hack.domain.models import Ticket


@dataclass
class _ConsoleHarness:
    """Bundles the patched-in container with direct handles to its autospec'd command mocks."""

    container: Container
    create_ticket: Any
    git_checkout_branch: Any
    git_commit: Any


@pytest.fixture
def cli_runner() -> CliRunner:
    """Typer test runner."""
    return CliRunner()


@pytest.fixture
def harness(mocker: MockerFixture, settings: Settings) -> _ConsoleHarness:
    """Build a real Container, override its command properties with autospec'd commands, patch it in.

    `cached_property` resolves on first read; assigning the attribute beforehand
    populates `__dict__` directly so the descriptor never runs. This avoids
    constructing real JIRA clients / LLM agents while keeping every collaborator
    `create_autospec`-validated.
    """
    create_ticket = create_autospec(CreateJiraTicketCommand, instance=True)
    git_checkout_branch = create_autospec(CheckoutBranchCommand, instance=True)
    git_commit = create_autospec(CommitCommand, instance=True)

    container = Container(settings)
    container.create_ticket_command = create_ticket
    container.git_checkout_branch_command = git_checkout_branch
    container.git_commit_command = git_commit

    container_class_mock = create_autospec(Container)
    container_class_mock.return_value = container
    mocker.patch.object(console_module, 'Container', new=container_class_mock)
    return _ConsoleHarness(
        container=container,
        create_ticket=create_ticket,
        git_checkout_branch=git_checkout_branch,
        git_commit=git_commit,
    )


@pytest.mark.unit
class TestConsoleCommands:
    """Verify Typer command dispatch and container wiring."""

    def test_no_args_prints_version_and_exits_cleanly(self, cli_runner: CliRunner, harness: _ConsoleHarness) -> None:
        """Invoking the CLI without a subcommand prints the version banner and exits 0."""
        del harness  # ensures the Container patch is active
        result = cli_runner.invoke(console_module.app, [])

        assert result.exit_code == 0
        assert 'Hack' in result.stdout
        assert '0.0.0-test' in result.stdout

    def test_version_flag_prints_version(self, cli_runner: CliRunner, harness: _ConsoleHarness) -> None:
        """--version prints the version banner regardless of subcommand."""
        del harness  # ensures the Container patch is active
        result = cli_runner.invoke(console_module.app, ['--version'])

        assert result.exit_code == 0
        assert '0.0.0-test' in result.stdout

    def test_jira_ticket_command_dispatches_to_container(self, cli_runner: CliRunner, harness: _ConsoleHarness) -> None:
        """`hack jira ticket "..."` invokes container.create_ticket_command and prints the issue URL."""
        ticket = Ticket(key='WS-1', summary='S', kind='Bug', description='D')
        harness.create_ticket.return_value = ticket

        result = cli_runner.invoke(console_module.app, ['jira', 'ticket', 'fix login flow'])

        assert result.exit_code == 0
        harness.create_ticket.assert_called_once()
        assert harness.create_ticket.call_args.args[0] == 'fix login flow'
        assert harness.create_ticket.call_args.kwargs == {'dry_run': False}
        assert 'WS-1' in result.stdout
        assert 'jira.example.com' in result.stdout

    def test_jira_ticket_dry_run_skips_persistence(self, cli_runner: CliRunner, harness: _ConsoleHarness) -> None:
        """`hack jira ticket --dry-run` renders the ticket without persisting and prints a banner."""
        ticket = Ticket(summary='S', kind='Bug', description='D')
        harness.create_ticket.return_value = ticket

        result = cli_runner.invoke(console_module.app, ['jira', 'ticket', 'fix login flow', '--dry-run'])

        assert result.exit_code == 0
        assert harness.create_ticket.call_args.kwargs == {'dry_run': True}
        assert 'Dry run' in result.stdout

    def test_git_branch_command_dispatches_to_container(self, cli_runner: CliRunner, harness: _ConsoleHarness) -> None:
        """`hack git branch WS-120` invokes the checkout command and prints its output."""
        harness.git_checkout_branch.return_value = 'feature/WS-120-fix'

        result = cli_runner.invoke(console_module.app, ['git', 'branch', 'WS-120'])

        assert result.exit_code == 0
        harness.git_checkout_branch.assert_called_once()
        assert harness.git_checkout_branch.call_args.args[0] == 'WS-120'
        assert harness.git_checkout_branch.call_args.kwargs == {'dry_run': False}
        assert 'feature/WS-120-fix' in result.stdout

    def test_git_branch_dry_run(self, cli_runner: CliRunner, harness: _ConsoleHarness) -> None:
        """`hack git branch WS-120 --dry-run` prints the resolved name without checking out."""
        harness.git_checkout_branch.return_value = 'feature/WS-120-fix'

        result = cli_runner.invoke(console_module.app, ['git', 'branch', 'WS-120', '--dry-run'])

        assert result.exit_code == 0
        assert harness.git_checkout_branch.call_args.kwargs == {'dry_run': True}
        assert 'Dry run' in result.stdout
        assert 'feature/WS-120-fix' in result.stdout

    def test_git_commit_command_dispatches_to_container(self, cli_runner: CliRunner, harness: _ConsoleHarness) -> None:
        """`hack git commit "..."` invokes the commit command and prints its output."""
        harness.git_commit.return_value = '[feature/WS-1] WS-1 Fix'

        result = cli_runner.invoke(console_module.app, ['git', 'commit', 'fix login'])

        assert result.exit_code == 0
        harness.git_commit.assert_called_once()
        assert harness.git_commit.call_args.args[0] == 'fix login'
        assert harness.git_commit.call_args.kwargs == {'dry_run': False}
        assert 'WS-1 Fix' in result.stdout

    def test_git_commit_dry_run(self, cli_runner: CliRunner, harness: _ConsoleHarness) -> None:
        """`hack git commit --dry-run` renders the commit message without committing."""
        harness.git_commit.return_value = 'WS-1 Fix login'

        result = cli_runner.invoke(console_module.app, ['git', 'commit', 'fix login', '--dry-run'])

        assert result.exit_code == 0
        assert harness.git_commit.call_args.kwargs == {'dry_run': True}
        assert 'Dry run' in result.stdout
        assert 'WS-1 Fix login' in result.stdout

    def test_diagnose_prints_redacted_metadata(self, cli_runner: CliRunner, harness: _ConsoleHarness) -> None:
        """`hack diagnose` prints version + config metadata; secrets are redacted."""
        result = cli_runner.invoke(console_module.app, ['info'])

        assert result.exit_code == 0
        assert '0.0.0-test' in result.stdout
        assert 'jira.example.com' in result.stdout
        assert 'redacted' in result.stdout
        assert harness.container.settings.agent.api_key.get_secret_value() not in result.stdout
        assert harness.container.settings.jira.token.get_secret_value() not in result.stdout

    def test_bootstrap_wraps_validation_error_as_settings_error(
        self, cli_runner: CliRunner, mocker: MockerFixture, settings: Settings
    ) -> None:
        """A ValidationError raised by Container construction is re-raised as a SettingsError."""
        del settings  # activates the fixture so Settings.instance() is cached
        with pytest.raises(ValidationError) as exc_info:
            GeneralSettings.model_validate({})

        container_class_mock = create_autospec(Container)
        container_class_mock.side_effect = exc_info.value
        mocker.patch.object(console_module, 'Container', new=container_class_mock)

        result = cli_runner.invoke(console_module.app, ['--version'])

        assert isinstance(result.exception, SettingsError)


def _install_app_mock(mocker: MockerFixture, side_effect: BaseException) -> None:
    """Substitute console.app with an autospec'd Typer instance that raises the given exception when called."""
    app_mock = create_autospec(Typer, instance=True)
    app_mock.side_effect = side_effect
    mocker.patch.object(console_module, 'app', new=app_mock)


def _install_error_console_print_mock(mocker: MockerFixture) -> Any:
    """Substitute error_console.print with an autospec'd callable so tests can read the rendered message."""
    print_mock = create_autospec(console_module.error_console.print)
    mocker.patch.object(console_module.error_console, 'print', new=print_mock)
    return print_mock


@pytest.mark.unit
class TestMainErrorHandler:
    """Verify main() surfaces failures as red lines and correct exit codes."""

    def test_propagates_typer_exit(self, mocker: MockerFixture) -> None:
        """A clean Typer Exit (e.g. --help / --version) must not be swallowed by the handler."""
        _install_app_mock(mocker, Exit())

        with pytest.raises(Exit):
            console_module.main()

    def test_keyboard_interrupt_exits_130(self, mocker: MockerFixture) -> None:
        """Ctrl-C exits with code 130 and a yellow 'Aborted' line."""
        _install_app_mock(mocker, KeyboardInterrupt())
        printer = _install_error_console_print_mock(mocker)

        with pytest.raises(SystemExit) as exc_info:
            console_module.main()

        assert exc_info.value.code == Application.EXIT_SIGINT
        assert 'Aborted' in printer.call_args.args[0]

    def test_any_exception_prints_error_and_exits_1(self, mocker: MockerFixture) -> None:
        """Any unhandled exception prints a red error line and exits with code 1."""
        _install_app_mock(mocker, RuntimeError('something went wrong'))
        printer = _install_error_console_print_mock(mocker)

        with pytest.raises(SystemExit) as exc_info:
            console_module.main()

        assert exc_info.value.code == 1
        assert 'something went wrong' in printer.call_args.args[0]

    def test_exception_with_debug_flag_also_prints_stack_trace(self, mocker: MockerFixture) -> None:
        """With --debug in sys.argv, unhandled exceptions also emit a full stack trace."""
        _install_app_mock(mocker, RuntimeError('oops'))
        _install_error_console_print_mock(mocker)
        print_exception_mock = create_autospec(console_module.error_console.print_exception)
        mocker.patch.object(console_module.error_console, 'print_exception', new=print_exception_mock)
        mocker.patch.object(sys, 'argv', new=['hack', '--debug'])

        with pytest.raises(SystemExit):
            console_module.main()

        print_exception_mock.assert_called_once()
