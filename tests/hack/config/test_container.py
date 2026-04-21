from typing import Any
from unittest.mock import create_autospec

import pytest
from pytest import MonkeyPatch

from rebelist.hack.commands.jira.services import TicketFactory
from rebelist.hack.config.container import Container
from rebelist.hack.config.settings import Settings
from rebelist.hack.connectors import JiraGateway
from rebelist.hack.connectors.agents import JiraTicketAgent


class TestContainer:
    def test_jira_gateway_lazy_initialization(self, mock_settings: Settings) -> None:
        """Verify that JiraGateway is initialized lazily and cached."""
        container = Container(mock_settings)

        # We need to mock JIRA and JiraGateway to avoid real connections
        with MonkeyPatch.context() as mp:
            mock_jira_client = create_autospec(lambda *args, **kwargs: None)
            mock_gateway_class = create_autospec(JiraGateway)

            mp.setattr('rebelist.hack.config.container.JIRA', mock_jira_client)

            def mock_gateway_factory(_: Any) -> JiraGateway:
                return mock_gateway_class

            mp.setattr('rebelist.hack.config.container.JiraGateway', mock_gateway_factory)

            gateway1 = container.jira_gateway
            gateway2 = container.jira_gateway

            assert gateway1 is gateway2
            assert gateway1 is mock_gateway_class

    def test_jira_gateway_missing_config(self, mock_settings: Settings) -> None:
        """Verify that ValueError is raised if Jira host or token is missing."""
        # Using a fresh Settings object to modify it
        from rebelist.hack.config.settings import JiraSettings

        # Test missing host
        bad_settings = create_autospec(Settings)
        bad_settings.jira = create_autospec(JiraSettings)
        bad_settings.jira.host = ''
        bad_settings.jira.token = 'token'

        container = Container(bad_settings)
        with pytest.raises(ValueError, match='Jira host is not configured.'):
            _ = container.jira_gateway

        # Test missing token
        bad_settings.jira.host = 'host'
        bad_settings.jira.token = ' '
        with pytest.raises(ValueError, match='Jira token is not configured.'):
            _ = container.jira_gateway

    def test_ticket_factory_lazy_initialization(self, mock_settings: Settings) -> None:
        """Verify that TicketFactory is initialized lazily and cached."""
        container = Container(mock_settings)

        factory1 = container.ticket_factory
        factory2 = container.ticket_factory

        assert factory1 is factory2
        assert isinstance(factory1, TicketFactory)

    def test_create_ticket_command_lazy_initialization(self, mock_settings: Settings) -> None:
        """Verify that CreateJiraTicketCommand is initialized lazily and cached."""
        container = Container(mock_settings)

        with MonkeyPatch.context() as mp:
            mp.setattr('rebelist.hack.config.container.JIRA', create_autospec(lambda *args, **kwargs: None))

            def mock_gateway_factory(_: Any) -> JiraGateway:
                return create_autospec(JiraGateway)

            mp.setattr('rebelist.hack.config.container.JiraGateway', mock_gateway_factory)
            mp.setattr('rebelist.hack.config.container.JiraTicketAgent', create_autospec(JiraTicketAgent))

            cmd1 = container.create_ticket_command
            cmd2 = container.create_ticket_command

            assert cmd1 is cmd2
