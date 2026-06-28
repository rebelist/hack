from datetime import datetime

from rebelist.hack.domain.models import Score


class ScoreLogFormatter:
    """Render stored score entries into a titled, dated, categorized Markdown score log.

    This is a pure transformation — the entries are already cleaned and categorized at save time,
    so no LLM pass is needed and the output is deterministic regardless of how many entries it covers.
    """

    TITLE = '# Score Log'
    DEFAULT_CATEGORY = 'Uncategorized'
    UNKNOWN_TIMESTAMP = 'unknown'

    def format(self, scores: list[Score]) -> str:
        """Render the given entries (assumed oldest-first) as a Markdown document."""
        lines = [self.__format_entry(score) for score in scores]
        return f'{self.TITLE}\n\n{self.__intro(scores)}\n\n' + '\n'.join(lines)

    @classmethod
    def __intro(cls, scores: list[Score]) -> str:
        """Build the one-sentence summary stating how many achievements the log covers and over what dates."""
        noun = 'achievement' if len(scores) == 1 else 'achievements'
        dates = sorted(score.created_at for score in scores if score.created_at is not None)
        if not dates:
            return f'A record of {len(scores)} {noun}.'

        first, last = cls.__format_date(dates[0]), cls.__format_date(dates[-1])
        span = f'on {first}' if first == last else f'between {first} and {last}'
        return f'A record of {len(scores)} {noun} logged {span}.'

    @classmethod
    def __format_entry(cls, score: Score) -> str:
        """Render a single entry as `- [<timestamp>] [<category>] <description>`."""
        timestamp = cls.__format_timestamp(score.created_at)
        category = score.category or cls.DEFAULT_CATEGORY
        return f'- [{timestamp}] [{category}] {score.description}'

    @classmethod
    def __format_timestamp(cls, created_at: datetime | None) -> str:
        """Render a creation time in local time, or `unknown` when it is unset."""
        if created_at is None:
            return cls.UNKNOWN_TIMESTAMP
        return created_at.astimezone().strftime('%Y-%m-%d %H:%M')

    @staticmethod
    def __format_date(created_at: datetime) -> str:
        """Render a creation time as a local calendar date."""
        return created_at.astimezone().strftime('%Y-%m-%d')
