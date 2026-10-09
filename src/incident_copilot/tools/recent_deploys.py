"""get_recent_deploys: deploys of one service within a time window."""

from typing import Final

from pydantic import AwareDatetime

from incident_copilot.domain.loaders import FixtureDataset
from incident_copilot.domain.models import DeployStatus, NonEmptyStr
from incident_copilot.tools.contracts import (
    ServiceWindowInput,
    ToolError,
    ToolModel,
    ToolName,
    ToolSpec,
)

TIMEOUT_SECONDS: Final = 5.0

DESCRIPTION: Final = (
    "Returns deploys of a service between start and end, oldest first. "
    "An empty list means there were no deploys in that window."
)


class DeployRecord(ToolModel):
    # No author: a person's name does not help find a cause and should not reach the LLM.
    id: NonEmptyStr
    version: NonEmptyStr
    deployed_at: AwareDatetime
    status: DeployStatus
    change_summary: NonEmptyStr


class RecentDeploys(ToolModel):
    service: NonEmptyStr
    deploys: tuple[DeployRecord, ...]


class RecentDeploysTool:
    def __init__(self, dataset: FixtureDataset) -> None:
        self._dataset = dataset
        self._known_services = {service.name for service in dataset.services}

    def spec(self) -> ToolSpec[ServiceWindowInput, RecentDeploys]:
        """The catalog card the executor uses to call this tool."""
        return ToolSpec(
            name=ToolName.GET_RECENT_DEPLOYS,
            description=DESCRIPTION,
            input_model=ServiceWindowInput,
            output_model=RecentDeploys,
            timeout_seconds=TIMEOUT_SECONDS,
            handler=self.run,
        )

    async def run(self, args: ServiceWindowInput) -> RecentDeploys:
        if args.service not in self._known_services:
            raise ToolError(f"Unknown service '{args.service}'")

        in_window = sorted(
            (
                deploy
                for deploy in self._dataset.deploys
                if deploy.service == args.service
                and args.start <= deploy.deployed_at <= args.end
            ),
            key=lambda deploy: deploy.deployed_at,
        )
        return RecentDeploys(
            service=args.service,
            deploys=tuple(
                DeployRecord(
                    id=deploy.id,
                    version=deploy.version,
                    deployed_at=deploy.deployed_at,
                    status=deploy.status,
                    change_summary=deploy.change_summary,
                )
                for deploy in in_window
            ),
        )
