"""Tests for the SQLite-backed ScoreRepository.

The repository owns a real, on-disk SQLite database — there is no external
service or binary to stub, so each test exercises a genuine temporary database
created under `tmp_path`. This mirrors how the GitManager test drives its real
boundary, just without a network or subprocess. For the failure paths, the
stdlib `sqlite3.connect` entry point is replaced with a `create_autospec`'d
stand-in that raises, keeping the single mock-construction mechanism.
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import create_autospec

import pytest
from pytest_mock import MockerFixture

from rebelist.hack.domain.models import Score
from rebelist.hack.infrastructure.sqlite import repository as repository_module
from rebelist.hack.infrastructure.sqlite.repository import ScoreRepository, ScoreRepositoryError


def _install_connect_mock(mocker: MockerFixture, error: Exception) -> Any:
    """Replace sqlite3.connect inside the repository module with an autospec'd callable that raises."""
    connect_mock = create_autospec(sqlite3.connect, side_effect=error)
    mocker.patch.object(repository_module.sqlite3, 'connect', new=connect_mock)
    return connect_mock


@pytest.mark.unit
class TestScoreRepository:
    """Verify the repository creates its schema, round-trips entries, and orders them newest-first."""

    def test_initialization_creates_database_file_and_parent_dirs(self, tmp_path: Path) -> None:
        """Constructing the repository creates the database file, including any missing parent directories."""
        database_path = tmp_path / 'nested' / 'hack.db'

        ScoreRepository(database_path)

        assert database_path.exists()

    def test_save_persists_entry_and_stamps_id_and_created_at(self, tmp_path: Path) -> None:
        """save() stores the description and returns a copy carrying the DB-assigned id and creation timestamp."""
        repository = ScoreRepository(tmp_path / 'hack.db')

        stored = repository.save(Score(description='Stabilized the deployment pipeline.'))

        assert stored.entry_id == 1
        assert stored.description == 'Stabilized the deployment pipeline.'
        assert isinstance(stored.created_at, datetime)

    def test_find_all_on_empty_database_returns_empty_list(self, tmp_path: Path) -> None:
        """A freshly initialized database has no entries to return."""
        repository = ScoreRepository(tmp_path / 'hack.db')

        assert repository.find_all() == []

    def test_find_all_returns_every_saved_entry(self, tmp_path: Path) -> None:
        """All persisted entries are returned by find_all()."""
        repository = ScoreRepository(tmp_path / 'hack.db')
        repository.save(Score(description='First achievement.'))
        repository.save(Score(description='Second achievement.'))

        descriptions = {score.description for score in repository.find_all()}

        assert descriptions == {'First achievement.', 'Second achievement.'}

    def test_find_all_orders_entries_oldest_first(self, tmp_path: Path) -> None:
        """Entries are returned chronologically ascending (oldest first), by insertion order."""
        repository = ScoreRepository(tmp_path / 'hack.db')
        repository.save(Score(description='Older achievement.'))
        repository.save(Score(description='Newer achievement.'))

        scores = repository.find_all()

        assert scores[0].description == 'Older achievement.'
        assert scores[1].description == 'Newer achievement.'

    def test_find_all_assigns_sequential_entry_ids(self, tmp_path: Path) -> None:
        """Each returned entry carries its row identifier, counting up from one in insertion order."""
        repository = ScoreRepository(tmp_path / 'hack.db')
        repository.save(Score(description='First achievement.'))
        repository.save(Score(description='Second achievement.'))

        scores = repository.find_all()

        assert [score.entry_id for score in scores] == [1, 2]

    def test_find_all_parses_created_at_into_datetime(self, tmp_path: Path) -> None:
        """The stored timestamp is read back and parsed into a datetime instance."""
        repository = ScoreRepository(tmp_path / 'hack.db')
        repository.save(Score(description='An achievement.'))

        (score,) = repository.find_all()

        assert isinstance(score.created_at, datetime)

    def test_data_persists_across_repository_instances(self, tmp_path: Path) -> None:
        """The schema uses CREATE TABLE IF NOT EXISTS, so re-opening the database keeps existing rows."""
        database_path = tmp_path / 'hack.db'
        ScoreRepository(database_path).save(Score(description='Durable achievement.'))

        reopened = ScoreRepository(database_path)

        assert [score.description for score in reopened.find_all()] == ['Durable achievement.']

    def test_delete_removes_entry_and_returns_it(self, tmp_path: Path) -> None:
        """delete() removes the matching row and returns the deleted entry, leaving the others intact."""
        repository = ScoreRepository(tmp_path / 'hack.db')
        repository.save(Score(description='Keep me.'))
        repository.save(Score(description='Delete me.'))

        deleted = repository.delete(2)

        assert deleted is not None
        assert deleted.entry_id == 2
        assert deleted.description == 'Delete me.'
        assert [score.description for score in repository.find_all()] == ['Keep me.']

    def test_delete_unknown_id_returns_none(self, tmp_path: Path) -> None:
        """Deleting an id that does not exist returns None and leaves the data untouched."""
        repository = ScoreRepository(tmp_path / 'hack.db')
        repository.save(Score(description='Only one.'))

        assert repository.delete(99) is None
        assert len(repository.find_all()) == 1

    def test_delete_all_removes_every_entry_and_returns_count(self, tmp_path: Path) -> None:
        """delete_all() empties the table and returns the number of entries removed."""
        repository = ScoreRepository(tmp_path / 'hack.db')
        repository.save(Score(description='First achievement.'))
        repository.save(Score(description='Second achievement.'))

        removed = repository.delete_all()

        assert removed == 2
        assert repository.find_all() == []

    def test_delete_all_on_empty_database_returns_zero(self, tmp_path: Path) -> None:
        """Truncating an already-empty score log removes nothing and reports a count of zero."""
        repository = ScoreRepository(tmp_path / 'hack.db')

        assert repository.delete_all() == 0


@pytest.mark.unit
class TestScoreRepositoryErrorHandling:
    """Verify low-level sqlite failures are surfaced as ScoreRepositoryError."""

    def test_initialization_failure_raises_repository_error(self, mocker: MockerFixture, tmp_path: Path) -> None:
        """A sqlite error during schema creation is wrapped as a ScoreRepositoryError."""
        _install_connect_mock(mocker, sqlite3.OperationalError('unable to open database file'))

        with pytest.raises(ScoreRepositoryError) as exc_info:
            ScoreRepository(tmp_path / 'hack.db')

        assert 'unable to open database file' in str(exc_info.value)

    def test_save_failure_raises_repository_error(self, mocker: MockerFixture, tmp_path: Path) -> None:
        """A sqlite error raised while saving is wrapped as a ScoreRepositoryError."""
        repository = ScoreRepository(tmp_path / 'hack.db')
        _install_connect_mock(mocker, sqlite3.OperationalError('database is locked'))

        with pytest.raises(ScoreRepositoryError) as exc_info:
            repository.save(Score(description='An achievement.'))

        assert 'database is locked' in str(exc_info.value)

    def test_find_all_failure_raises_repository_error(self, mocker: MockerFixture, tmp_path: Path) -> None:
        """A sqlite error raised while reading is wrapped as a ScoreRepositoryError."""
        repository = ScoreRepository(tmp_path / 'hack.db')
        _install_connect_mock(mocker, sqlite3.OperationalError('disk I/O error'))

        with pytest.raises(ScoreRepositoryError) as exc_info:
            repository.find_all()

        assert 'disk I/O error' in str(exc_info.value)

    def test_delete_failure_raises_repository_error(self, mocker: MockerFixture, tmp_path: Path) -> None:
        """A sqlite error raised while deleting is wrapped as a ScoreRepositoryError."""
        repository = ScoreRepository(tmp_path / 'hack.db')
        _install_connect_mock(mocker, sqlite3.OperationalError('database is locked'))

        with pytest.raises(ScoreRepositoryError) as exc_info:
            repository.delete(1)

        assert 'database is locked' in str(exc_info.value)

    def test_delete_all_failure_raises_repository_error(self, mocker: MockerFixture, tmp_path: Path) -> None:
        """A sqlite error raised while truncating is wrapped as a ScoreRepositoryError."""
        repository = ScoreRepository(tmp_path / 'hack.db')
        _install_connect_mock(mocker, sqlite3.OperationalError('disk I/O error'))

        with pytest.raises(ScoreRepositoryError) as exc_info:
            repository.delete_all()

        assert 'disk I/O error' in str(exc_info.value)
