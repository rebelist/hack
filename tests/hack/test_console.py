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

from dataclasses import dataclass
from typing import Any
from unittest.mock import create_autospec

import pytest
from jira.exceptions import JIRAError
from pydantic import ValidationError
from pytest_mock import MockerFixture
from rich.console import Console
from typer import Exit, Typer
from typer.testing import CliRunner

from rebelist.hack import console as console_module
from rebelist.hack.commands.git import CheckoutBranchCommand, CommitCommand
from rebelist.hack.commands.jira import CreateJiraTicketCommand
from rebelist.hack.config.container import Container
from rebelist.hack.config.settings import Settings
from rebelist.hack.domain.models import Ticket
from rebelist.hack.infrastructure.git.manager import GitCommandError, GitTimeoutError


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
        assert harness.create_ticket.call_args.args == ('fix login flow',)
        assert 'WS-1' in result.stdout
        assert 'jira.example.com' in result.stdout

    def test_git_branch_command_dispatches_to_container(self, cli_runner: CliRunner, harness: _ConsoleHarness) -> None:
        """`hack git branch WS-120` invokes the checkout command and prints its output."""
        harness.git_checkout_branch.return_value = 'feature/WS-120-fix'

        result = cli_runner.invoke(console_module.app, ['git', 'branch', 'WS-120'])

        assert result.exit_code == 0
        harness.git_checkout_branch.assert_called_once()
        assert harness.git_checkout_branch.call_args.args == ('WS-120',)
        assert 'feature/WS-120-fix' in result.stdout

    def test_git_commit_command_dispatches_to_container(self, cli_runner: CliRunner, harness: _ConsoleHarness) -> None:
        """`hack git commit "..."` invokes the commit command and prints its output."""
        harness.git_commit.return_value = '[feature/WS-1] WS-1 Fix'

        result = cli_runner.invoke(console_module.app, ['git', 'commit', 'fix login'])

        assert result.exit_code == 0
        harness.git_commit.assert_called_once()
        assert harness.git_commit.call_args.args == ('fix login',)
        assert 'WS-1 Fix' in result.stdout


def _install_app_mock(mocker: MockerFixture, side_effect: BaseException) -> None:
    """Substitute console.app with an autospec'd Typer instance that raises the given exception when called."""
    app_mock = create_autospec(Typer, instance=True)
    app_mock.side_effect = side_effect
    mocker.patch.object(console_module, 'app', new=app_mock)


def _install_error_console_print_mock(mocker: MockerFixture) -> Any:
    """Substitute error_console.print with an autospec'd callable so tests can read the rendered message."""
    print_mock = create_autospec(Console.print)
    mocker.patch.object(console_module.error_console, 'print', new=print_mock)
    return print_mock


@pytest.mark.unit
class TestMainErrorHandler:
    """Verify main() translates expected failures into red lines + non-zero exit codes."""

    def test_propagates_typer_exit(self, mocker: MockerFixture) -> None:
        """A clean Typer Exit (e.g. --help / --version) must not be swallowed by the handler."""
        _install_app_mock(mocker, Exit())

        with pytest.raises(Exit):
            console_module.main()

    def test_handles_git_command_error(self, mocker: MockerFixture) -> None:
        """GitCommandError exits 1 and renders a red 'Git error' line on stderr."""
        _install_app_mock(mocker, GitCommandError(['git', 'commit'], 1, 'nothing to commit', ''))
        printer = _install_error_console_print_mock(mocker)

        with pytest.raises(SystemExit) as exc_info:
            console_module.main()

        assert exc_info.value.code == 1
        printer.assert_called_once()
        assert 'Git error' in printer.call_args.args[0]

    def test_handles_git_timeout_error(self, mocker: MockerFixture) -> None:
        """GitTimeoutError exits 1 and renders a red 'Git error' line."""
        _install_app_mock(mocker, GitTimeoutError(['git', 'fetch'], 30.0))
        printer = _install_error_console_print_mock(mocker)

        with pytest.raises(SystemExit) as exc_info:
            console_module.main()

        assert exc_info.value.code == 1
        assert 'Git error' in printer.call_args.args[0]

    def test_handles_jira_error_with_text(self, mocker: MockerFixture) -> None:
        """JIRAError is rendered with its `text` attribute when present."""
        _install_app_mock(mocker, JIRAError(status_code=400, text='Issue type is required'))
        printer = _install_error_console_print_mock(mocker)

        with pytest.raises(SystemExit) as exc_info:
            console_module.main()

        assert exc_info.value.code == 1
        rendered = printer.call_args.args[0]
        assert 'Jira error' in rendered
        assert 'Issue type is required' in rendered

    def test_handles_validation_error(self, mocker: MockerFixture) -> None:
        """A pydantic ValidationError surfaces as a count of validation errors."""
        with pytest.raises(ValidationError) as exc_info:
            Ticket.model_validate({'summary': None, 'kind': None, 'description': None})
        _install_app_mock(mocker, exc_info.value)
        printer = _install_error_console_print_mock(mocker)

        with pytest.raises(SystemExit) as system_exit:
            console_module.main()

        assert system_exit.value.code == 1
        assert 'Invalid agent output' in printer.call_args.args[0]

    def test_handles_keyboard_interrupt(self, mocker: MockerFixture) -> None:
        """Ctrl-C exits 130 with a yellow 'Aborted' line."""
        _install_app_mock(mocker, KeyboardInterrupt())
        printer = _install_error_console_print_mock(mocker)

        with pytest.raises(SystemExit) as exc_info:
            console_module.main()

        assert exc_info.value.code == 130
        assert 'Aborted' in printer.call_args.args[0]

    def test_handles_unexpected_exception(self, mocker: MockerFixture) -> None:
        """Any other exception is rendered as 'Unexpected error' and exits 1."""
        _install_app_mock(mocker, RuntimeError('boom'))
        printer = _install_error_console_print_mock(mocker)

        with pytest.raises(SystemExit) as exc_info:
            console_module.main()

        assert exc_info.value.code == 1
        assert 'Unexpected error' in printer.call_args.args[0]
        assert 'boom' in printer.call_args.args[0]
