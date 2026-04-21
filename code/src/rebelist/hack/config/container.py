from functools import cached_property

from jira import JIRA

from rebelist.hack.commands.jira import CreateJiraTicketCommand
from rebelist.hack.commands.jira.services import TicketFactory
from rebelist.hack.config.settings import Settings
from rebelist.hack.connectors import JiraGateway
from rebelist.hack.connectors.agents import JiraTicketAgent


class Container:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @cached_property
    def jira_gateway(self) -> JiraGateway:
        """Jira connector instance."""
        host = self.settings.jira.host.strip()
        token = self.settings.jira.token.strip()
        if not host:
            msg = 'Jira host is not configured.'
            raise ValueError(msg)
        if not token:
            msg = 'Jira token is not configured.'
            raise ValueError(msg)
        client = JIRA(host, token_auth=token)
        return JiraGateway(client)

    @cached_property
    def ticket_factory(self) -> TicketFactory:
        """Build `Ticket` instances from agent output using user YAML settings."""
        return TicketFactory(self.settings.jira)

    @cached_property
    def create_ticket_command(self) -> CreateJiraTicketCommand:
        """Create a jira ticket command instance."""
        agent = JiraTicketAgent(self.settings.agent.model, self.settings.jira)
        return CreateJiraTicketCommand(self.ticket_factory, agent, self.jira_gateway)
