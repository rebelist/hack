"""Tests for the subprocess-backed GitManager.

`subprocess.run` is substituted with a `create_autospec(subprocess.run)` stand-in
at the module level. CompletedProcess return values are also autospec'd via the
shared helper. No raw MagicMock or unspec'd patch is used.
"""

import subprocess
from typing import Any
from unittest.mock import create_autospec

import pytest
from pytest_mock import MockerFixture

from rebelist.hack.domain.models import Commit
from rebelist.hack.infrastructure.git import manager as manager_module
from rebelist.hack.infrastructure.git.manager import GitCommandError, GitManager, GitTimeoutError


def _completed_process(stdout: str = '', stderr: str = '') -> Any:
    process = create_autospec(subprocess.CompletedProcess, instance=True)
    process.stdout = stdout
    process.stderr = stderr
    return process


def _install_run_mock(mocker: MockerFixture, **mock_kwargs: Any) -> Any:
    """Substitute subprocess.run inside the manager module with an autospec'd callable."""
    run_mock = create_autospec(subprocess.run, **mock_kwargs)
    mocker.patch.object(manager_module.subprocess, 'run', new=run_mock)
    return run_mock


@pytest.mark.unit
class TestGitManager:
    """Verify GitManager builds the right argv, captures output, and surfaces errors."""

    def test_get_current_branch_invokes_correct_argv(self, mocker: MockerFixture) -> None:
        """get_current_branch shells out to `git branch --show-current`."""
        run = _install_run_mock(mocker, return_value=_completed_process(stdout='main\n'))
        manager = GitManager(timeout_seconds=5.0)

        branch = manager.get_current_branch()

        assert branch == 'main'
        run.assert_called_once_with(
            ['git', 'branch', '--show-current'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            text=True,
            encoding='utf-8',
            timeout=5.0,
        )

    def test_checkout_branch_invokes_correct_argv(self, mocker: MockerFixture) -> None:
        """checkout_branch shells out to `git checkout -b <name>`."""
        run = _install_run_mock(mocker, return_value=_completed_process(stderr='Switched to a new branch'))
        manager = GitManager()

        output = manager.checkout_branch('feature/WS-1-foo')

        assert 'Switched' in output
        assert run.call_args.args[0] == ['git', 'checkout', '-b', 'feature/WS-1-foo']

    def test_commit_with_subject_only(self, mocker: MockerFixture) -> None:
        """A Commit without a body uses a single -m flag."""
        run = _install_run_mock(mocker, return_value=_completed_process(stdout='ok'))
        manager = GitManager()

        manager.commit(Commit(subject='Fix bug'))

        assert run.call_args.args[0] == ['git', 'commit', '-m', 'Fix bug']

    def test_commit_with_body_uses_two_message_flags(self, mocker: MockerFixture) -> None:
        """A Commit with a non-empty body adds a second -m flag for the body."""
        run = _install_run_mock(mocker, return_value=_completed_process(stdout='ok'))
        manager = GitManager()

        manager.commit(Commit(subject='Fix bug', body='Why this matters.'))

        assert run.call_args.args[0] == ['git', 'commit', '-m', 'Fix bug', '-m', 'Why this matters.']

    def test_failed_command_raises_git_command_error_with_stderr(self, mocker: MockerFixture) -> None:
        """A non-zero exit raises GitCommandError whose message is the git stderr output."""
        error = subprocess.CalledProcessError(
            returncode=1, cmd=['git', 'commit'], output='', stderr='nothing to commit'
        )
        _install_run_mock(mocker, side_effect=error)
        manager = GitManager()

        with pytest.raises(GitCommandError) as exc_info:
            manager.commit(Commit(subject='Fix bug'))

        assert exc_info.value.returncode == 1
        assert 'nothing to commit' in exc_info.value.stderr
        assert 'nothing to commit' in str(exc_info.value)

    def test_failed_command_with_stdout_only_surfaces_it_in_message(self, mocker: MockerFixture) -> None:
        """When git writes its failure output to stdout (e.g. 'nothing to commit'), that text appears in the message."""
        error = subprocess.CalledProcessError(
            returncode=1, cmd=['git', 'commit'], output='nothing to commit, working tree clean', stderr=''
        )
        _install_run_mock(mocker, side_effect=error)
        manager = GitManager()

        with pytest.raises(GitCommandError) as exc_info:
            manager.commit(Commit(subject='Fix bug'))

        assert 'nothing to commit, working tree clean' in str(exc_info.value)
        assert exc_info.value.stdout == 'nothing to commit, working tree clean'
        assert exc_info.value.stderr == ''

    def test_failed_command_with_no_stderr_falls_back_to_empty_string(self, mocker: MockerFixture) -> None:
        """If the failure carries no stderr, the error message renders an empty stderr fragment."""
        error = subprocess.CalledProcessError(returncode=2, cmd=['git', 'commit'], output=None, stderr=None)
        _install_run_mock(mocker, side_effect=error)
        manager = GitManager()

        with pytest.raises(GitCommandError) as exc_info:
            manager.commit(Commit(subject='Fix'))

        assert exc_info.value.stderr == ''
        assert exc_info.value.stdout == ''

    def test_timeout_raises_git_timeout_error(self, mocker: MockerFixture) -> None:
        """A subprocess timeout is translated into GitTimeoutError carrying the configured limit."""
        timeout_error = subprocess.TimeoutExpired(cmd=['git', 'commit'], timeout=2.0)
        _install_run_mock(mocker, side_effect=timeout_error)
        manager = GitManager(timeout_seconds=2.0)

        with pytest.raises(GitTimeoutError) as exc_info:
            manager.commit(Commit(subject='Fix'))

        assert exc_info.value.timeout == 2.0
        assert 'timed out after 2.0s' in str(exc_info.value)


@pytest.mark.unit
class TestGitErrors:
    """Verify the error classes carry the right attributes."""

    def test_git_command_error_exposes_command_and_streams(self) -> None:
        """GitCommandError keeps the command, exit code, and both streams accessible."""
        error = GitCommandError(['git', 'status'], 128, 'fatal: not a git repo', 'partial')

        assert error.command == ['git', 'status']
        assert error.returncode == 128
        assert error.stderr == 'fatal: not a git repo'
        assert error.stdout == 'partial'

    def test_git_timeout_error_exposes_command_and_timeout(self) -> None:
        """GitTimeoutError keeps the command and timeout accessible for handlers."""
        error = GitTimeoutError(['git', 'fetch'], 30.0)

        assert error.command == ['git', 'fetch']
        assert error.timeout == 30.0


@pytest.mark.unit
class TestGitManagerConfigurability:
    """Verify the constructor wires git_binary and timeout into subprocess.run."""

    def test_uses_custom_git_binary(self, mocker: MockerFixture) -> None:
        """A custom git binary path is honoured at execution time."""
        run = _install_run_mock(mocker, return_value=_completed_process())
        manager = GitManager(git_binary='/usr/local/bin/git')

        manager.get_current_branch()

        assert run.call_args.args[0][0] == '/usr/local/bin/git'

    def test_uses_default_timeout(self, mocker: MockerFixture) -> None:
        """Without an explicit timeout the manager uses DEFAULT_TIMEOUT_SECONDS."""
        run = _install_run_mock(mocker, return_value=_completed_process())
        manager = GitManager()

        manager.get_current_branch()

        assert run.call_args.kwargs['timeout'] == GitManager.DEFAULT_TIMEOUT_SECONDS
