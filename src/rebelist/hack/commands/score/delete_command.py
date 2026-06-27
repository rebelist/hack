from rebelist.hack.domain.models import Score
from rebelist.hack.infrastructure.sqlite import ScoreRepository


class DeleteScoreCommand:
    def __init__(self, score_repository: ScoreRepository) -> None:
        self.__score_repository = score_repository

    def __call__(self, entry_id: int) -> Score | None:
        """Delete the score log entry with the given id, returning it or None when it does not exist."""
        return self.__score_repository.delete(entry_id)


class DeleteAllScoresCommand:
    def __init__(self, score_repository: ScoreRepository) -> None:
        self.__score_repository = score_repository

    def __call__(self) -> int:
        """Remove every score log entry, returning the number of entries deleted."""
        return self.__score_repository.delete_all()
