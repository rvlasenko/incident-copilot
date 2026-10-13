"""get_dependency_status: what a service depends on, and how its external dependencies are doing."""

from typing import Final

from pydantic import AwareDatetime

from incident_copilot.domain.loaders import FixtureDataset
from incident_copilot.domain.models import DependencyStatus, NonEmptyStr
from incident_copilot.tools.checks import require_known_service
from incident_copilot.tools.contracts import ToolError, ToolModel, ToolName, ToolSpec

TIMEOUT_SECONDS: Final = 5.0

DESCRIPTION: Final = (
    "Returns what a service depends on. Internal services are listed by name only; "
    "check them with get_service_health. External dependencies come with their "
    "current status and the time it has held since; there is no status history."
)


class DependencyStatusInput(ToolModel):
    service: NonEmptyStr


class ExternalDependency(ToolModel):
    name: NonEmptyStr
    status: DependencyStatus
    since: AwareDatetime
    description: NonEmptyStr


class DependencyReport(ToolModel):
    service: NonEmptyStr
    # Two lists instead of one record type with optional status: an internal
    # service has no status here, and this shape makes that impossible to fake.
    internal_services: tuple[NonEmptyStr, ...]
    external_dependencies: tuple[ExternalDependency, ...]


class DependencyStatusTool:
    def __init__(self, dataset: FixtureDataset) -> None:
        self._dataset = dataset

    def spec(self) -> ToolSpec[DependencyStatusInput, DependencyReport]:
        return ToolSpec(
            name=ToolName.GET_DEPENDENCY_STATUS,
            description=DESCRIPTION,
            input_model=DependencyStatusInput,
            output_model=DependencyReport,
            timeout_seconds=TIMEOUT_SECONDS,
            handler=self.run,
        )

    async def run(self, args: DependencyStatusInput) -> DependencyReport:
        require_known_service(self._dataset, args.service)

        services = {service.name: service for service in self._dataset.services}
        externals = {dep.name: dep for dep in self._dataset.dependencies}

        internal: list[str] = []
        external: list[ExternalDependency] = []
        for name in services[args.service].depends_on:
            if name in services:
                internal.append(name)
            elif (found := externals.get(name)) is not None:
                external.append(
                    ExternalDependency(
                        name=found.name,
                        status=found.status,
                        since=found.since,
                        description=found.description,
                    )
                )
            else:
                # load_dataset rejects such references; only a hand-built dataset gets here.
                raise ToolError(
                    f"Dependency '{name}' of service '{args.service}' is not described"
                )

        return DependencyReport(
            service=args.service,
            internal_services=tuple(internal),
            external_dependencies=tuple(external),
        )
