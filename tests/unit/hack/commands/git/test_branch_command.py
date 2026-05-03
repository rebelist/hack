from unittest.mock import create_autospec

import pytest

from rebelist.hack.commands.git.branch_command import CheckoutBranchCommand
from rebelist.hack.domain.models import Branch, Ticket
from rebelist.hack.infrastructure.git import GitBranchComposer, GitManager
from rebelist.hack.infrastructure.jira import JiraGateway


@pytest.mark.unit
class TestCheckoutBranchCommand:
    """Verify the use-case fetches the ticket, composes a Branch, assembles the name, and checks it out."""

    def test_full_flow(self) -> None:
        """The command resolves the ticket, asks the composer for a Branch, assembles the full name, and checks out."""
        gateway = create_autospec(JiraGateway, instance=True)
        ticket = Ticket(key='WS-120', summary='Fix login', kind='Bug', description='D')
        gateway.get_ticket.return_value = ticket
        composer = create_autospec(GitBranchComposer, instance=True)
        composer.compose.return_value = Branch(prefix='feature', name='fix-login')
        manager = create_autospec(GitManager, instance=True)
        manager.checkout_branch.return_value = 'Switched to a new branch feature/WS-120-fix-login'
        command = CheckoutBranchCommand(gateway, composer, manager)

        result = command('WS-120')

        gateway.get_ticket.assert_called_once_with('WS-120')
        composer.compose.assert_called_once_with(ticket)
        manager.checkout_branch.assert_called_once_with('feature/WS-120-fix-login')
        assert 'feature/WS-120-fix-login' in result

    def test_dry_run_skips_checkout(self) -> None:
        """With dry_run=True the resolved branch name is returned but checkout_branch is not called."""
        gateway = create_autospec(JiraGateway, instance=True)
        ticket = Ticket(key='WS-120', summary='Fix login', kind='Bug', description='D')
        gateway.get_ticket.return_value = ticket
        composer = create_autospec(GitBranchComposer, instance=True)
        composer.compose.return_value = Branch(prefix='feature', name='fix-login')
        manager = create_autospec(GitManager, instance=True)
        command = CheckoutBranchCommand(gateway, composer, manager)

        result = command('WS-120', dry_run=True)

        manager.checkout_branch.assert_not_called()
        assert result == 'feature/WS-120-fix-login'
