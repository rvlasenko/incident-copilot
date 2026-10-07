"""Manual playground: call get_service_health on the repository fixtures."""

import asyncio
from datetime import UTC, datetime
from pathlib import Path

from incident_copilot.domain.loaders import load_dataset
from incident_copilot.tools.service_health import (
    ServiceHealthInput,
    ServiceHealthTool,
)


async def main() -> None:
    dataset = load_dataset(Path("data/fixtures"))
    tool = ServiceHealthTool(dataset)

    args = ServiceHealthInput(
        service="inventory", at=datetime(2026, 9, 22, 14, 5, tzinfo=UTC)
    )
    health = await tool.run(args)

    print(health.model_dump_json(indent=2))


asyncio.run(main())
