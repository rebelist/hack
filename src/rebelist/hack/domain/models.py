from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator


class Ticket(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)
    key: Annotated[str | None, Field(description="Unique identifier (e.g., 'MD-1234').")] = None
    summary: Annotated[str, Field(description='Descriptive headline of the task.')]
    kind: Annotated[str, Field(description='Category that defines the nature of the work item.')]
    description: Annotated[str, Field(description='Contextual details in Wiki Markup style.')]


class Branch(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)
    prefix: Annotated[str, StringConstraints(to_lower=True), Field(description='The branch category.')]
    name: Annotated[
        str,
        StringConstraints(pattern=r'^[a-z0-9]+(?:-[a-z0-9]+)*$', max_length=60),
        Field(description="Kebab-case summary of the task (e.g., 'fix-php-worker-memory-leak')."),
    ]

    @field_validator('name', mode='before')
    @classmethod
    def _format_kebab_case(cls, v: str) -> str:
        """Normalize to lowercase kebab-case before pattern validation."""
        return '-'.join(v.lower().split())


class Commit(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)
    subject: Annotated[
        str,
        StringConstraints(max_length=50),
        Field(description='A concise, imperative summary of the change. Capitalized, no period.'),
    ]

    body: Annotated[
        str,
        StringConstraints(max_length=1000),
        Field(
            description='Rationale for change. Wrap at 72 chars per line. Empty if trivial.',
        ),
    ] = ''


class Score(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)
    entry_id: Annotated[
        int | None,
        Field(description='Row identifier, assigned by the repository when the entry is read or persisted.'),
    ] = None
    created_at: Annotated[
        datetime | None,
        Field(description='Creation timestamp, assigned by the repository when the entry is persisted.'),
    ] = None
    description: Annotated[
        str,
        StringConstraints(min_length=1),
        Field(description='A single score log achievement entry, lightly cleaned up by the LLM.'),
    ]
    category: Annotated[
        str | None,
        Field(description='Best-fit category assigned by the LLM at save time; None for legacy entries.'),
    ] = None


class ScoreDraft(BaseModel):
    """LLM cleanup output: a tidied achievement entry paired with its best-fit category."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)
    description: Annotated[
        str,
        StringConstraints(min_length=1),
        Field(description='The lightly cleaned-up achievement entry text.'),
    ]
    category: Annotated[
        str,
        StringConstraints(min_length=1),
        Field(description="A single best-fit category (e.g. 'Engineering', 'Leadership', 'Mentorship')."),
    ]
