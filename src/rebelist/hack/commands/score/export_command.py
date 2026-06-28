from pathlib import Path

from rebelist.hack.domain.score_log import ScoreLogFormatter
from rebelist.hack.infrastructure.sqlite import ScoreRepository


class NoScoresError(Exception):
    """Raised when a score log export is requested but no achievements have been recorded yet."""


class ExportScoreLogCommand:
    def __init__(self, score_repository: ScoreRepository, score_log_formatter: ScoreLogFormatter) -> None:
        self.__score_repository = score_repository
        self.__score_log_formatter = score_log_formatter

    def __call__(self, file_path: Path, dry_run: bool = False) -> str:
        """Format a categorized score log from all stored entries and write it to a Markdown file."""
        scores = self.__score_repository.find_all()
        if not scores:
            raise NoScoresError('No achievements recorded yet. Use `hack score save "..."` to add one.')

        markdown = self.__score_log_formatter.format(scores)
        if not dry_run:
            file_path.write_text(markdown, encoding='utf-8')
        return markdown
