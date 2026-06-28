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
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import create_autospec

import pytest
from pydantic import ValidationError
from pytest_mock import MockerFixture
from rich.panel import Panel
from typer import Typer
from typer.testing import CliRunner

from rebelist.hack import console as console_module
from rebelist.hack.commands.git import CheckoutBranchCommand, CommitCommand
from rebelist.hack.commands.jira import CreateJiraTicketCommand
from rebelist.hack.commands.score import (
    DeleteAllScoresCommand,
    DeleteScoreCommand,
    ExportScoreLogCommand,
    ListScoresCommand,
    SaveScoreCommand,
)
from rebelist.hack.config.container import Container
from rebelist.hack.config.settings import GeneralSettings, Settings, SettingsError
from rebelist.hack.console import Application
from rebelist.hack.domain.models import Score, Ticket


@dataclass
class _ConsoleHarness:
    """Bundles the patched-in container with direct handles to its autospec'd command mocks."""

    container: Container
    create_ticket: Any
    git_checkout_branch: Any
    git_commit: Any
    score_save: Any
    score_export: Any
    score_list: Any
    score_delete: Any
    score_delete_all: Any


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
    score_save = create_autospec(SaveScoreCommand, instance=True)
    score_export = create_autospec(ExportScoreLogCommand, instance=True)
    score_list = create_autospec(ListScoresCommand, instance=True)
    score_delete = create_autospec(DeleteScoreCommand, instance=True)
    score_delete_all = create_autospec(DeleteAllScoresCommand, instance=True)

    container = Container(settings)
    container.create_ticket_command = create_ticket
    container.git_checkout_branch_command = git_checkout_branch
    container.git_commit_command = git_commit
    container.score_save_command = score_save
    container.score_export_command = score_export
    container.score_list_command = score_list
    container.score_delete_command = score_delete
    container.score_delete_all_command = score_delete_all

    container_class_mock = create_autospec(Container)
    container_class_mock.return_value = container
    mocker.patch.object(console_module, 'Container', new=container_class_mock)
    return _ConsoleHarness(
        container=container,
        create_ticket=create_ticket,
        git_checkout_branch=git_checkout_branch,
        git_commit=git_commit,
        score_save=score_save,
        score_export=score_export,
        score_list=score_list,
        score_delete=score_delete,
        score_delete_all=score_delete_all,
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

    def test_jira_ticket_command_prompts_when_description_omitted(
        self, cli_runner: CliRunner, harness: _ConsoleHarness
    ) -> None:
        """`hack jira ticket` with no description prompts for it, then dispatches the entered text."""
        ticket = Ticket(key='WS-1', summary='S', kind='Bug', description='D')
        harness.create_ticket.return_value = ticket

        result = cli_runner.invoke(console_module.app, ['jira', 'ticket'], input='fix login flow\n')

        assert result.exit_code == 0
        harness.create_ticket.assert_called_once()
        assert harness.create_ticket.call_args.args[0] == 'fix login flow'
        assert harness.create_ticket.call_args.kwargs == {'dry_run': False}
        assert 'WS-1' in result.stdout

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

    def test_git_commit_command_prompts_when_description_omitted(
        self, cli_runner: CliRunner, harness: _ConsoleHarness
    ) -> None:
        """`hack git commit` with no description prompts for it, then dispatches the entered text."""
        harness.git_commit.return_value = '[feature/WS-1] WS-1 Fix'

        result = cli_runner.invoke(console_module.app, ['git', 'commit'], input='fix login\n')

        assert result.exit_code == 0
        harness.git_commit.assert_called_once()
        assert harness.git_commit.call_args.args[0] == 'fix login'
        assert harness.git_commit.call_args.kwargs == {'dry_run': False}
        assert 'WS-1 Fix' in result.stdout

    def test_score_save_command_dispatches_to_container(self, cli_runner: CliRunner, harness: _ConsoleHarness) -> None:
        """`hack score save "..."` invokes the save command and prints the stored entry."""
        harness.score_save.return_value = Score(description='Stabilized the deployment pipeline.')

        result = cli_runner.invoke(console_module.app, ['score', 'save', 'stabilized the deploy pipeline'])

        assert result.exit_code == 0
        harness.score_save.assert_called_once()
        assert harness.score_save.call_args.args[0] == 'stabilized the deploy pipeline'
        assert harness.score_save.call_args.kwargs == {'dry_run': False}
        assert 'Stabilized the deployment pipeline.' in result.stdout

    def test_score_save_dry_run(self, cli_runner: CliRunner, harness: _ConsoleHarness) -> None:
        """`hack score save --dry-run` shows the cleaned entry without persisting it."""
        harness.score_save.return_value = Score(description='Mentored two engineers.')

        result = cli_runner.invoke(console_module.app, ['score', 'save', 'mentored two engineers', '--dry-run'])

        assert result.exit_code == 0
        assert harness.score_save.call_args.kwargs == {'dry_run': True}
        assert 'Dry run' in result.stdout
        assert 'Mentored two engineers.' in result.stdout

    def test_score_save_command_prompts_when_description_omitted(
        self, cli_runner: CliRunner, harness: _ConsoleHarness
    ) -> None:
        """`hack score save` with no description prompts for it, then dispatches the entered text."""
        harness.score_save.return_value = Score(description='Stabilized the deployment pipeline.')

        result = cli_runner.invoke(console_module.app, ['score', 'save'], input='stabilized the deploy pipeline\n')

        assert result.exit_code == 0
        harness.score_save.assert_called_once()
        assert harness.score_save.call_args.args[0] == 'stabilized the deploy pipeline'
        assert harness.score_save.call_args.kwargs == {'dry_run': False}
        assert 'Stabilized the deployment pipeline.' in result.stdout

    def test_score_export_command_dispatches_to_container(
        self, cli_runner: CliRunner, harness: _ConsoleHarness
    ) -> None:
        """`hack score export score-log.md` invokes the export command with the destination path."""
        harness.score_export.return_value = '# Score Log'

        result = cli_runner.invoke(console_module.app, ['score', 'export', 'score-log.md'])

        assert result.exit_code == 0
        harness.score_export.assert_called_once()
        assert Path(harness.score_export.call_args.args[0]) == Path('score-log.md')
        assert harness.score_export.call_args.kwargs == {'dry_run': False}
        assert 'score-log.md' in result.stdout

    def test_score_export_dry_run(self, cli_runner: CliRunner, harness: _ConsoleHarness) -> None:
        """`hack score export --dry-run` renders the score log without writing a file."""
        harness.score_export.return_value = '# Score Log'

        result = cli_runner.invoke(console_module.app, ['score', 'export', 'score-log.md', '--dry-run'])

        assert result.exit_code == 0
        assert harness.score_export.call_args.kwargs == {'dry_run': True}
        assert 'Dry run' in result.stdout

    def test_score_list_command_prints_entries_with_ids(self, cli_runner: CliRunner, harness: _ConsoleHarness) -> None:
        """`hack score list` prints each entry prefixed with its id in square brackets."""
        harness.score_list.return_value = [
            Score(entry_id=1, created_at=datetime(2026, 3, 12, 9, 30, 0), description='First achievement.'),
            Score(entry_id=2, created_at=datetime(2026, 5, 1, 14, 0, 0), description='Second achievement.'),
        ]

        result = cli_runner.invoke(console_module.app, ['score', 'list'])

        assert result.exit_code == 0
        harness.score_list.assert_called_once()
        assert '[1]' in result.stdout
        assert 'First achievement.' in result.stdout
        assert '[2]' in result.stdout
        assert 'Second achievement.' in result.stdout

    def test_score_list_command_when_empty(self, cli_runner: CliRunner, harness: _ConsoleHarness) -> None:
        """`hack score list` with no entries prints a friendly empty-state message."""
        harness.score_list.return_value = []

        result = cli_runner.invoke(console_module.app, ['score', 'list'])

        assert result.exit_code == 0
        assert 'No achievements' in result.stdout

    def test_score_delete_command_prompts_for_id_and_deletes(
        self, cli_runner: CliRunner, harness: _ConsoleHarness
    ) -> None:
        """`hack score delete` prompts for the id, deletes it, and confirms what was removed."""
        harness.score_delete.return_value = Score(
            entry_id=2, created_at=datetime(2026, 5, 1, 14, 0, 0), description='Removed achievement.'
        )

        result = cli_runner.invoke(console_module.app, ['score', 'delete'], input='2\n')

        assert result.exit_code == 0
        harness.score_delete.assert_called_once()
        assert harness.score_delete.call_args.args[0] == 2
        assert 'Deleted' in result.stdout
        assert 'Removed achievement.' in result.stdout

    def test_score_delete_command_unknown_id(self, cli_runner: CliRunner, harness: _ConsoleHarness) -> None:
        """`hack score delete --entry-id` with an unknown id reports that nothing was found."""
        harness.score_delete.return_value = None

        result = cli_runner.invoke(console_module.app, ['score', 'delete', '--entry-id', '99'])

        assert result.exit_code == 0
        assert harness.score_delete.call_args.args[0] == 99
        assert 'No entry found' in result.stdout

    def test_score_delete_all_truncates_after_confirmation(
        self, cli_runner: CliRunner, harness: _ConsoleHarness
    ) -> None:
        """`hack score delete --all` confirms first, then truncates the table without asking for an id."""
        harness.score_delete_all.return_value = 3

        result = cli_runner.invoke(console_module.app, ['score', 'delete', '--all'], input='y\n')

        assert result.exit_code == 0
        harness.score_delete_all.assert_called_once()
        harness.score_delete.assert_not_called()
        assert '3' in result.stdout

    def test_score_delete_all_aborted_when_declined(self, cli_runner: CliRunner, harness: _ConsoleHarness) -> None:
        """`hack score delete --all` answered with 'no' deletes nothing."""
        result = cli_runner.invoke(console_module.app, ['score', 'delete', '--all'], input='n\n')

        assert result.exit_code == 0
        harness.score_delete_all.assert_not_called()
        assert 'Aborted' in result.stdout

    def test_diagnose_prints_redacted_metadata(self, cli_runner: CliRunner, harness: _ConsoleHarness) -> None:
        """`hack diagnose` prints version + config metadata; secrets are redacted."""
        result = cli_runner.invoke(console_module.app, ['info'])

        assert result.exit_code == 0
        assert '0.0.0-test' in result.stdout
        assert 'jira.example.com' in result.stdout
        assert 'redacted' in result.stdout
        assert 'Score' in result.stdout
        assert 'Database' in result.stdout
        assert harness.container.settings.agent.api_key.get_secret_value() not in result.stdout
        assert harness.container.settings.jira.token.get_secret_value() not in result.stdout

    def test_bootstrap_wraps_validation_error_as_settings_error(
        self, cli_runner: CliRunner, mocker: MockerFixture, settings: Settings
    ) -> None:
        """A ValidationError raised by Container construction is re-raised as a SettingsError.

        Container is only built for real subcommands (`--version` short-circuits on lightweight
        metadata before the Settings graph loads), so the failure is driven through `info`.
        """
        del settings
        with pytest.raises(ValidationError) as exc_info:
            GeneralSettings.model_validate({})

        container_class_mock = create_autospec(Container)
        container_class_mock.side_effect = exc_info.value
        mocker.patch.object(console_module, 'Container', new=container_class_mock)

        result = cli_runner.invoke(console_module.app, ['info'])

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
    """Verify main() surfaces failures as error Panels on stderr and uses correct exit codes."""

    def test_keyboard_interrupt_exits_130(self, mocker: MockerFixture) -> None:
        """Ctrl-C exits with code 130 and a yellow 'Aborted' line on stderr."""
        _install_app_mock(mocker, KeyboardInterrupt())
        printer = _install_error_console_print_mock(mocker)

        with pytest.raises(SystemExit) as exc_info:
            console_module.main()

        assert exc_info.value.code == Application.EXIT_SIGINT
        assert 'Aborted' in printer.call_args.args[0]

    def test_any_exception_prints_error_panel_on_stderr_and_exits_1(self, mocker: MockerFixture) -> None:
        """Any unhandled exception prints a Rich Panel to stderr containing the message and exits with code 1."""
        _install_app_mock(mocker, RuntimeError('something went wrong'))
        printer = _install_error_console_print_mock(mocker)

        with pytest.raises(SystemExit) as exc_info:
            console_module.main()

        assert exc_info.value.code == 1
        panel: Panel = printer.call_args.args[0]
        assert isinstance(panel, Panel)
        assert 'something went wrong' in str(panel.renderable)

    def test_exception_with_debug_flag_also_prints_stack_trace(self, mocker: MockerFixture) -> None:
        """With --debug in sys.argv, unhandled exceptions emit a full stack trace via error_console."""
        _install_app_mock(mocker, RuntimeError('oops'))
        _install_error_console_print_mock(mocker)
        print_exception_mock = create_autospec(console_module.error_console.print_exception)
        mocker.patch.object(console_module.error_console, 'print_exception', new=print_exception_mock)
        mocker.patch.object(sys, 'argv', new=['hack', '--debug'])

        with pytest.raises(SystemExit):
            console_module.main()

        print_exception_mock.assert_called_once()
