import pytest
from pydantic import ValidationError

from incident_copilot.config import AgentSettings


def test_run_timeout_is_read_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RUN_TIMEOUT_SECONDS", "15")

    assert AgentSettings(_env_file=None).run_timeout_seconds == 15


@pytest.mark.parametrize("value", ["0", "-5"])
def test_non_positive_run_timeout_is_rejected(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("RUN_TIMEOUT_SECONDS", value)

    with pytest.raises(ValidationError):
        AgentSettings(_env_file=None)
