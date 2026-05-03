from unittest.mock import create_autospec

import pytest

from rebelist.hack.commands.jira.ticket_command import CreateJiraTicketCommand
from rebelist.hack.domain.models import Ticket
from rebelist.hack.infrastructure.jira import JiraGateway, JiraTicketComposer


@pytest.mark.unit
class TestCreateJiraTicketCommand:
    """Verify the use-case orchestrates composer and gateway in the right order."""

    def test_compose_then_persist_then_return_ticket(self) -> None:
        """The command must compose a Ticket, persist it via the gateway, and return the persisted ticket."""
        composer = create_autospec(JiraTicketComposer, instance=True)
        ticket = Ticket(summary='Fix login', kind='Bug', description='D')
        persisted = ticket.model_copy(update={'key': 'WS-1'})
        composer.compose.return_value = ticket
        gateway = create_autospec(JiraGateway, instance=True)
        gateway.add_ticket.return_value = persisted
        command = CreateJiraTicketCommand(composer, gateway)

        result = command('Make login work')

        composer.compose.assert_called_once_with('Make login work')
        gateway.add_ticket.assert_called_once_with(ticket)
        assert result is persisted

    def test_dry_run_skips_gateway(self) -> None:
        """With dry_run=True the gateway is not called and the composed ticket is returned."""
        composer = create_autospec(JiraTicketComposer, instance=True)
        ticket = Ticket(summary='Fix login', kind='Bug', description='D')
        composer.compose.return_value = ticket
        gateway = create_autospec(JiraGateway, instance=True)
        command = CreateJiraTicketCommand(composer, gateway)

        result = command('Make login work', dry_run=True)

        composer.compose.assert_called_once_with('Make login work')
        gateway.add_ticket.assert_not_called()
        assert result is ticket
