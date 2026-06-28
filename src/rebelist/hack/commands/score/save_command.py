from rebelist.hack.domain.models import Score
from rebelist.hack.infrastructure.agent import ScoreComposer
from rebelist.hack.infrastructure.sqlite import ScoreRepository


class SaveScoreCommand:
    def __init__(self, score_composer: ScoreComposer, score_repository: ScoreRepository) -> None:
        self.__score_composer = score_composer
        self.__score_repository = score_repository

    def __call__(self, description: str, dry_run: bool = False) -> Score:
        """Clean up and categorize a raw achievement note and persist it as a score log entry."""
        draft = self.__score_composer.compose(description)
        score = Score(description=draft.description, category=draft.category)
        if dry_run:
            return score
        return self.__score_repository.save(score)
