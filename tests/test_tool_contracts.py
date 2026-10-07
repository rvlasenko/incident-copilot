from uuid import uuid4

import pytest
from pydantic import ValidationError

from incident_copilot.tools.contracts import (
    ToolCall,
    ToolName,
    ToolResult,
    ToolStatus,
)

FAILED_STATUSES = [ToolStatus.ERROR, ToolStatus.TIMEOUT]


def test_tool_call_rejects_unknown_tool_name() -> None:
    with pytest.raises(ValidationError):
        ToolCall.model_validate(
            {"call_id": str(uuid4()), "tool": "drop_database", "arguments": {}}
        )


def test_ok_result_carries_data() -> None:
    result = ToolResult(
        call_id=uuid4(),
        tool=ToolName.GET_SERVICE_HEALTH,
        status=ToolStatus.OK,
        data={"error_rate": 0.42},
    )

    assert result.data == {"error_rate": 0.42}
    assert result.error is None


def test_ok_result_without_data_is_rejected() -> None:
    with pytest.raises(ValidationError, match="must carry data"):
        ToolResult(
            call_id=uuid4(), tool=ToolName.GET_SERVICE_HEALTH, status=ToolStatus.OK
        )


def test_ok_result_with_error_is_rejected() -> None:
    with pytest.raises(ValidationError, match="must carry data"):
        ToolResult(
            call_id=uuid4(),
            tool=ToolName.GET_SERVICE_HEALTH,
            status=ToolStatus.OK,
            data={},
            error="boom",
        )


@pytest.mark.parametrize("status", FAILED_STATUSES)
def test_failed_result_carries_error(status: ToolStatus) -> None:
    result = ToolResult(
        call_id=uuid4(),
        tool=ToolName.GET_SERVICE_HEALTH,
        status=status,
        error="unknown service",
    )

    assert result.data is None


@pytest.mark.parametrize("status", FAILED_STATUSES)
def test_failed_result_without_error_is_rejected(status: ToolStatus) -> None:
    with pytest.raises(ValidationError, match="must carry an error"):
        ToolResult(call_id=uuid4(), tool=ToolName.GET_SERVICE_HEALTH, status=status)


@pytest.mark.parametrize("status", FAILED_STATUSES)
def test_failed_result_with_data_is_rejected(status: ToolStatus) -> None:
    with pytest.raises(ValidationError, match="must carry an error"):
        ToolResult(
            call_id=uuid4(),
            tool=ToolName.GET_SERVICE_HEALTH,
            status=status,
            data={"error_rate": 0.42},
            error="unknown service",
        )
