from textwrap import dedent
from typing import Final

from pydantic_ai import Agent, RunContext

from rebelist.hack.domain.models import ScoreDraft


class ScoreComposer:
    SYSTEM_PROMPT: Final[str] = dedent("""
        ## Role
        You are an editor that lightly cleans up a single score log achievement entry and files it
        under a best-fit category.

        ## Task
        Take the user's raw note about something they accomplished and return a tidied version of it
        together with the single category that best describes it.

        ## Constraints
        - Fix grammar, spelling, and punctuation.
        - Tighten the wording, but stay close to the original meaning and length.
        - Do NOT rewrite it into a grandiose statement, invent impact, or add facts.
        - Keep it as a concise, first-person-friendly description of the achievement.
        - Preserve concrete details the user provided (names, systems, numbers).

        ## Category
        - Choose ONE concise category that best fits the achievement, e.g. `Engineering`,
          `Leadership`, `Management`, `Communication`, `Mentorship`.
        - Invent a sensible single category if none of the examples fit.

        ## Output
        Return a `ScoreDraft` with the cleaned-up entry text and its category. No preamble or commentary.
    """).strip()

    def __init__(self, model: str) -> None:
        self.__agent = Agent(model, output_type=ScoreDraft)
        self.__agent.system_prompt(self.__build_system_prompt)

    def compose(self, description: str) -> ScoreDraft:
        """Lightly clean up a raw achievement note and return the tidied text with its best-fit category."""
        result = self.__agent.run_sync(description)
        return result.output

    def __build_system_prompt(self, _: RunContext) -> str:
        return self.SYSTEM_PROMPT
