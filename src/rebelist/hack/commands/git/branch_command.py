from rebelist.hack.infrastructure.git import GitBranchComposer, GitManager
from rebelist.hack.infrastructure.jira import JiraGateway


class CheckoutBranchCommand:
    def __init__(
        self, jira_gateway: JiraGateway, git_branch_composer: GitBranchComposer, git_manager: GitManager
    ) -> None:
        self.__git_branch_composer = git_branch_composer
        self.__jira_gateway = jira_gateway
        self.__git_manager = git_manager

    def __call__(self, ticket_key: str) -> str:
        """Create a git branch."""
        ticket = self.__jira_gateway.get_ticket(ticket_key)
        branch = self.__git_branch_composer.compose(ticket)
        name = f'{branch.prefix}/{ticket.key}-{branch.name}'
        output = self.__git_manager.checkout_branch(name)

        return output
