from jira import JIRA

from rebelist.hack.commands.jira import CreateJiraTicketCommand
from rebelist.hack.commands.jira.services import TicketFactory
from rebelist.hack.config.settings import AppSettings, UserSettings
from rebelist.hack.connectors import JiraGateway
from rebelist.hack.connectors.agents import JiraTicketAgent


class Container:
    def __init__(self, app_settings: AppSettings, user_settings: UserSettings) -> None:
        self.app_settings: AppSettings = app_settings
        self.user_settings: UserSettings = user_settings
        self.__jira: JiraGateway | None = None
        self.__create_jira_ticket_command: CreateJiraTicketCommand | None = None
        self.__ticket_factory: TicketFactory | None = None

    @property
    def jira_gateway(self) -> JiraGateway:
        """Jira connector instance."""
        instance = self.__jira
        if instance is None:
            client = JIRA(self.app_settings.jira.host, token_auth=self.app_settings.jira.token)
            instance = JiraGateway(client, settings=self.app_settings.jira)
            self.__jira = instance

        return instance

    @property
    def ticket_factory(self) -> TicketFactory:
        """Jira gateway instance."""
        instance = self.__ticket_factory
        if instance is None:
            instance = TicketFactory(self.user_settings.jira)
            self.__ticket_factory = instance

        return instance

    @property
    def create_ticket_command(self) -> CreateJiraTicketCommand:
        """Create a jira ticket command instance."""
        instance = self.__create_jira_ticket_command
        if instance is None:
            agent = JiraTicketAgent(self.app_settings.agent.model, self.user_settings.jira)
            instance = CreateJiraTicketCommand(self.ticket_factory, agent, self.jira_gateway)
            self.__create_jira_ticket_command = instance

        return instance
