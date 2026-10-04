from uuid import uuid4

import pytest
from pydantic import ValidationError

from incident_copilot.agent.state import AgentState, RunOutcome


def test_outcome_without_answer_is_rejected() -> None:
    with pytest.raises(ValidationError, match="outcome and answer"):
        AgentState(run_id=uuid4(), query="q", outcome=RunOutcome.COMPLETED)


def test_answer_without_outcome_is_rejected() -> None:
    with pytest.raises(ValidationError, match="outcome and answer"):
        AgentState(run_id=uuid4(), query="q", answer="some answer")
