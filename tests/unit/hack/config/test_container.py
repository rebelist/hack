"""Tests for the lazy DI Container.

External constructors that the Container reaches for (`JIRA`, `Agent`) are
substituted at the module level with `create_autospec`-backed replacements so
no network or LLM call is made and so every mock validates the production
class signature.
"""

from unittest.mock import create_autospec

import pytest
from jira import JIRA
from pydantic_ai import Agent
from pytest_mock import MockerFixture

from rebelist.hack.commands.git import CheckoutBranchCommand, CommitCommand
from rebelist.hack.commands.jira import CreateJiraTicketCommand
from rebelist.hack.commands.score import (
    DeleteAllScoresCommand,
    DeleteScoreCommand,
    ExportScoreLogCommand,
    ListScoresCommand,
    SaveScoreCommand,
)
from rebelist.hack.config import container as container_module
from rebelist.hack.config.container import Container
from rebelist.hack.config.settings import Settings
from rebelist.hack.infrastructure.git import GitManager
from rebelist.hack.infrastructure.git import agents as git_agents_module
from rebelist.hack.infrastructure.jira import JiraGateway
from rebelist.hack.infrastructure.jira import agents as jira_agents_module
from rebelist.hack.infrastructure.sqlite import ScoreRepository
from rebelist.hack.infrastructure.sqlite import agents as sqlite_agents_module


@pytest.fixture(autouse=True)
def stub_external_constructors(mocker: MockerFixture) -> None:
    """Replace heavy / network-touching constructors with autospec'd stand-ins."""
    mocker.patch.object(container_module, 'JIRA', new=create_autospec(JIRA))
    mocker.patch.object(jira_agents_module, 'Agent', new=create_autospec(Agent))
    mocker.patch.object(git_agents_module, 'Agent', new=create_autospec(Agent))
    mocker.patch.object(sqlite_agents_module, 'Agent', new=create_autospec(Agent))


@pytest.mark.unit
class TestContainer:
    """Verify the lazy DI graph wires the right concrete classes and caches them."""

    def test_resolves_jira_gateway_with_mapped_settings(self, settings: Settings) -> None:
        """jira_gateway is built lazily and exposes a JiraGateway instance."""
        container = Container(settings)

        gateway = container.jira_gateway

        assert isinstance(gateway, JiraGateway)

    def test_resolves_create_ticket_command(self, settings: Settings) -> None:
        """create_ticket_command resolves to a CreateJiraTicketCommand."""
        container = Container(settings)

        command = container.create_ticket_command

        assert isinstance(command, CreateJiraTicketCommand)

    def test_resolves_git_checkout_branch_command(self, settings: Settings) -> None:
        """git_checkout_branch_command resolves to a CheckoutBranchCommand."""
        container = Container(settings)

        command = container.git_checkout_branch_command

        assert isinstance(command, CheckoutBranchCommand)

    def test_resolves_git_commit_command(self, settings: Settings) -> None:
        """git_commit_command resolves to a CommitCommand."""
        container = Container(settings)

        command = container.git_commit_command

        assert isinstance(command, CommitCommand)

    def test_resolves_git_manager(self, settings: Settings) -> None:
        """git_manager resolves to a GitManager."""
        container = Container(settings)

        manager = container.git_manager

        assert isinstance(manager, GitManager)

    def test_resolves_score_repository(self, settings: Settings) -> None:
        """score_repository resolves to a ScoreRepository backed by a file next to the config."""
        container = Container(settings)

        repository = container.score_repository

        assert isinstance(repository, ScoreRepository)

    def test_resolves_score_save_command(self, settings: Settings) -> None:
        """score_save_command resolves to a SaveScoreCommand."""
        container = Container(settings)

        command = container.score_save_command

        assert isinstance(command, SaveScoreCommand)

    def test_resolves_score_export_command(self, settings: Settings) -> None:
        """score_export_command resolves to an ExportScoreLogCommand."""
        container = Container(settings)

        command = container.score_export_command

        assert isinstance(command, ExportScoreLogCommand)

    def test_resolves_score_list_command(self, settings: Settings) -> None:
        """score_list_command resolves to a ListScoresCommand."""
        container = Container(settings)

        command = container.score_list_command

        assert isinstance(command, ListScoresCommand)

    def test_resolves_score_delete_command(self, settings: Settings) -> None:
        """score_delete_command resolves to a DeleteScoreCommand."""
        container = Container(settings)

        command = container.score_delete_command

        assert isinstance(command, DeleteScoreCommand)

    def test_resolves_score_delete_all_command(self, settings: Settings) -> None:
        """score_delete_all_command resolves to a DeleteAllScoresCommand."""
        container = Container(settings)

        command = container.score_delete_all_command

        assert isinstance(command, DeleteAllScoresCommand)

    def test_each_resolution_is_singleton_per_container(self, settings: Settings) -> None:
        """cached_property guarantees a single instance per Container per key."""
        container = Container(settings)

        assert container.jira_gateway is container.jira_gateway
        assert container.git_manager is container.git_manager
        assert container.create_ticket_command is container.create_ticket_command
        assert container.score_repository is container.score_repository

    def test_settings_is_exposed_as_attribute(self, settings: Settings) -> None:
        """Commands read configuration values off container.settings, so it must be reachable."""
        container = Container(settings)

        assert container.settings is settings
