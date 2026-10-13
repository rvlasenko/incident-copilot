import pytest

from incident_copilot.domain.loaders import FixtureDataset
from incident_copilot.domain.models import DependencyStatus
from incident_copilot.tools.contracts import ToolError, ToolName
from incident_copilot.tools.dependency_status import (
    DependencyReport,
    DependencyStatusInput,
    DependencyStatusTool,
)
from tests.factories import at, dataset, dependency, service

pytestmark = pytest.mark.anyio

DATASET = dataset(
    services=[
        service("payments", depends_on=["psp-gateway", "auth", "postgres-main"]),
        "auth",
        "lonely",
        service("broken", depends_on=["ghost"]),
    ],
    dependencies=[
        dependency("psp-gateway", DependencyStatus.DEGRADED, at(13, 58)),
        dependency("postgres-main", DependencyStatus.OPERATIONAL, at(8, 0)),
    ],
)


async def _report(service_name: str) -> DependencyReport:
    tool = DependencyStatusTool(DATASET)
    return await tool.run(DependencyStatusInput(service=service_name))


async def test_splits_internal_services_from_external_dependencies() -> None:
    report = await _report("payments")

    assert report.internal_services == ("auth",)
    assert [dep.name for dep in report.external_dependencies] == [
        "psp-gateway",
        "postgres-main",
    ]


async def test_external_dependency_carries_status_and_since() -> None:
    report = await _report("payments")

    psp = report.external_dependencies[0]
    assert psp.status is DependencyStatus.DEGRADED
    assert psp.since == at(13, 58)


async def test_service_without_dependencies_is_an_empty_answer_not_an_error() -> None:
    report = await _report("lonely")

    assert report.internal_services == ()
    assert report.external_dependencies == ()


async def test_unknown_service_is_an_error() -> None:
    with pytest.raises(ToolError, match="Unknown service 'paymnts'"):
        await _report("paymnts")


async def test_undescribed_dependency_is_an_error_not_a_silent_skip() -> None:
    with pytest.raises(ToolError, match="Dependency 'ghost' of service 'broken'"):
        await _report("broken")


async def test_external_dependency_name_is_not_a_service() -> None:
    with pytest.raises(ToolError, match="Unknown service 'psp-gateway'"):
        await _report("psp-gateway")


def test_spec_describes_the_tool() -> None:
    spec = DependencyStatusTool(DATASET).spec()

    assert spec.name is ToolName.GET_DEPENDENCY_STATUS
    assert spec.input_model is DependencyStatusInput
    assert spec.output_model is DependencyReport


async def test_repository_fixtures_show_payments_depends_on_degraded_psp(
    repo_dataset: FixtureDataset,
) -> None:
    # Called through the card, the way the executor will call it.
    spec = DependencyStatusTool(repo_dataset).spec()

    payments = await spec.handler(DependencyStatusInput(service="payments"))
    checkout = await spec.handler(DependencyStatusInput(service="checkout"))

    [psp] = payments.external_dependencies
    assert psp.name == "psp-gateway"
    assert psp.status is DependencyStatus.DEGRADED
    assert payments.internal_services == ("auth",)
    assert checkout.internal_services == ("payments", "inventory", "auth")
    assert checkout.external_dependencies == ()
