"""Tests for the deterministic score log Markdown formatter.

The formatter is a pure transformation over domain `Score` entries — no LLM,
no I/O — so each test feeds it constructed entries and asserts on the exact
Markdown it returns. Timestamps use midday local times so the rendered dates
stay stable regardless of the machine's timezone.
"""

from datetime import datetime

import pytest

from rebelist.hack.domain.models import Score
from rebelist.hack.domain.score_log import ScoreLogFormatter


@pytest.mark.unit
class TestScoreLogFormatter:
    """Verify the formatter renders a titled, dated, categorized Markdown score log."""

    def test_renders_title_intro_and_one_line_per_entry(self) -> None:
        """The log opens with a title and an intro stating the count and date range, then lists every entry."""
        formatter = ScoreLogFormatter()
        scores = [
            Score(
                created_at=datetime(2026, 3, 12, 9, 30), description='Stabilized the pipeline.', category='Engineering'
            ),
            Score(created_at=datetime(2026, 5, 1, 14, 0), description='Mentored two engineers.', category='Mentorship'),
        ]

        markdown = formatter.format(scores)

        assert markdown == (
            '# Score Log\n'
            '\n'
            'A record of 2 achievements logged between 2026-03-12 and 2026-05-01.\n'
            '\n'
            '- [2026-03-12 09:30] [Engineering] Stabilized the pipeline.\n'
            '- [2026-05-01 14:00] [Mentorship] Mentored two engineers.'
        )

    def test_single_entry_uses_singular_wording_and_on_date(self) -> None:
        """A lone entry is described in the singular and dated with `on <date>` rather than a range."""
        formatter = ScoreLogFormatter()
        scores = [
            Score(created_at=datetime(2026, 3, 12, 9, 30), description='Shipped onboarding.', category='Engineering')
        ]

        markdown = formatter.format(scores)

        assert 'A record of 1 achievement logged on 2026-03-12.' in markdown

    def test_entry_without_category_renders_uncategorized(self) -> None:
        """Legacy entries with no category are tagged `[Uncategorized]`."""
        formatter = ScoreLogFormatter()
        scores = [Score(created_at=datetime(2026, 3, 12, 9, 30), description='Legacy win.')]

        markdown = formatter.format(scores)

        assert '- [2026-03-12 09:30] [Uncategorized] Legacy win.' in markdown

    def test_entry_without_timestamp_renders_unknown(self) -> None:
        """An entry with no creation time renders its timestamp as `unknown`."""
        formatter = ScoreLogFormatter()
        scores = [Score(description='Undated win.', category='Engineering')]

        markdown = formatter.format(scores)

        assert '- [unknown] [Engineering] Undated win.' in markdown

    def test_intro_omits_range_when_no_entry_has_a_timestamp(self) -> None:
        """With no timestamps to bound, the intro states the count without a date range."""
        formatter = ScoreLogFormatter()
        scores = [Score(description='Undated win.', category='Engineering')]

        markdown = formatter.format(scores)

        assert 'A record of 1 achievement.' in markdown
