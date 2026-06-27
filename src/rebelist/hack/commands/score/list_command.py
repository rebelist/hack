from rebelist.hack.domain.models import Score
from rebelist.hack.infrastructure.sqlite import ScoreRepository


class ListScoresCommand:
    def __init__(self, score_repository: ScoreRepository) -> None:
        self.__score_repository = score_repository

    def __call__(self) -> list[Score]:
        """Return every stored score log entry, chronologically ascending (oldest first)."""
        return self.__score_repository.find_all()
