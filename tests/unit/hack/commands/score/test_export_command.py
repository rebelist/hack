from datetime import datetime
from pathlib import Path
from unittest.mock import create_autospec

import pytest

from rebelist.hack.commands.score.export_command import ExportScoreLogCommand, NoScoresError
from rebelist.hack.domain.models import Score
from rebelist.hack.domain.score_log import ScoreLogFormatter
from rebelist.hack.infrastructure.sqlite import ScoreRepository


def _scores() -> list[Score]:
    return [
        Score(created_at=datetime(2026, 3, 12, 9, 30, 0), description='Stabilized the deployment pipeline.'),
        Score(created_at=datetime(2026, 5, 1, 14, 0, 0), description='Mentored two engineers.'),
    ]


@pytest.mark.unit
class TestExportScoreLogCommand:
    """Verify the use-case loads entries, formats a score log, and writes the markdown file."""

    def test_full_flow_writes_markdown_to_file(self, tmp_path: Path) -> None:
        """The command loads every entry, asks the formatter for markdown, and writes it to the given path."""
        repository = create_autospec(ScoreRepository, instance=True)
        repository.find_all.return_value = _scores()
        formatter = create_autospec(ScoreLogFormatter, instance=True)
        formatter.format.return_value = '# Score Log\n- entry'
        command = ExportScoreLogCommand(repository, formatter)
        destination = tmp_path / 'score-log.md'

        result = command(destination)

        repository.find_all.assert_called_once()
        formatter.format.assert_called_once_with(_scores())
        assert destination.read_text(encoding='utf-8') == '# Score Log\n- entry'
        assert result == '# Score Log\n- entry'

    def test_dry_run_returns_markdown_without_writing(self, tmp_path: Path) -> None:
        """With dry_run=True the markdown is returned but no file is written."""
        repository = create_autospec(ScoreRepository, instance=True)
        repository.find_all.return_value = _scores()
        formatter = create_autospec(ScoreLogFormatter, instance=True)
        formatter.format.return_value = '# Score Log'
        command = ExportScoreLogCommand(repository, formatter)
        destination = tmp_path / 'score-log.md'

        result = command(destination, dry_run=True)

        assert not destination.exists()
        assert result == '# Score Log'

    def test_export_with_no_entries_raises_no_scores_error(self, tmp_path: Path) -> None:
        """Exporting an empty score log raises NoScoresError and never calls the formatter."""
        repository = create_autospec(ScoreRepository, instance=True)
        repository.find_all.return_value = []
        formatter = create_autospec(ScoreLogFormatter, instance=True)
        command = ExportScoreLogCommand(repository, formatter)

        with pytest.raises(NoScoresError):
            command(tmp_path / 'score-log.md')

        formatter.format.assert_not_called()
