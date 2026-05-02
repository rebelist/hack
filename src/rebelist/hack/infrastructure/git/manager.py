import subprocess
from typing import Final

from rebelist.hack.domain.models import Commit


class GitCommandError(Exception):
    """Raised when a git command fails."""

    def __init__(self, command: list[str], returncode: int, stderr: str, stdout: str) -> None:
        self.command = command
        self.returncode = returncode
        self.stderr = stderr
        self.stdout = stdout

        super().__init__(f'Git command failed: {" ".join(command)} (exit={returncode}) stderr={stderr.strip()}')


class GitTimeoutError(Exception):
    """Raised when a git command exceeds the allowed execution time."""

    def __init__(self, command: list[str], timeout: float) -> None:
        self.command = command
        self.timeout = timeout

        super().__init__(f'Git command timed out after {timeout}s: {" ".join(command)}')


class GitManager:
    DEFAULT_TIMEOUT_SECONDS: Final[float] = 30.0

    def __init__(self, git_binary: str = 'git', timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS) -> None:
        self._git = git_binary
        self._timeout = timeout_seconds

    def checkout_branch(self, name: str) -> str:
        """Create a branch named branch_name."""
        return self.__execute(['checkout', '-b', name], use_stderr=True)

    def get_current_branch(self) -> str:
        """Return the current branch name as a plain string."""
        return self.__execute(['branch', '--show-current'])

    def commit(self, commit: Commit) -> str:
        """Commit changes with the given message."""
        command = ['commit', '-m', commit.subject]

        if commit.body:
            command.extend(['-m', commit.body])

        return self.__execute(command)

    def __execute(self, arguments: list[str], use_stderr: bool = False) -> str:
        command = [self._git, *arguments]

        try:
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                text=True,
                encoding='utf-8',
                timeout=self._timeout,
            )
            output = (result.stderr if use_stderr else result.stdout).strip()
            return output

        except subprocess.TimeoutExpired as e:
            raise GitTimeoutError(command, e.timeout) from e
        except subprocess.CalledProcessError as e:
            raise GitCommandError(command, e.returncode, e.stderr or '', e.stdout or '') from e
