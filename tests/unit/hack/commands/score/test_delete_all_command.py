from unittest.mock import create_autospec

import pytest

from rebelist.hack.commands.score import DeleteAllScoresCommand
from rebelist.hack.infrastructure.sqlite import ScoreRepository


@pytest.mark.unit
class TestDeleteAllScoresCommand:
    """Verify the use-case truncates the score log through the repository."""

    def test_truncates_via_repository_and_returns_count(self) -> None:
        """The command delegates to the repository and returns the number of entries removed."""
        repository = create_autospec(ScoreRepository, instance=True)
        repository.delete_all.return_value = 3
        command = DeleteAllScoresCommand(repository)

        result = command()

        repository.delete_all.assert_called_once()
        assert result == 3
