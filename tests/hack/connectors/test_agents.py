from typing import Any
from unittest.mock import create_autospec

import pytest
from pydantic_ai import Agent, RunContext

from rebelist.hack.config.settings import (
    JiraIssueTypeSettings,
    JiraSettings,
    JiraTicketFieldsSettings,
    JiraTicketReporterSettings,
    JiraTicketTemplateSettings,
)
from rebelist.hack.connectors.agents import JiraTicketAgent
from rebelist.hack.models.jira import DraftTicket


class TestJiraTicketAgent:
    def test_agent_initialization(self, mock_jira_settings: JiraSettings) -> None:
        """Verify that JiraTicketAgent initializes the underlying Agent correctly."""
        with pytest.MonkeyPatch.context() as mp:
            mock_agent_class = create_autospec(Agent)
            mp.setattr('rebelist.hack.connectors.agents.Agent', mock_agent_class)

            _ = JiraTicketAgent('openai:gpt-4', mock_jira_settings)

            mock_agent_class.assert_called_once_with('openai:gpt-4', output_type=DraftTicket)

    def test_run_calls_agent_run_sync(self, mock_jira_settings: JiraSettings) -> None:
        """Verify that run method delegates to the underlying Agent's run_sync."""
        with pytest.MonkeyPatch.context() as mp:
            mock_agent_instance = create_autospec(Agent)

            def mock_agent_factory(*_args: Any, **_kwargs: Any) -> Agent:
                return mock_agent_instance

            mp.setattr('rebelist.hack.connectors.agents.Agent', mock_agent_factory)

            agent_wrapper = JiraTicketAgent('openai:gpt-4', mock_jira_settings)

            mock_result = create_autospec(lambda: None)
            mock_result.output = DraftTicket(summary='S', issue_type='Task', description='D')
            mock_agent_instance.run_sync.return_value = mock_result

            result = agent_wrapper.run('test prompt')

            assert result == mock_result.output
            mock_agent_instance.run_sync.assert_called_once_with('test prompt')

    def test_system_prompt_generation(self, mock_jira_settings: JiraSettings) -> None:
        """Verify that the system prompt contains expected information from settings."""
        agent_wrapper = JiraTicketAgent('openai:gpt-4', mock_jira_settings)

        # Access the private method to test it directly
        prompt = agent_wrapper._JiraTicketAgent__build_system_prompt(create_autospec(RunContext))  # type: ignore

        assert 'Bug, Task' in prompt
        assert 'Bug Template Content' in prompt


@pytest.fixture
def mock_jira_settings() -> JiraSettings:
    """Fixture for mocked JiraSettings."""
    fields = JiraTicketFieldsSettings(
        project='HACK',
        reporter=JiraTicketReporterSettings(default='admin'),
        issue_type=JiraIssueTypeSettings(options=['Bug', 'Task']),
    )
    templates = [JiraTicketTemplateSettings(issue_type='Bug', template='Bug Template Content')]
    return JiraSettings(host='https://jira.com', token='token', fields=fields, custom_fields={}, templates=templates)
