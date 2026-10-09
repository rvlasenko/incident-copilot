from collections.abc import AsyncIterator

import pytest

from incident_copilot.domain.loaders import FixtureDataset, load_dataset
from tests.factories import REPO_FIXTURES_DIR


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    """Run async tests on asyncio only (anyio would otherwise also try trio)."""
    return "asyncio"


@pytest.fixture(scope="session", autouse=True)
async def shared_event_loop(anyio_backend: str) -> AsyncIterator[None]:
    """Keep one event loop alive for the whole session, as in production.

    The OpenAI client pools its connections process-wide. With a fresh loop per
    test, a pooled connection outlives the loop it was opened on and the next
    test fails with "Event loop is closed".
    """
    yield


@pytest.fixture(scope="session")
def repo_dataset() -> FixtureDataset:
    """The repository fixtures, loaded once; safe to share because the dataset is immutable."""
    return load_dataset(REPO_FIXTURES_DIR)
