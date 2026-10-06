"""OpenAIProvider error handling against a local stand-in for the OpenAI API."""

import json
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import Final

import pytest
from pydantic import SecretStr

from incident_copilot.agent.state import Plan
from incident_copilot.config import LLMSettings
from incident_copilot.llm.base import LLMError
from incident_copilot.llm.openai_provider import OpenAIProvider

pytestmark = pytest.mark.anyio

LEAKED_KEY_FRAGMENT: Final = "sk-ab****wxyz"


class _RejectWithKeyEcho(BaseHTTPRequestHandler):
    """Answers every request the way OpenAI answers a wrong key: 401 with the key echoed."""

    def do_POST(self) -> None:
        body = json.dumps(
            {
                "error": {
                    "message": f"Incorrect API key provided: {LEAKED_KEY_FRAGMENT}",
                    "code": "invalid_api_key",
                }
            }
        ).encode()
        self.send_response(401)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        pass


@pytest.fixture
def rejecting_api_url() -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _RejectWithKeyEcho)
    Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1"
    finally:
        server.shutdown()
        server.server_close()


def _provider() -> OpenAIProvider:
    settings = LLMSettings(
        openai_api_key=SecretStr("sk-test"), llm_max_retries=0, llm_timeout_seconds=2
    )
    return OpenAIProvider(settings)


async def test_http_error_keeps_status_and_drops_provider_message(
    rejecting_api_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENAI_BASE_URL", rejecting_api_url)

    with pytest.raises(LLMError) as exc_info:
        await _provider().generate(system="s", user="u", schema=Plan)

    assert exc_info.value.status_code == 401
    assert "Authentication" in exc_info.value.error_type
    assert LEAKED_KEY_FRAGMENT not in str(exc_info.value)


async def test_connection_failure_has_no_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A closed local port fails instantly, so the real error path runs without network access.
    monkeypatch.setenv("OPENAI_BASE_URL", "http://127.0.0.1:9/v1")

    with pytest.raises(LLMError) as exc_info:
        await _provider().generate(system="s", user="u", schema=Plan)

    assert "Connection" in exc_info.value.error_type
    assert exc_info.value.status_code is None
