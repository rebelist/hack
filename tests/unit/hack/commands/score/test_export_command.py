from datetime import datetime
from pathlib import Path
from unittest.mock import create_autospec

import pytest

from rebelist.hack.commands.score.export_command import ExportScoreLogCommand, NoScoresError
from rebelist.hack.domain.models import Score
from rebelist.hack.infrastructure.sqlite import ScoreLogComposer, ScoreRepository


def _scores() -> list[Score]:
    return [
        Score(created_at=datetime(2026, 5, 1, 14, 0, 0), description='Mentored two engineers.'),
        Score(created_at=datetime(2026, 3, 12, 9, 30, 0), description='Stabilized the deployment pipeline.'),
    ]


@pytest.mark.unit
class TestExportScoreLogCommand:
    """Verify the use-case loads entries, composes a score log, and writes the markdown file."""

    def test_full_flow_writes_markdown_to_file(self, tmp_path: Path) -> None:
        """The command loads every entry, asks the composer for markdown, and writes it to the given path."""
        repository = create_autospec(ScoreRepository, instance=True)
        repository.find_all.return_value = _scores()
        composer = create_autospec(ScoreLogComposer, instance=True)
        composer.compose.return_value = '# Score Log\n- entry'
        command = ExportScoreLogCommand(repository, composer)
        destination = tmp_path / 'score-log.md'

        result = command(destination)

        repository.find_all.assert_called_once()
        composer.compose.assert_called_once_with(_scores())
        assert destination.read_text(encoding='utf-8') == '# Score Log\n- entry'
        assert result == '# Score Log\n- entry'

    def test_dry_run_returns_markdown_without_writing(self, tmp_path: Path) -> None:
        """With dry_run=True the markdown is returned but no file is written."""
        repository = create_autospec(ScoreRepository, instance=True)
        repository.find_all.return_value = _scores()
        composer = create_autospec(ScoreLogComposer, instance=True)
        composer.compose.return_value = '# Score Log'
        command = ExportScoreLogCommand(repository, composer)
        destination = tmp_path / 'score-log.md'

        result = command(destination, dry_run=True)

        assert not destination.exists()
        assert result == '# Score Log'

    def test_export_with_no_entries_raises_no_scores_error(self, tmp_path: Path) -> None:
        """Exporting an empty score log raises NoScoresError and never calls the composer."""
        repository = create_autospec(ScoreRepository, instance=True)
        repository.find_all.return_value = []
        composer = create_autospec(ScoreLogComposer, instance=True)
        command = ExportScoreLogCommand(repository, composer)

        with pytest.raises(NoScoresError):
            command(tmp_path / 'score-log.md')

        composer.compose.assert_not_called()
