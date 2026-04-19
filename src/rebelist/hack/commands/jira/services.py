from rebelist.hack.config.settings import JiraTicketSettings
from rebelist.hack.models.jira import CustomField, CustomFieldType, DraftTicket, Ticket


class TicketFactory:
    def __init__(self, settings: JiraTicketSettings) -> None:
        self.__settings = settings

    def create(self, draft_ticket: DraftTicket) -> Ticket:
        """Create a new jira ticket with the given draft ticket."""
        custom_fields: list[CustomField] = []

        for alias, custom_field_settings in self.__settings.custom_fields.items():
            custom_field = CustomField(
                field_id=custom_field_settings.name,
                field_type=CustomFieldType(custom_field_settings.field_type),
                alias=alias,
                value=custom_field_settings.default,
            )

            custom_fields.append(custom_field)

        ticket = Ticket(
            project=self.__settings.fields.project,
            summary=draft_ticket.summary,
            reporter=self.__settings.fields.reporter.default,
            description=draft_ticket.description,
            issue_type=draft_ticket.issue_type,
            custom_fields=custom_fields,
        )

        return ticket
