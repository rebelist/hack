from typing import Any

from jira import JIRA

from rebelist.hack.config.settings import JiraSettings
from rebelist.hack.models.jira import CustomFieldType, Ticket


class JiraTicketMapper:
    @staticmethod
    def map(ticket: Ticket) -> dict[str, Any]:
        """Map Jira ticket data to API payload dict."""
        data: dict[str, Any] = {
            'project': {'key': ticket.project},
            'summary': ticket.summary,
            'issuetype': {'name': ticket.issue_type},
            'reporter': {'name': ticket.reporter},
            'description': ticket.description,
        }

        for custom_field in ticket.custom_fields:
            if not custom_field.value:
                continue

            match custom_field.field_type:
                case CustomFieldType.USER:
                    data[custom_field.field_id] = {'name': str(custom_field.value)}
                case CustomFieldType.SELECT:
                    data[custom_field.field_id] = {'value': str(custom_field.value)}
                case CustomFieldType.MULTI_SELECT:
                    data[custom_field.field_id] = [{'value': item} for item in custom_field.value]
                case CustomFieldType.TEXT:
                    data[custom_field.field_id] = custom_field.value

        return data


class JiraGateway:
    def __init__(self, client: JIRA, settings: JiraSettings) -> None:
        self.__client = client
        self.__settings = settings

    def add_ticket(self, ticket: Ticket) -> str:
        """Create a new jira ticket."""
        data = JiraTicketMapper.map(ticket)
        issue = self.__client.create_issue(fields=data)
        return issue.key
