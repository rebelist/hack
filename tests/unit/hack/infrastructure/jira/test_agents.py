"""Tests for the Jira ticket LLM composer.

The composer registers its system-prompt callback by calling
`agent.system_prompt(callback)` during construction. We substitute `Agent`
with a `create_autospec` stand-in, then read back the callback via
`agent_instance.system_prompt.call_args.args[0]` to test prompt assembly —
no name-mangled private access, no pyright ignores.
"""

from collections.abc import Callable
from typing import Any
from unittest.mock import create_autospec

import pytest
from pydantic_ai import Agent, RunContext
from pydantic_ai.run import AgentRunResult
from pytest_mock import MockerFixture

from rebelist.hack.config.settings import (
    JiraIssueDescriptionTemplateSettings,
    JiraIssueFieldsSettings,
    JiraSettings,
)
from rebelist.hack.domain.models import Ticket
from rebelist.hack.infrastructure.jira import agents as jira_agents_module
from rebelist.hack.infrastructure.jira.agents import JiraTicketComposer


def _install_agent_mock(mocker: MockerFixture) -> Any:
    """Replace `Agent` in the jira agents module with an autospec'd class mock."""
    agent_class = create_autospec(Agent)
    mocker.patch.object(jira_agents_module, 'Agent', new=agent_class)
    return agent_class


def _captured_prompt_callback(agent_class: Any) -> Callable[[RunContext[Any]], str]:
    """Return the system_prompt callback that the composer registered with the agent."""
    agent_instance = agent_class.return_value
    callback: Callable[[RunContext[Any]], str] = agent_instance.system_prompt.call_args.args[0]
    return callback


@pytest.mark.unit
class TestJiraTicketComposer:
    """Verify composer wiring and the assembled system prompt."""

    def test_compose_runs_agent_and_returns_output(self, mocker: MockerFixture, jira_settings: JiraSettings) -> None:
        """compose() delegates to the Pydantic-AI agent and returns its structured output."""
        agent_class = _install_agent_mock(mocker)
        ticket = Ticket(summary='S', kind='Bug', description='D')
        _run_result = create_autospec(AgentRunResult, instance=True)
        _run_result.output = ticket
        agent_class.return_value.run_sync.return_value = _run_result
        composer = JiraTicketComposer('test:dummy', jira_settings)

        result = composer.compose('Make login work')

        agent_class.assert_called_once_with('test:dummy', output_type=Ticket)
        agent_class.return_value.run_sync.assert_called_once_with('Make login work')
        assert result is ticket

    def test_system_prompt_lists_all_issue_types_and_templates(
        self, mocker: MockerFixture, jira_settings: JiraSettings
    ) -> None:
        """The registered system-prompt callback emits the configured issue types and templates."""
        agent_class = _install_agent_mock(mocker)
        JiraTicketComposer('test:dummy', jira_settings)
        run_context = create_autospec(RunContext, instance=True)

        prompt = _captured_prompt_callback(agent_class)(run_context)

        for issue_type in jira_settings.fields.issue_types:
            assert issue_type in prompt
        for template in jira_settings.templates:
            assert template.template.strip() in prompt

    def test_system_prompt_survives_curly_braces_in_templates(self, mocker: MockerFixture) -> None:
        """Regression: templates containing { or } must not blow up prompt assembly."""
        settings = JiraSettings(
            host='https://jira.example.com',
            token='tok',  # type: ignore[arg-type]
            fields=JiraIssueFieldsSettings(project='X', reporter='alice', issue_types=['Bug']),
            templates=[
                JiraIssueDescriptionTemplateSettings(
                    issue_type='Bug', template='h2. Vars: {placeholder} and {{escaped}}'
                )
            ],
        )
        agent_class = _install_agent_mock(mocker)
        JiraTicketComposer('test:dummy', settings)
        run_context = create_autospec(RunContext, instance=True)

        prompt = _captured_prompt_callback(agent_class)(run_context)

        assert '{placeholder}' in prompt
        assert '{{escaped}}' in prompt
