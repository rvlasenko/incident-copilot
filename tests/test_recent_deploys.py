from datetime import datetime

import pytest
from pydantic import ValidationError

from incident_copilot.domain.loaders import FixtureDataset
from incident_copilot.domain.models import DeployStatus
from incident_copilot.tools.contracts import ServiceWindowInput, ToolError, ToolName
from incident_copilot.tools.recent_deploys import RecentDeploys, RecentDeploysTool
from tests.factories import at, dataset, deploy

pytestmark = pytest.mark.anyio

# Deploys are deliberately out of time order: the tool must sort them itself.
DATASET = dataset(
    services=["checkout", "auth"],
    deploys=[
        deploy("late", "checkout", at(12, 0)),
        deploy("early", "checkout", at(10, 0)),
        deploy("before-window", "checkout", at(8, 59)),
        deploy("after-window", "checkout", at(12, 1)),
        deploy("other-service", "auth", at(11, 0)),
    ],
)


async def _deploys(service: str, start: datetime, end: datetime) -> RecentDeploys:
    tool = RecentDeploysTool(DATASET)
    return await tool.run(ServiceWindowInput(service=service, start=start, end=end))


async def test_returns_deploys_of_the_service_inside_window_oldest_first() -> None:
    result = await _deploys("checkout", at(9, 0), at(12, 0))

    assert [d.id for d in result.deploys] == ["early", "late"]


async def test_deploys_exactly_on_window_ends_are_included() -> None:
    result = await _deploys("checkout", at(10, 0), at(12, 0))

    assert [d.id for d in result.deploys] == ["early", "late"]


async def test_window_without_deploys_is_an_empty_answer_not_an_error() -> None:
    result = await _deploys("checkout", at(13, 0), at(14, 0))

    assert result.service == "checkout"
    assert result.deploys == ()


async def test_author_is_not_returned() -> None:
    result = await _deploys("checkout", at(9, 0), at(12, 0))

    assert "author" not in result.deploys[0].model_dump()


async def test_unknown_service_is_an_error() -> None:
    with pytest.raises(ToolError, match="Unknown service 'chekout'"):
        await _deploys("chekout", at(9, 0), at(12, 0))


def test_inverted_window_is_rejected() -> None:
    with pytest.raises(ValidationError, match="start must not be after end"):
        ServiceWindowInput(service="checkout", start=at(12, 0), end=at(9, 0))


def test_spec_describes_the_tool() -> None:
    spec = RecentDeploysTool(DATASET).spec()

    assert spec.name is ToolName.GET_RECENT_DEPLOYS
    assert spec.input_model is ServiceWindowInput
    assert spec.output_model is RecentDeploys


async def test_spec_handler_finds_the_inventory_regression_in_repository_fixtures(
    repo_dataset: FixtureDataset,
) -> None:
    # Called through the card, the way the executor will call it.
    spec = RecentDeploysTool(repo_dataset).spec()

    result = await spec.handler(
        ServiceWindowInput(service="inventory", start=at(10, 0), end=at(11, 30))
    )

    [found] = result.deploys
    assert found.version == "1.9.3"
    assert found.deployed_at == at(10, 58)


async def test_rolled_back_status_is_kept_in_repository_fixtures(
    repo_dataset: FixtureDataset,
) -> None:
    spec = RecentDeploysTool(repo_dataset).spec()

    result = await spec.handler(
        ServiceWindowInput(service="auth", start=at(12, 0), end=at(13, 0))
    )

    [found] = result.deploys
    assert found.status is DeployStatus.ROLLED_BACK
