from typing import Any
from unittest.mock import create_autospec

import pytest
from typer.testing import CliRunner

from rebelist.hack.config.container import Container
from rebelist.hack.config.settings import Settings
from rebelist.hack.console import app


class TestConsole:
    def test_bootstrap_version(self, runner: CliRunner, mock_settings: Settings) -> None:
        """Verify that the --version flag prints the application name and version."""
        mock_container = create_autospec(Container)
        mock_container.settings = mock_settings

        # We need to mock Settings.instance() because bootstrap calls it
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr('rebelist.hack.console.Settings.instance', lambda: mock_settings)

            def mock_container_factory(_settings: Any) -> Container:
                return mock_container

            mp.setattr('rebelist.hack.console.Container', mock_container_factory)

            result = runner.invoke(app, ['--version'])

            assert result.exit_code == 0
            assert 'Hack' in result.stdout
            assert 'v0.1.0' in result.stdout

    def test_jira_ticket_command(self, runner: CliRunner, mock_settings: Settings) -> None:
        """Verify that the jira ticket command calls the container's create_ticket_command."""
        mock_container = create_autospec(Container)
        mock_container.settings = mock_settings
        mock_container.create_ticket_command.return_value = 'HACK-123'

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr('rebelist.hack.console.Settings.instance', lambda: mock_settings)

            def mock_container_factory(_settings: Any) -> Container:
                return mock_container

            mp.setattr('rebelist.hack.console.Container', mock_container_factory)

            result = runner.invoke(app, ['jira', 'ticket', 'Test description'])

            assert result.exit_code == 0
            mock_container.create_ticket_command.assert_called_once_with('Test description')

    def test_main(self) -> None:
        """Verify that main calls the app."""
        with pytest.MonkeyPatch.context() as mp:
            from rebelist.hack import console

            mock_app = create_autospec(console.app)
            mp.setattr('rebelist.hack.console.app', mock_app)
            console.main()
            mock_app.assert_called_once()


@pytest.fixture
def runner() -> CliRunner:
    """Fixture for Typer CliRunner."""
    return CliRunner()


@pytest.fixture
def mock_settings() -> Settings:
    """Fixture for mocked Settings."""
    from rebelist.hack.config.settings import (
        AgentSettings,
        GeneralSettings,
        JiraIssueTypeSettings,
        JiraSettings,
        JiraTicketFieldsSettings,
        JiraTicketReporterSettings,
    )

    general = GeneralSettings(name='hack', version='0.1.0')
    agent = AgentSettings(model='openai:gpt-4', api_key_name='OPENAI_API_KEY', api_key='sk-123')
    jira_fields = JiraTicketFieldsSettings(
        project='HACK',
        reporter=JiraTicketReporterSettings(default='admin'),
        issue_type=JiraIssueTypeSettings(options=['Bug', 'Task']),
    )
    jira = JiraSettings(
        host='https://example.atlassian.net', token='token123', fields=jira_fields, custom_fields={}, templates=[]
    )

    mock = create_autospec(Settings)
    mock.general = general
    mock.agent = agent
    mock.jira = jira
    return mock
