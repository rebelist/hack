from typing import Any
from unittest.mock import MagicMock, create_autospec

import pytest
from typer.testing import CliRunner

from rebelist.hack.config.container import Container
from rebelist.hack.config.settings import Settings
from rebelist.hack.console import app

# Shared fixtures (`runner`, `mock_settings`) are defined in `tests/conftest.py`.


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
        # `create_ticket_command` is a cached_property that resolves to a callable command;
        # autospec can't infer that, so we stub it with an explicit callable mock.
        mock_command = MagicMock(return_value='HACK-123')
        mock_container.create_ticket_command = mock_command

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
