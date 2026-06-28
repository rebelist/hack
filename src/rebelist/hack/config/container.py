from functools import cached_property
from typing import Final

from jira import JIRA

from rebelist.hack.commands.git import CheckoutBranchCommand, CommitCommand
from rebelist.hack.commands.jira import CreateJiraTicketCommand
from rebelist.hack.commands.score import (
    DeleteAllScoresCommand,
    DeleteScoreCommand,
    ExportScoreLogCommand,
    ListScoresCommand,
    SaveScoreCommand,
)
from rebelist.hack.config.settings import Settings, YamlSettingsSource
from rebelist.hack.domain.score_log import ScoreLogFormatter
from rebelist.hack.infrastructure.agent import (
    GitBranchComposer,
    GitCommitComposer,
    JiraTicketComposer,
    ScoreComposer,
)
from rebelist.hack.infrastructure.git import GitManager
from rebelist.hack.infrastructure.jira import JiraGateway, JiraMapper
from rebelist.hack.infrastructure.sqlite import ScoreRepository


class Container:
    DATABASE_FILE_NAME: Final[str] = 'hack.db'

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

    @cached_property
    def score_repository(self) -> ScoreRepository:
        """Score repository instance, stored next to the user's config file."""
        database_path = YamlSettingsSource.get_user_config_path().parent / Container.DATABASE_FILE_NAME
        return ScoreRepository(database_path)

    @cached_property
    def score_save_command(self) -> SaveScoreCommand:
        """Save-score command instance."""
        composer = ScoreComposer(self.settings.agent.model)
        return SaveScoreCommand(composer, self.score_repository)

    @cached_property
    def score_export_command(self) -> ExportScoreLogCommand:
        """Export-score-log command instance."""
        return ExportScoreLogCommand(self.score_repository, ScoreLogFormatter())

    @cached_property
    def score_list_command(self) -> ListScoresCommand:
        """List-scores command instance."""
        return ListScoresCommand(self.score_repository)

    @cached_property
    def score_delete_command(self) -> DeleteScoreCommand:
        """Delete-score command instance."""
        return DeleteScoreCommand(self.score_repository)

    @cached_property
    def score_delete_all_command(self) -> DeleteAllScoresCommand:
        """Delete-all-scores command instance."""
        return DeleteAllScoresCommand(self.score_repository)
