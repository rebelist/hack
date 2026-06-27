from datetime import datetime
from unittest.mock import create_autospec

import pytest

from rebelist.hack.commands.score.save_command import SaveScoreCommand
from rebelist.hack.domain.models import Score
from rebelist.hack.infrastructure.sqlite import ScoreComposer, ScoreRepository


@pytest.mark.unit
class TestSaveScoreCommand:
    """Verify the use-case cleans up the entry and persists it via the repository."""

    def test_full_flow_cleans_then_persists(self) -> None:
        """The command asks the composer to clean the note, then saves it and returns the stored Score."""
        composer = create_autospec(ScoreComposer, instance=True)
        composer.compose.return_value = 'Fixed the flaky deployment pipeline.'
        repository = create_autospec(ScoreRepository, instance=True)
        stored = Score(created_at=datetime(2026, 3, 12, 9, 30, 0), description='Fixed the flaky deployment pipeline.')
        repository.save.return_value = stored
        command = SaveScoreCommand(composer, repository)

        result = command('fixed the flaky deploy pipeline everyone hated')

        composer.compose.assert_called_once_with('fixed the flaky deploy pipeline everyone hated')
        repository.save.assert_called_once_with(Score(description='Fixed the flaky deployment pipeline.'))
        assert result is stored

    def test_dry_run_returns_cleaned_score_without_persisting(self) -> None:
        """With dry_run=True the cleaned (unsaved) Score is returned and the repository is not touched."""
        composer = create_autospec(ScoreComposer, instance=True)
        composer.compose.return_value = 'Mentored two engineers.'
        repository = create_autospec(ScoreRepository, instance=True)
        command = SaveScoreCommand(composer, repository)

        result = command('mentored two engineers', dry_run=True)

        repository.save.assert_not_called()
        assert result == Score(description='Mentored two engineers.')
        assert result.created_at is None
