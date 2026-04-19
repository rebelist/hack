from rebelist.hack.commands.jira.services import TicketFactory
from rebelist.hack.connectors import JiraGateway
from rebelist.hack.connectors.agents import JiraTicketAgent


class CreateJiraTicketCommand:
    def __init__(self, ticket_factory: TicketFactory, agent: JiraTicketAgent, jira_gateway: JiraGateway) -> None:
        self.__ticket_factory = ticket_factory
        self.__agent = agent
        self.__jira_gateway = jira_gateway

    def __call__(self, description: str) -> str:
        """Create a new jira ticket with the given description."""
        draft_ticket = self.__agent.run(description)
        ticket = self.__ticket_factory.create(draft_ticket)
        key = self.__jira_gateway.add_ticket(ticket)

        return key
