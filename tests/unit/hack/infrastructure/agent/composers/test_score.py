"""Tests for the score log LLM composers.

Each composer registers its system-prompt callback via
`agent.system_prompt(callback)` during construction. We substitute `Agent`
with a `create_autospec` stand-in, then read the callback back through
`agent_instance.system_prompt.call_args.args[0]` to assert on the assembled
prompt — no private access, no pyright ignores.
"""

from collections.abc import Callable
from datetime import datetime
from typing import Any
from unittest.mock import create_autospec

import pytest
from pydantic_ai import Agent, RunContext
from pydantic_ai.run import AgentRunResult
from pytest_mock import MockerFixture

from rebelist.hack.domain.models import Score
from rebelist.hack.infrastructure.agent.composers import score as score_composers_module
from rebelist.hack.infrastructure.agent.composers.score import ScoreComposer, ScoreLogComposer


def _install_agent_mock(mocker: MockerFixture) -> Any:
    """Replace `Agent` in the agent composers module with an autospec'd class mock."""
    agent_class = create_autospec(Agent)
    mocker.patch.object(score_composers_module, 'Agent', new=agent_class)
    return agent_class


def _stub_run_output(agent_class: Any, output: str) -> None:
    """Make the agent's run_sync return an AgentRunResult exposing the given output."""
    run_result = create_autospec(AgentRunResult, instance=True)
    run_result.output = output
    agent_class.return_value.run_sync.return_value = run_result


def _captured_prompt_callback(agent_class: Any) -> Callable[[RunContext[Any]], str]:
    """Return the system_prompt callback that the composer registered with the agent."""
    callback: Callable[[RunContext[Any]], str] = agent_class.return_value.system_prompt.call_args.args[0]
    return callback


@pytest.mark.unit
class TestScoreComposer:
    """Verify the cleanup composer wiring and its system prompt."""

    def test_compose_runs_agent_and_returns_cleaned_text(self, mocker: MockerFixture) -> None:
        """compose() forwards the raw description to the agent and returns the cleaned string output."""
        agent_class = _install_agent_mock(mocker)
        _stub_run_output(agent_class, 'Fixed the flaky deployment pipeline.')
        composer = ScoreComposer('test:dummy')

        result = composer.compose('fixed the flaky deploy pipeline everyone hated')

        agent_class.assert_called_once_with('test:dummy', output_type=str)
        assert agent_class.return_value.run_sync.call_args.args[0] == 'fixed the flaky deploy pipeline everyone hated'
        assert result == 'Fixed the flaky deployment pipeline.'

    def test_system_prompt_describes_light_cleanup(self, mocker: MockerFixture) -> None:
        """The registered system prompt instructs the model to lightly clean up, not rewrite, the entry."""
        agent_class = _install_agent_mock(mocker)
        ScoreComposer('test:dummy')
        run_context = create_autospec(RunContext, instance=True)

        prompt = _captured_prompt_callback(agent_class)(run_context).lower()

        assert 'grammar' in prompt
        assert 'achievement' in prompt


@pytest.mark.unit
class TestScoreLogComposer:
    """Verify the export composer feeds entries as data and assembles a score log prompt."""

    def test_compose_passes_entries_as_data_and_returns_markdown(self, mocker: MockerFixture) -> None:
        """compose() builds a run prompt embedding every entry and returns the agent's markdown output."""
        agent_class = _install_agent_mock(mocker)
        _stub_run_output(agent_class, '# Score Log\n- entry')
        composer = ScoreLogComposer('test:dummy')
        scores = [
            Score(created_at=datetime(2026, 3, 12, 9, 30, 0), description='Stabilized the deployment pipeline.'),
            Score(created_at=datetime(2026, 5, 1, 14, 0, 0), description='Mentored two engineers.'),
        ]

        result = composer.compose(scores)

        agent_class.assert_called_once_with('test:dummy', output_type=str)
        run_prompt = agent_class.return_value.run_sync.call_args.args[0]
        assert 'Stabilized the deployment pipeline.' in run_prompt
        assert 'Mentored two engineers.' in run_prompt
        assert '2026-03-12' in run_prompt
        assert result == '# Score Log\n- entry'

    def test_compose_renders_unknown_timestamp_for_entries_without_created_at(self, mocker: MockerFixture) -> None:
        """Entries with an unset created_at are rendered with an `unknown` timestamp in the run prompt."""
        agent_class = _install_agent_mock(mocker)
        _stub_run_output(agent_class, '# Score Log')
        composer = ScoreLogComposer('test:dummy')
        scores = [Score(description='Shipped the onboarding flow.')]

        composer.compose(scores)

        run_prompt = agent_class.return_value.run_sync.call_args.args[0]
        assert run_prompt == '- [unknown] Shipped the onboarding flow.'

    def test_system_prompt_requests_chronological_categorized_score_log(self, mocker: MockerFixture) -> None:
        """The system prompt asks for a newest-first, category-tagged score log."""
        agent_class = _install_agent_mock(mocker)
        ScoreLogComposer('test:dummy')
        run_context = create_autospec(RunContext, instance=True)

        prompt = _captured_prompt_callback(agent_class)(run_context).lower()

        assert 'category' in prompt
        assert 'chronological' in prompt or 'newest' in prompt
