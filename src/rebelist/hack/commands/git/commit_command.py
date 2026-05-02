from rebelist.hack.infrastructure.git.agents import GitCommitComposer
from rebelist.hack.infrastructure.git.manager import GitManager


class CommitCommand:
    def __init__(self, git_commit_composer: GitCommitComposer, git_manager: GitManager) -> None:
        self.__git_commit_composer = git_commit_composer
        self.__git_manager = git_manager

    def __call__(self, description: str) -> str:
        """Create a commit on the current branch."""
        branch_name = self.__git_manager.get_current_branch()
        commit = self.__git_commit_composer.compose(description, branch_name)
        output = self.__git_manager.commit(commit)

        return output
