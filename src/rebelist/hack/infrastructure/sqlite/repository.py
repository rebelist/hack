import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Final

from rebelist.hack.domain.models import Score


class ScoreRepositoryError(Exception):
    """Raised when the score repository cannot read from or write to the database."""


class ScoreRepository:
    CREATE_TABLE: Final[str] = (
        'CREATE TABLE IF NOT EXISTS scores ('
        'created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, '
        'description TEXT NOT NULL, '
        'category TEXT)'
    )
    ADD_CATEGORY_COLUMN: Final[str] = 'ALTER TABLE scores ADD COLUMN category TEXT'
    TABLE_COLUMNS: Final[str] = 'PRAGMA table_info(scores)'
    INSERT_SCORE: Final[str] = 'INSERT INTO scores (description, category) VALUES (?, ?)'
    SELECT_BY_ID: Final[str] = 'SELECT rowid, created_at, description, category FROM scores WHERE rowid = ?'
    SELECT_ALL: Final[str] = 'SELECT rowid, created_at, description, category FROM scores ORDER BY rowid ASC'
    COUNT_ALL: Final[str] = 'SELECT COUNT(*) FROM scores'
    DELETE_BY_ID: Final[str] = 'DELETE FROM scores WHERE rowid = ?'
    DELETE_ALL: Final[str] = 'DELETE FROM scores'

    def __init__(self, database_path: Path) -> None:
        self.__database_path = database_path
        self.__initialize()

    def save(self, score: Score) -> Score:
        """Persist a score entry and return a copy stamped with the database-assigned id and creation time."""
        try:
            with closing(self.__connect()) as connection, connection:
                cursor = connection.execute(self.INSERT_SCORE, (score.description, score.category))
                row = connection.execute(self.SELECT_BY_ID, (cursor.lastrowid,)).fetchone()
        except sqlite3.Error as error:
            raise ScoreRepositoryError(str(error)) from error

        return self.__to_score(row)

    def find_all(self) -> list[Score]:
        """Return every stored score entry, chronologically ascending (oldest first)."""
        try:
            with closing(self.__connect()) as connection:
                rows = connection.execute(self.SELECT_ALL).fetchall()
        except sqlite3.Error as error:
            raise ScoreRepositoryError(str(error)) from error

        return [self.__to_score(row) for row in rows]

    def delete(self, entry_id: int) -> Score | None:
        """Delete the entry with the given id, returning it, or None when no such entry exists."""
        try:
            with closing(self.__connect()) as connection, connection:
                row = connection.execute(self.SELECT_BY_ID, (entry_id,)).fetchone()
                if row is None:
                    return None
                connection.execute(self.DELETE_BY_ID, (entry_id,))
        except sqlite3.Error as error:
            raise ScoreRepositoryError(str(error)) from error

        return self.__to_score(row)

    def delete_all(self) -> int:
        """Remove every entry from the score log, returning the number of entries deleted."""
        try:
            with closing(self.__connect()) as connection, connection:
                count: int = connection.execute(self.COUNT_ALL).fetchone()[0]
                connection.execute(self.DELETE_ALL)
        except sqlite3.Error as error:
            raise ScoreRepositoryError(str(error)) from error

        return count

    def __initialize(self) -> None:
        """Create the parent directory and the scores table, migrating legacy schemas as needed."""
        self.__database_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with closing(self.__connect()) as connection, connection:
                connection.execute(self.CREATE_TABLE)
                columns = {row[1] for row in connection.execute(self.TABLE_COLUMNS).fetchall()}
                if 'category' not in columns:
                    connection.execute(self.ADD_CATEGORY_COLUMN)
        except sqlite3.Error as error:
            raise ScoreRepositoryError(str(error)) from error

    def __connect(self) -> sqlite3.Connection:
        """Open a new connection to the configured database file."""
        return sqlite3.connect(self.__database_path)

    @classmethod
    def __to_score(cls, row: tuple[int, str, str, str | None]) -> Score:
        """Build a Score from a ``(rowid, created_at, description, category)`` database row."""
        entry_id, created_at, description, category = row
        return Score(
            entry_id=entry_id,
            created_at=cls.__parse_timestamp(created_at),
            description=description,
            category=category,
        )

    @staticmethod
    def __parse_timestamp(value: str) -> datetime:
        """Parse a stored timestamp into a timezone-aware datetime.

        SQLite's ``CURRENT_TIMESTAMP`` default writes naive UTC text (``YYYY-MM-DD HH:MM:SS``); such
        values are tagged as UTC so callers can localize them for display. Values that already carry
        an offset are returned unchanged.
        """
        parsed = datetime.fromisoformat(value)
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)
