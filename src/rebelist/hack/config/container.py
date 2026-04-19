from jira import JIRA

from rebelist.hack.commands.jira import CreateJiraTicketCommand
from rebelist.hack.commands.jira.services import TicketFactory
from rebelist.hack.config.settings import Settings
from rebelist.hack.connectors import JiraGateway
from rebelist.hack.connectors.agents import JiraTicketAgent


class Container:
    def __init__(self, settings: Settings) -> None:
        self.settings: Settings = settings
        self.__jira: JiraGateway | None = None
        self.__create_jira_ticket_command: CreateJiraTicketCommand | None = None
        self.__ticket_factory: TicketFactory | None = None

    @property
    def jira_gateway(self) -> JiraGateway:
        """Jira connector instance."""
        instance = self.__jira
        if instance is None:
            host = self.settings.jira.host.strip()
            token = self.settings.jira.token.strip()
            if not host:
                msg = 'Jira host is not configured.'
                raise ValueError(msg)
            if not token:
                msg = 'Jira token is not configured.'
                raise ValueError(msg)
            client = JIRA(host, token_auth=token)
            instance = JiraGateway(client)
            self.__jira = instance

        return instance

    @property
    def ticket_factory(self) -> TicketFactory:
        """Build `Ticket` instances from agent output using user YAML settings."""
        instance = self.__ticket_factory
        if instance is None:
            instance = TicketFactory(self.settings.jira)
            self.__ticket_factory = instance

        return instance

    @property
    def create_ticket_command(self) -> CreateJiraTicketCommand:
        """Create a jira ticket command instance."""
        instance = self.__create_jira_ticket_command
        if instance is None:
            agent = JiraTicketAgent(self.settings.agent.model, self.settings.jira)
            instance = CreateJiraTicketCommand(self.ticket_factory, agent, self.jira_gateway)
            self.__create_jira_ticket_command = instance

        return instance
