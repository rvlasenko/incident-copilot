from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from incident_copilot.domain.loaders import FixtureDataset, load_dataset
from incident_copilot.domain.models import Deploy, DeployStatus, Service
from incident_copilot.tools.contracts import ServiceWindowInput, ToolError, ToolName
from incident_copilot.tools.recent_deploys import (
    RecentDeploys,
    RecentDeploysTool,
)

pytestmark = pytest.mark.anyio

REPO_FIXTURES_DIR = Path(__file__).resolve().parents[1] / "data" / "fixtures"


def _at(hour: int, minute: int) -> datetime:
    return datetime(2026, 9, 22, hour, minute, tzinfo=UTC)


def _service(name: str) -> Service:
    return Service(name=name, owner_team="team", description=name, depends_on=())


def _deploy(
    deploy_id: str,
    service: str,
    hour: int,
    minute: int,
    status: DeployStatus = DeployStatus.SUCCEEDED,
) -> Deploy:
    return Deploy(
        id=deploy_id,
        service=service,
        version="1.0.0",
        deployed_at=_at(hour, minute),
        author="alice",
        status=status,
        change_summary=f"change {deploy_id}",
    )


# Deploys are deliberately out of time order: the tool must sort them itself.
DATASET = FixtureDataset(
    services=(_service("checkout"), _service("auth")),
    dependencies=(),
    deploys=(
        _deploy("late", "checkout", 12, 0),
        _deploy("early", "checkout", 10, 0),
        _deploy("before-window", "checkout", 8, 59),
        _deploy("after-window", "checkout", 12, 1),
        _deploy("other-service", "auth", 11, 0),
    ),
    metrics=(),
    logs=(),
)


async def _deploys(service: str, start: datetime, end: datetime) -> RecentDeploys:
    tool = RecentDeploysTool(DATASET)
    return await tool.run(ServiceWindowInput(service=service, start=start, end=end))


async def test_returns_deploys_of_the_service_inside_window_oldest_first() -> None:
    result = await _deploys("checkout", _at(9, 0), _at(12, 0))

    assert [deploy.id for deploy in result.deploys] == ["early", "late"]


async def test_deploys_exactly_on_window_ends_are_included() -> None:
    result = await _deploys("checkout", _at(10, 0), _at(12, 0))

    assert [deploy.id for deploy in result.deploys] == ["early", "late"]


async def test_window_without_deploys_is_an_empty_answer_not_an_error() -> None:
    result = await _deploys("checkout", _at(13, 0), _at(14, 0))

    assert result.service == "checkout"
    assert result.deploys == ()


async def test_author_is_not_returned() -> None:
    result = await _deploys("checkout", _at(9, 0), _at(12, 0))

    assert "author" not in result.deploys[0].model_dump()


async def test_unknown_service_is_an_error() -> None:
    with pytest.raises(ToolError, match="Unknown service 'chekout'"):
        await _deploys("chekout", _at(9, 0), _at(12, 0))


def test_inverted_window_is_rejected() -> None:
    with pytest.raises(ValidationError, match="start must not be after end"):
        ServiceWindowInput(service="checkout", start=_at(12, 0), end=_at(9, 0))


def test_spec_describes_the_tool() -> None:
    spec = RecentDeploysTool(DATASET).spec()

    assert spec.name is ToolName.GET_RECENT_DEPLOYS
    assert spec.input_model is ServiceWindowInput
    assert spec.output_model is RecentDeploys


async def test_spec_handler_finds_the_inventory_regression_in_repository_fixtures() -> (
    None
):
    # Called through the card, the way the executor will call it.
    spec = RecentDeploysTool(load_dataset(REPO_FIXTURES_DIR)).spec()

    result = await spec.handler(
        ServiceWindowInput(service="inventory", start=_at(10, 0), end=_at(11, 30))
    )

    [deploy] = result.deploys
    assert deploy.version == "1.9.3"
    assert deploy.deployed_at == _at(10, 58)


async def test_rolled_back_status_is_kept_in_repository_fixtures() -> None:
    spec = RecentDeploysTool(load_dataset(REPO_FIXTURES_DIR)).spec()

    result = await spec.handler(
        ServiceWindowInput(service="auth", start=_at(12, 0), end=_at(13, 0))
    )

    [deploy] = result.deploys
    assert deploy.status is DeployStatus.ROLLED_BACK
