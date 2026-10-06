from collections.abc import AsyncIterator

import pytest


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
