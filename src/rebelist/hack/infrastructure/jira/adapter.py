from typing import Any

from jira import JIRA, JIRAError
from rebelist.hack.config.settings import JiraIssueCustomFieldType, JiraSettings
from rebelist.hack.domain.models import Ticket


class JiraGatewayError(Exception):
    """Raised when the Jira gateway encounters an error."""


class JiraMapper:
    def __init__(self, settings: JiraSettings) -> None:
        self.__settings = settings

    def to_dict(self, ticket: Ticket) -> dict[str, Any]:
        """Map Jira ticket data to API payload dict."""
        data: dict[str, Any] = {
            'project': {'key': self.__settings.fields.project},
            'summary': ticket.summary,
            'issuetype': {'name': ticket.kind},
            'reporter': {'name': self.__settings.fields.reporter},
            'description': ticket.description,
        }

        for custom_field in self.__settings.custom_fields:
            if not custom_field.value:
                continue

            match custom_field.field_type:
                case JiraIssueCustomFieldType.USER:
                    data[custom_field.name] = {'name': str(custom_field.value)}
                case JiraIssueCustomFieldType.SELECT:
                    data[custom_field.name] = {'value': str(custom_field.value)}
                case JiraIssueCustomFieldType.MULTI_SELECT:
                    raw = custom_field.value
                    if isinstance(raw, str):
                        data[custom_field.name] = [{'value': raw}]
                    else:
                        data[custom_field.name] = [{'value': item} for item in raw]
                case JiraIssueCustomFieldType.TEXT:
                    data[custom_field.name] = custom_field.value

        return data


class JiraGateway:
    def __init__(self, client: JIRA, mapper: JiraMapper) -> None:
        self.__client = client
        self.__mapper = mapper

    def add_ticket(self, ticket: Ticket) -> Ticket:
        """Add a new jira ticket and return a copy with the assigned key."""
        data = self.__mapper.to_dict(ticket)

        try:
            issue = self.__client.create_issue(fields=data)
        except JIRAError as e:
            raise JiraGatewayError(e.text or str(e)) from e

        return ticket.model_copy(update={'key': issue.key})

    def get_ticket(self, key: str) -> Ticket:
        """Get a jira ticket."""
        try:
            issue = self.__client.issue(key)
        except JIRAError as e:
            raise JiraGatewayError(e.text or str(e)) from e

        ticket = Ticket(
            key=issue.key,
            summary=issue.fields.summary,
            kind=issue.fields.issuetype.name,
            description=getattr(issue.fields, 'description', '') or '',
        )
        return ticket
