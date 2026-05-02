from unittest.mock import create_autospec

import pytest

from rebelist.hack.commands.git.commit_command import CommitCommand
from rebelist.hack.domain.models import Commit
from rebelist.hack.infrastructure.git import GitCommitComposer, GitManager


@pytest.mark.unit
class TestCommitCommand:
    """Verify the use-case reads the current branch, composes a commit, and commits it."""

    def test_full_flow(self) -> None:
        """The command queries current branch, asks the composer for a Commit, and commits via the manager."""
        manager = create_autospec(GitManager, instance=True)
        manager.get_current_branch.return_value = 'feature/WS-120-fix-login'
        manager.commit.return_value = '[feature/WS-120-fix-login] WS-120 Fix login'
        composer = create_autospec(GitCommitComposer, instance=True)
        commit = Commit(subject='WS-120 Fix login', body='Why this matters.')
        composer.compose.return_value = commit
        command = CommitCommand(composer, manager)

        result = command('fix login flow')

        manager.get_current_branch.assert_called_once()
        composer.compose.assert_called_once_with('fix login flow', 'feature/WS-120-fix-login')
        manager.commit.assert_called_once_with(commit)
        assert result == '[feature/WS-120-fix-login] WS-120 Fix login'
