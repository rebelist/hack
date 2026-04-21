"""Shared pytest fixtures."""

from unittest.mock import create_autospec

import pytest
from typer.testing import CliRunner

from rebelist.hack.config.settings import (
    AgentSettings,
    GeneralSettings,
    JiraIssueTypeSettings,
    JiraSettings,
    JiraTicketFieldsSettings,
    JiraTicketReporterSettings,
    JiraTicketTemplateSettings,
    Settings,
)


@pytest.fixture
def runner() -> CliRunner:
    """Fixture for the Typer CLI runner."""
    return CliRunner()


@pytest.fixture
def mock_jira_settings() -> JiraSettings:
    """Build a fully-populated `JiraSettings` including one Bug template.

    The `Bug Template Content` marker is asserted on by the agent system-prompt test,
    so callers may rely on that template being present.
    """
    fields = JiraTicketFieldsSettings(
        project='HACK',
        reporter=JiraTicketReporterSettings(default='admin'),
        issue_type=JiraIssueTypeSettings(options=['Bug', 'Task']),
    )
    templates = [JiraTicketTemplateSettings(issue_type='Bug', template='Bug Template Content')]
    return JiraSettings(
        host='https://example.atlassian.net',
        token='token123',
        fields=fields,
        custom_fields={},
        templates=templates,
    )


@pytest.fixture
def mock_settings(mock_jira_settings: JiraSettings) -> Settings:
    """Build a `Settings` autospec pre-wired with realistic `general`, `agent`, and `jira` values."""
    mock = create_autospec(Settings)
    mock.general = GeneralSettings(name='hack', version='0.1.0')
    mock.agent = AgentSettings(model='openai:gpt-4', api_key_name='OPENAI_API_KEY', api_key='sk-123')
    mock.jira = mock_jira_settings
    return mock
