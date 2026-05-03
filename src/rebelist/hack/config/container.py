from functools import cached_property

from jira import JIRA

from rebelist.hack.commands.git import CheckoutBranchCommand, CommitCommand
from rebelist.hack.commands.jira import CreateJiraTicketCommand
from rebelist.hack.config.settings import Settings
from rebelist.hack.infrastructure.git import GitBranchComposer, GitCommitComposer, GitManager
from rebelist.hack.infrastructure.jira import JiraGateway, JiraMapper, JiraTicketComposer


class Container:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @cached_property
    def jira_gateway(self) -> JiraGateway:
        """Jira connector instance."""
        return JiraGateway(
            JIRA(self.settings.jira.host, token_auth=self.settings.jira.token.get_secret_value()),
            JiraMapper(self.settings.jira),
        )

    @cached_property
    def create_ticket_command(self) -> CreateJiraTicketCommand:
        """Create-ticket command instance."""
        composer = JiraTicketComposer(self.settings.agent.model, self.settings.jira)
        return CreateJiraTicketCommand(composer, self.jira_gateway)

    @cached_property
    def git_checkout_branch_command(self) -> CheckoutBranchCommand:
        """Checkout-branch command instance."""
        composer = GitBranchComposer(self.settings.agent.model, self.settings.git)
        return CheckoutBranchCommand(self.jira_gateway, composer, self.git_manager)

    @cached_property
    def git_commit_command(self) -> CommitCommand:
        """Commit command instance."""
        composer = GitCommitComposer(self.settings.agent.model)
        return CommitCommand(composer, self.git_manager)

    @cached_property
    def git_manager(self) -> GitManager:
        """Git manager instance."""
        return GitManager()
