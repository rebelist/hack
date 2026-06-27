from datetime import datetime
from unittest.mock import create_autospec

import pytest

from rebelist.hack.commands.score.list_command import ListScoresCommand
from rebelist.hack.domain.models import Score
from rebelist.hack.infrastructure.sqlite import ScoreRepository


@pytest.mark.unit
class TestListScoresCommand:
    """Verify the use-case returns the stored entries from the repository."""

    def test_returns_entries_from_repository(self) -> None:
        """The command delegates to the repository and returns its entries unchanged."""
        repository = create_autospec(ScoreRepository, instance=True)
        scores = [
            Score(entry_id=1, created_at=datetime(2026, 3, 12, 9, 30, 0), description='First achievement.'),
            Score(entry_id=2, created_at=datetime(2026, 5, 1, 14, 0, 0), description='Second achievement.'),
        ]
        repository.find_all.return_value = scores
        command = ListScoresCommand(repository)

        result = command()

        repository.find_all.assert_called_once()
        assert result is scores
