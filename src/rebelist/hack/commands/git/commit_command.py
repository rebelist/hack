from rebelist.hack.infrastructure.git.agents import GitCommitComposer
from rebelist.hack.infrastructure.git.manager import GitManager


class CommitCommand:
    def __init__(self, git_commit_composer: GitCommitComposer, git_manager: GitManager) -> None:
        self.__git_commit_composer = git_commit_composer
        self.__git_manager = git_manager

    def __call__(self, description: str, dry_run: bool = False) -> str:
        """Create a commit on the current branch."""
        branch_name = self.__git_manager.get_current_branch()
        commit = self.__git_commit_composer.compose(description, branch_name)
        if dry_run:
            body = f'\n\n{commit.body}' if commit.body else ''
            return f'{commit.subject}{body}'
        return self.__git_manager.commit(commit)
