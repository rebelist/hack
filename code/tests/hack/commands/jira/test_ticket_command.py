from unittest.mock import create_autospec

from rebelist.hack.commands.jira.services import TicketFactory
from rebelist.hack.commands.jira.ticket_command import CreateJiraTicketCommand
from rebelist.hack.connectors import JiraGateway
from rebelist.hack.connectors.agents import JiraTicketAgent
from rebelist.hack.models.jira import DraftTicket, Ticket


class TestCreateJiraTicketCommand:
    def test_call_executes_workflow(self) -> None:
        """Verify that __call__ orchestrates agent, factory, and gateway correctly."""
        mock_factory = create_autospec(TicketFactory)
        mock_agent = create_autospec(JiraTicketAgent)
        mock_gateway = create_autospec(JiraGateway)

        command = CreateJiraTicketCommand(mock_factory, mock_agent, mock_gateway)

        description = 'Test description'
        draft = create_autospec(DraftTicket)
        ticket = create_autospec(Ticket)

        mock_agent.run.return_value = draft
        mock_factory.create.return_value = ticket
        mock_gateway.add_ticket.return_value = 'HACK-456'

        result = command(description)

        assert result == 'HACK-456'
        mock_agent.run.assert_called_once_with(description)
        mock_factory.create.assert_called_once_with(draft)
        mock_gateway.add_ticket.assert_called_once_with(ticket)
