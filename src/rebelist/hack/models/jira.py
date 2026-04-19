from enum import StrEnum, auto
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field


class CustomFieldType(StrEnum):
    """Interaction type for a Jira custom field."""

    SELECT = auto()
    MULTI_SELECT = auto()
    USER = auto()
    TEXT = auto()


class CustomField(BaseModel):
    """A resolved Jira custom field with its serialization rules."""

    model_config = ConfigDict(str_strip_whitespace=True)

    field_id: Annotated[
        str,
        Field(pattern=r'^customfield_\d+$', description="Internal Jira custom field ID (e.g., 'customfield_13207')."),
    ]
    field_type: Annotated[CustomFieldType, Field(description='The type of the resolved value for this field.')]
    alias: Annotated[str, Field(description='Human readable name for the custom field.')]
    value: Annotated[str | list[str] | None, Field(description='The resolved value for this field.')]


class DraftTicket(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    summary: Annotated[str, Field(default=None, description='Issue title.')]
    issue_type: Annotated[str, Field(description='Category that defines the nature of the work item.')]
    description: Annotated[str, Field(description='Jira ticket description in Wiki Markup style.')]


class Ticket(BaseModel):
    """A jira ticket representation."""

    model_config = ConfigDict(str_strip_whitespace=True)

    project: Annotated[str, Field(description="Jira project key (e.g. 'WS').")]
    summary: Annotated[str, Field(default=None, description='Ticket title or short summary.')]
    reporter: Annotated[str, Field(description='Jira username of the issue reporter.')]
    description: Annotated[str, Field(description='Description of the issue in Wiki style markup.')]
    issue_type: Annotated[
        str,
        BeforeValidator(lambda v: v.title() if isinstance(v, str) else v),
        Field(description='Category that defines the nature of the work item.'),
    ]
    custom_fields: Annotated[
        list[CustomField],
        Field(
            default_factory=list,
            description='Dynamic custom fields.',
        ),
    ]
