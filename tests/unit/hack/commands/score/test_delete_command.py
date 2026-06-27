from datetime import datetime
from unittest.mock import create_autospec

import pytest

from rebelist.hack.commands.score.delete_command import DeleteScoreCommand
from rebelist.hack.domain.models import Score
from rebelist.hack.infrastructure.sqlite import ScoreRepository


@pytest.mark.unit
class TestDeleteScoreCommand:
    """Verify the use-case deletes the requested entry through the repository."""

    def test_deletes_entry_via_repository(self) -> None:
        """The command forwards the id to the repository and returns the deleted entry."""
        repository = create_autospec(ScoreRepository, instance=True)
        deleted = Score(entry_id=3, created_at=datetime(2026, 3, 12, 9, 30, 0), description='Removed achievement.')
        repository.delete.return_value = deleted
        command = DeleteScoreCommand(repository)

        result = command(3)

        repository.delete.assert_called_once_with(3)
        assert result is deleted

    def test_returns_none_when_entry_absent(self) -> None:
        """When the repository finds no matching entry, the command returns None."""
        repository = create_autospec(ScoreRepository, instance=True)
        repository.delete.return_value = None
        command = DeleteScoreCommand(repository)

        result = command(99)

        repository.delete.assert_called_once_with(99)
        assert result is None
