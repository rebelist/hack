import re
from re import Pattern
from textwrap import dedent
from typing import Final

from pydantic_ai import Agent, RunContext

from rebelist.hack.config.settings import GitSettings
from rebelist.hack.domain.models import Branch, Commit, Ticket


class GitBranchComposer:
    _SYSTEM_PROMPT: Final[str] = dedent("""
        ## Role
        You are a specialized Git workflow automation tool. Your goal is to generate a concise, kebab-case branch
        description based on ticket metadata.

        ## Task
        1. From the allowed list of **Categories** ({categories}), select the one that best fits the ticket.
        2. Assign this selection to the `prefix` field.
        3. Generate a kebab-case `name` based on the technical summary.

        ## Constraints
        - **Format:** Use kebab-case (english letters, numbers, and hyphens only).
        - **Linguistic Logic:**
            - Extract the core technical verb and noun (e.g., "fix-memory-leak").
            - Remove all stop words ("a", "the", "in", "with", "for").
            - Keep it purely technical and concise.
        - **Length:** The `name` field must not exceed 60 characters.

        ## Example
        Input Summary: "Fixing the memory leak in the PHP worker process"
        Output Name: "fix-php-worker-memory-leak"

        ## Output
        Populate the `Branch` schema. Do not provide any preamble or explanation.
    """).strip()

    def __init__(self, model: str, git_settings: GitSettings) -> None:
        self.__git_settings = git_settings
        self.__agent = Agent(model, output_type=Branch)
        self.__agent.system_prompt(self.__build_system_prompt)

    def compose(self, ticket: Ticket) -> Branch:
        """Create a git branch name from a ticket."""
        prompt = f"""
        - Ticket Kind: {ticket.kind}
        - Summary: {ticket.summary}
        """
        result = self.__agent.run_sync(prompt)

        return result.output

    def __build_system_prompt(self, _: RunContext) -> str:
        categories = ','.join(f'`{item.strip().lower()}`' for item in self.__git_settings.branch_categories)
        return self._SYSTEM_PROMPT.format(categories=categories)


class GitCommitComposer:
    PREFIX_REGEX: Final[Pattern[str]] = re.compile(r'\b([A-Z][A-Z0-9]{1,9}-\d+)\b')

    _SYSTEM_PROMPT: Final[str] = dedent("""
        ## Role
        You are a Senior Engineer. Your task is to transform raw commit descriptions into professional Git messages.

        ## Logic & Constraints
        1. **Subject Field (Max 50 chars):**
           - Use the imperative mood (e.g., "Add," "Fix," "Refactor").
           - Capitalize the first letter; no trailing period.
           - Do not use type prefixes (e.g., no "feat:").
        2. **Body Field (Max 1000 chars):**
           - Explain the "why" and "what."
           - **Crucial:** Insert actual newline characters (`\\n`) — never HTML tags like `<br>` — so that no single
             line exceeds 72 characters. Count characters and break the line before reaching the limit.
           - If the change is trivial, return an empty string for the body.
        3. **Tone:**
           - Technical, neutral, and direct.
           - No conversational filler or preamble.
    """).strip()

    def __init__(self, model: str) -> None:
        self.__agent = Agent(model, output_type=Commit)
        self.__agent.system_prompt(self.__build_system_prompt)

    def compose(self, description: str, branch_name: str = '') -> Commit:
        """Create a git commit message."""
        result = self.__agent.run_sync(description)
        commit = result.output
        prefix = self.__extract_message_prefix(branch_name)
        subject = f'{prefix} {commit.subject}'.strip()
        body = GitCommitComposer.__normalize_body(commit.body)
        return commit.model_copy(update={'subject': subject, 'body': body})

    @staticmethod
    def __normalize_body(body: str) -> str:
        """Replace HTML line break variants with real newlines, LLMs occasionally emit these despite instructions."""
        return body.replace('<br>', '\n').replace('<br/>', '\n').replace('<br />', '\n')

    def __extract_message_prefix(self, branch_name: str) -> str:
        if not branch_name:
            return ''

        normalized = branch_name.upper()
        match = GitCommitComposer.PREFIX_REGEX.search(normalized)
        return match.group(1) if match else ''

    def __build_system_prompt(self, _: RunContext) -> str:
        return self._SYSTEM_PROMPT
