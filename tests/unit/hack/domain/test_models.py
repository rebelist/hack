from datetime import datetime

import pytest
from pydantic import ValidationError

from rebelist.hack.domain.models import Branch, Commit, Score, Ticket


@pytest.mark.unit
class TestTicket:
    """Verify Ticket validation and stripping behaviour."""

    def test_constructs_with_minimum_fields(self) -> None:
        """A Ticket can be built with summary/kind/description; key defaults to None."""
        ticket = Ticket(summary='Fix login', kind='Bug', description='h2. Steps')

        assert ticket.key is None
        assert ticket.summary == 'Fix login'
        assert ticket.kind == 'Bug'
        assert ticket.description == 'h2. Steps'

    def test_strips_whitespace_on_string_fields(self) -> None:
        """str_strip_whitespace is enabled, so leading/trailing whitespace is removed."""
        ticket = Ticket(summary='  Fix login  ', kind=' Bug ', description='   h2. Steps   ')

        assert ticket.summary == 'Fix login'
        assert ticket.kind == 'Bug'
        assert ticket.description == 'h2. Steps'

    def test_is_frozen(self) -> None:
        """Ticket is immutable; the gateway returns a fresh copy with the assigned key."""
        ticket = Ticket(summary='S', kind='Bug', description='D')

        with pytest.raises(ValidationError):
            ticket.key = 'MD-1234'

    def test_model_copy_returns_new_ticket_with_key(self) -> None:
        """Persistence flow uses model_copy to obtain a keyed ticket without mutation."""
        ticket = Ticket(summary='S', kind='Bug', description='D')

        keyed = ticket.model_copy(update={'key': 'MD-1234'})

        assert ticket.key is None
        assert keyed.key == 'MD-1234'


@pytest.mark.unit
class TestBranch:
    """Verify Branch kebab-case constraints, length cap, and immutability."""

    def test_accepts_valid_kebab_case_name(self) -> None:
        """A valid kebab-case lowercase name is accepted."""
        branch = Branch(prefix='feature', name='fix-php-worker-memory-leak')

        assert branch.prefix == 'feature'
        assert branch.name == 'fix-php-worker-memory-leak'

    def test_lowercases_uppercase_letters_in_name(self) -> None:
        """to_lower normalizes uppercase input — LLMs are non-deterministic so silent correction is preferable."""
        branch = Branch(prefix='feature', name='Fix-Memory-Leak')

        assert branch.name == 'fix-memory-leak'

    def test_coalesces_whitespace_into_hyphens(self) -> None:
        """The pre-validator joins whitespace-separated tokens with hyphens before pattern check."""
        branch = Branch(prefix='feature', name='fix memory leak')

        assert branch.name == 'fix-memory-leak'

    def test_collapses_multiple_spaces(self) -> None:
        """Adjacent whitespace runs collapse to a single hyphen via str.split() + '-'.join()."""
        branch = Branch(prefix='feature', name='fix   memory\tleak')

        assert branch.name == 'fix-memory-leak'

    def test_rejects_underscores_in_name(self) -> None:
        """Underscores are not part of the kebab-case alphabet."""
        with pytest.raises(ValidationError):
            Branch(prefix='feature', name='fix_memory_leak')

    def test_rejects_name_above_60_chars(self) -> None:
        """Branch.name has a 60-char hard cap."""
        with pytest.raises(ValidationError):
            Branch(prefix='feature', name='a' + ('-b' * 40))

    def test_is_frozen(self) -> None:
        """Branch is immutable — the project pattern."""
        branch = Branch(prefix='feature', name='fix-bug')

        with pytest.raises(ValidationError):
            branch.prefix = 'bugfix'


@pytest.mark.unit
class TestCommit:
    """Verify Commit subject/body constraints and post-construction subject mutation."""

    def test_constructs_with_subject_only(self) -> None:
        """Body defaults to an empty string."""
        commit = Commit(subject='Fix login bug')

        assert commit.subject == 'Fix login bug'
        assert commit.body == ''

    def test_rejects_subject_above_50_chars(self) -> None:
        """Subjects are capped at 50 characters."""
        with pytest.raises(ValidationError):
            Commit(subject='a' * 51)

    def test_accepts_body_up_to_1000_chars(self) -> None:
        """Body cap matches the prompt: 1000 characters."""
        body = 'a' * 1000
        commit = Commit(subject='Fix', body=body)

        assert commit.body == body

    def test_rejects_body_above_1000_chars(self) -> None:
        """Body above 1000 chars must fail validation."""
        with pytest.raises(ValidationError):
            Commit(subject='Fix', body='a' * 1001)

    def test_is_frozen(self) -> None:
        """Commit is immutable; ticket-prefixing uses model_copy to produce a fresh instance."""
        commit = Commit(subject='Fix login bug')

        with pytest.raises(ValidationError):
            commit.subject = 'WS-120 Fix login bug'

    def test_model_copy_yields_prefixed_commit(self) -> None:
        """The composer's prefix step is expressed via model_copy; original is untouched."""
        commit = Commit(subject='Fix login bug')

        prefixed = commit.model_copy(update={'subject': 'WS-120 Fix login bug'})

        assert commit.subject == 'Fix login bug'
        assert prefixed.subject == 'WS-120 Fix login bug'


@pytest.mark.unit
class TestScore:
    """Verify Score validation, stripping, and the repository-assigned timestamp pattern."""

    def test_constructs_with_description_only(self) -> None:
        """A Score can be built from a description alone; entry_id and created_at default to None until persisted."""
        score = Score(description='Stabilized the deployment pipeline.')

        assert score.entry_id is None
        assert score.created_at is None
        assert score.description == 'Stabilized the deployment pipeline.'

    def test_model_copy_assigns_entry_id(self) -> None:
        """The repository stamps the row identifier via model_copy without mutating the original."""
        score = Score(description='Shipped the feature.')

        stamped = score.model_copy(update={'entry_id': 7})

        assert score.entry_id is None
        assert stamped.entry_id == 7

    def test_strips_whitespace_on_description(self) -> None:
        """str_strip_whitespace is enabled, so surrounding whitespace is removed."""
        score = Score(description='   Mentored two engineers.   ')

        assert score.description == 'Mentored two engineers.'

    def test_rejects_empty_description(self) -> None:
        """An empty (or whitespace-only) description is not a valid achievement entry."""
        with pytest.raises(ValidationError):
            Score(description='   ')

    def test_is_frozen(self) -> None:
        """Score is immutable; the repository returns a fresh copy carrying the assigned timestamp."""
        score = Score(description='Shipped the feature.')

        with pytest.raises(ValidationError):
            score.description = 'Changed.'

    def test_model_copy_assigns_created_at(self) -> None:
        """The persistence flow uses model_copy to stamp created_at without mutating the original."""
        score = Score(description='Shipped the feature.')
        timestamp = datetime(2026, 3, 12, 9, 30, 0)

        stamped = score.model_copy(update={'created_at': timestamp})

        assert score.created_at is None
        assert stamped.created_at == timestamp
