"""Tests for the git LLM composers (branch + commit).

`Agent` is substituted at the module level with a `create_autospec` stand-in,
and the registered system-prompt callback is captured via the autospec'd
`agent.system_prompt.call_args` for prompt-assembly verification.
"""

from collections.abc import Callable
from typing import Any
from unittest.mock import create_autospec

import pytest
from pydantic_ai import Agent, RunContext
from pydantic_ai.run import AgentRunResult
from pytest_mock import MockerFixture

from rebelist.hack.config.settings import GitSettings
from rebelist.hack.domain.models import Branch, Commit, Ticket
from rebelist.hack.infrastructure.git import agents as git_agents_module
from rebelist.hack.infrastructure.git.agents import GitBranchComposer, GitCommitComposer


def _install_agent_mock(mocker: MockerFixture) -> Any:
    """Replace `Agent` in the git agents module with an autospec'd class mock."""
    agent_class = create_autospec(Agent)
    mocker.patch.object(git_agents_module, 'Agent', new=agent_class)
    return agent_class


def _captured_prompt_callback(agent_class: Any) -> Callable[[RunContext[Any]], str]:
    """Return the system_prompt callback that a composer registered with the agent."""
    agent_instance = agent_class.return_value
    callback: Callable[[RunContext[Any]], str] = agent_instance.system_prompt.call_args.args[0]
    return callback


@pytest.mark.unit
class TestGitBranchComposer:
    """Verify branch composer wiring and prompt content."""

    def test_compose_returns_the_agents_branch_output(self, mocker: MockerFixture, git_settings: GitSettings) -> None:
        """compose() returns the structured Branch produced by the agent — name assembly is the caller's job."""
        agent_class = _install_agent_mock(mocker)
        branch = Branch(prefix='feature', name='fix-memory-leak')
        _run_result = create_autospec(AgentRunResult, instance=True)
        _run_result.output = branch
        agent_class.return_value.run_sync.return_value = _run_result
        composer = GitBranchComposer('test:dummy', git_settings)
        ticket = Ticket(key='WS-120', summary='Fix memory leak', kind='Bug', description='D')

        result = composer.compose(ticket)

        assert result is branch
        agent_class.assert_called_once_with('test:dummy', output_type=Branch)
        agent_class.return_value.run_sync.assert_called_once()

    def test_system_prompt_lists_all_categories(self, mocker: MockerFixture, git_settings: GitSettings) -> None:
        """The system prompt interpolates every configured branch category in lowercase."""
        agent_class = _install_agent_mock(mocker)
        GitBranchComposer('test:dummy', git_settings)
        run_context = create_autospec(RunContext, instance=True)

        prompt = _captured_prompt_callback(agent_class)(run_context)

        for category in git_settings.branch_categories:
            assert f'`{category.lower()}`' in prompt
        assert '{categories}' not in prompt


@pytest.mark.unit
class TestGitCommitComposer:
    """Verify commit composer wiring and ticket-prefix extraction."""

    def test_compose_prepends_ticket_prefix_when_branch_has_one(self, mocker: MockerFixture) -> None:
        """A ticket prefix in the branch name is auto-prepended to the commit subject."""
        agent_class = _install_agent_mock(mocker)
        _run_result = create_autospec(AgentRunResult, instance=True)
        _run_result.output = Commit(subject='Fix login', body='')
        agent_class.return_value.run_sync.return_value = _run_result
        composer = GitCommitComposer('test:dummy')

        commit = composer.compose('fix login flow', branch_name='feature/WS-120-fix-login')

        assert commit.subject == 'WS-120 Fix login'

    def test_compose_omits_prefix_when_branch_has_none(self, mocker: MockerFixture) -> None:
        """If no ticket key matches the regex, the subject is left as-is (only stripped)."""
        agent_class = _install_agent_mock(mocker)
        _run_result = create_autospec(AgentRunResult, instance=True)
        _run_result.output = Commit(subject='Fix login', body='')
        agent_class.return_value.run_sync.return_value = _run_result
        composer = GitCommitComposer('test:dummy')

        commit = composer.compose('fix login flow', branch_name='main')

        assert commit.subject == 'Fix login'

    def test_compose_with_empty_branch_skips_prefix(self, mocker: MockerFixture) -> None:
        """An empty branch_name short-circuits prefix extraction."""
        agent_class = _install_agent_mock(mocker)
        _run_result = create_autospec(AgentRunResult, instance=True)
        _run_result.output = Commit(subject='Fix login', body='')
        agent_class.return_value.run_sync.return_value = _run_result
        composer = GitCommitComposer('test:dummy')

        commit = composer.compose('fix login flow')

        assert commit.subject == 'Fix login'

    def test_prefix_regex_handles_lowercase_branch_names(self, mocker: MockerFixture) -> None:
        """Branch names are upper-cased before the regex search, so lowercase keys still match."""
        agent_class = _install_agent_mock(mocker)
        _run_result = create_autospec(AgentRunResult, instance=True)
        _run_result.output = Commit(subject='Fix login', body='')
        agent_class.return_value.run_sync.return_value = _run_result
        composer = GitCommitComposer('test:dummy')

        commit = composer.compose('fix login flow', branch_name='feature/ws-42-fix-login')

        assert commit.subject == 'WS-42 Fix login'

    def test_compose_normalizes_html_line_breaks_in_body(self, mocker: MockerFixture) -> None:
        """HTML <br> variants returned by the LLM are converted to real newlines via normalize_body."""
        agent_class = _install_agent_mock(mocker)
        _run_result = create_autospec(AgentRunResult, instance=True)
        _run_result.output = Commit(subject='Fix login', body='line1<br>line2<br/>line3<br />line4')
        agent_class.return_value.run_sync.return_value = _run_result
        composer = GitCommitComposer('test:dummy')

        commit = composer.compose('fix login flow')

        assert commit.body == 'line1\nline2\nline3\nline4'

    def test_system_prompt_contains_commit_constraints(self, mocker: MockerFixture) -> None:
        """The system prompt encodes the subject length and body line-wrap constraints."""
        agent_class = _install_agent_mock(mocker)
        GitCommitComposer('test:dummy')
        run_context = create_autospec(RunContext, instance=True)

        prompt = _captured_prompt_callback(agent_class)(run_context)

        assert 'Max 50 chars' in prompt
        assert '72 characters' in prompt
        assert 'imperative' in prompt
