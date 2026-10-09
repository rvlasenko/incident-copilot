from datetime import datetime

import pytest

from incident_copilot.domain.loaders import FixtureDataset
from incident_copilot.domain.models import LogLevel
from incident_copilot.tools.contracts import ToolError, ToolName
from incident_copilot.tools.search_logs import (
    LogSearchResult,
    SearchLogsInput,
    SearchLogsTool,
)
from tests.factories import at, dataset, log

pytestmark = pytest.mark.anyio

# Records are deliberately out of time order: the tool must sort them itself.
DATASET = dataset(
    services=["checkout", "payments"],
    logs=[
        log("checkout", at(14, 5), LogLevel.ERROR, "second error"),
        log("checkout", at(14, 0), LogLevel.WARNING, "first warning"),
        log("checkout", at(14, 2), LogLevel.INFO, "order placed"),
        log("checkout", at(14, 3), LogLevel.CRITICAL, "critical"),
        log("checkout", at(13, 59), LogLevel.ERROR, "before window"),
        log("checkout", at(14, 11), LogLevel.ERROR, "after window"),
        log("payments", at(14, 1), LogLevel.ERROR, "other service"),
    ],
)


async def _search(
    start: datetime,
    end: datetime,
    min_level: LogLevel = LogLevel.WARNING,
    service: str = "checkout",
) -> LogSearchResult:
    tool = SearchLogsTool(DATASET)
    args = SearchLogsInput(service=service, start=start, end=end, min_level=min_level)
    return await tool.run(args)


def _messages(result: LogSearchResult) -> list[str]:
    return [record.message for record in result.records]


async def test_default_level_returns_warnings_and_worse_oldest_first() -> None:
    result = await _search(at(14, 0), at(14, 10))

    assert _messages(result) == ["first warning", "critical", "second error"]


async def test_min_level_error_drops_warnings() -> None:
    result = await _search(at(14, 0), at(14, 10), min_level=LogLevel.ERROR)

    assert _messages(result) == ["critical", "second error"]


async def test_min_level_debug_returns_everything_in_window() -> None:
    result = await _search(at(14, 0), at(14, 10), min_level=LogLevel.DEBUG)

    assert "order placed" in _messages(result)
    assert len(result.records) == 4


async def test_records_exactly_on_window_ends_are_included() -> None:
    result = await _search(at(14, 0), at(14, 5))

    assert _messages(result) == ["first warning", "critical", "second error"]


async def test_window_without_records_is_an_empty_answer_not_an_error() -> None:
    result = await _search(at(15, 0), at(16, 0))

    assert result.service == "checkout"
    assert result.records == ()


async def test_unknown_service_is_an_error() -> None:
    with pytest.raises(ToolError, match="Unknown service 'chekout'"):
        await _search(at(14, 0), at(14, 10), service="chekout")


def test_min_level_defaults_to_warning() -> None:
    args = SearchLogsInput(service="checkout", start=at(14, 0), end=at(14, 10))

    assert args.min_level is LogLevel.WARNING


def test_spec_describes_the_tool() -> None:
    spec = SearchLogsTool(DATASET).spec()

    assert spec.name is ToolName.SEARCH_LOGS
    assert spec.input_model is SearchLogsInput
    assert spec.output_model is LogSearchResult


async def test_repository_fixtures_link_checkout_errors_to_payments_by_trace(
    repo_dataset: FixtureDataset,
) -> None:
    # Called through the card, the way the executor will call it.
    spec = SearchLogsTool(repo_dataset).spec()

    checkout = await spec.handler(
        SearchLogsInput(service="checkout", start=at(13, 50), end=at(14, 10))
    )
    payments = await spec.handler(
        SearchLogsInput(service="payments", start=at(13, 50), end=at(14, 10))
    )

    assert [r.level for r in checkout.records] == [LogLevel.ERROR, LogLevel.ERROR]
    shared = {r.trace_id for r in checkout.records} & {
        r.trace_id for r in payments.records
    }
    assert shared == {"t-9f2c"}
