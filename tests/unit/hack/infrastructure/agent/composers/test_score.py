"""Tests for the score log cleanup composer.

The composer registers its system-prompt callback via
`agent.system_prompt(callback)` during construction. We substitute `Agent`
with a `create_autospec` stand-in, then read the callback back through
`agent_instance.system_prompt.call_args.args[0]` to assert on the assembled
prompt — no private access, no pyright ignores.
"""

from collections.abc import Callable
from typing import Any
from unittest.mock import create_autospec

import pytest
from pydantic_ai import Agent, RunContext
from pydantic_ai.run import AgentRunResult
from pytest_mock import MockerFixture

from rebelist.hack.domain.models import ScoreDraft
from rebelist.hack.infrastructure.agent.composers import score as score_composers_module
from rebelist.hack.infrastructure.agent.composers.score import ScoreComposer


def _install_agent_mock(mocker: MockerFixture) -> Any:
    """Replace `Agent` in the agent composers module with an autospec'd class mock."""
    agent_class = create_autospec(Agent)
    mocker.patch.object(score_composers_module, 'Agent', new=agent_class)
    return agent_class


def _stub_run_output(agent_class: Any, output: ScoreDraft) -> None:
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

    def test_compose_runs_agent_and_returns_cleaned_draft(self, mocker: MockerFixture) -> None:
        """compose() forwards the raw description to the agent and returns the cleaned, categorized draft."""
        agent_class = _install_agent_mock(mocker)
        draft = ScoreDraft(description='Fixed the flaky deployment pipeline.', category='Engineering')
        _stub_run_output(agent_class, draft)
        composer = ScoreComposer('test:dummy')

        result = composer.compose('fixed the flaky deploy pipeline everyone hated')

        agent_class.assert_called_once_with('test:dummy', output_type=ScoreDraft)
        assert agent_class.return_value.run_sync.call_args.args[0] == 'fixed the flaky deploy pipeline everyone hated'
        assert result == draft

    def test_system_prompt_describes_cleanup_and_categorization(self, mocker: MockerFixture) -> None:
        """The system prompt instructs the model to lightly clean the entry and assign a best-fit category."""
        agent_class = _install_agent_mock(mocker)
        ScoreComposer('test:dummy')
        run_context = create_autospec(RunContext, instance=True)

        prompt = _captured_prompt_callback(agent_class)(run_context).lower()

        assert 'grammar' in prompt
        assert 'achievement' in prompt
        assert 'category' in prompt
