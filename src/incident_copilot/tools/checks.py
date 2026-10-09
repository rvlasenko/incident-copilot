"""Argument checks that need the data source, so input models cannot do them."""

from incident_copilot.domain.loaders import FixtureDataset
from incident_copilot.tools.contracts import ToolError


def require_known_service(dataset: FixtureDataset, service: str) -> None:
    if all(known.name != service for known in dataset.services):
        raise ToolError(f"Unknown service '{service}'")
