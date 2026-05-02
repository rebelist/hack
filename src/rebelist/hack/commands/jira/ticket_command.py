from rebelist.hack.domain.models import Ticket
from rebelist.hack.infrastructure.jira import JiraGateway, JiraTicketComposer


class CreateJiraTicketCommand:
    def __init__(self, jira_ticket_composer: JiraTicketComposer, jira_gateway: JiraGateway) -> None:
        self.__jira_ticket_composer = jira_ticket_composer
        self.__jira_gateway = jira_gateway

    def __call__(self, description: str) -> Ticket:
        """Create a new jira ticket with the given description."""
        ticket = self.__jira_ticket_composer.compose(description)
        self.__jira_gateway.add_ticket(ticket)

        return ticket
