"""OpenAI-compatible providers (OpenAI / Gemini / Ollama) against a local stub server."""

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import pytest

from app.core.config import Settings
from app.core.errors import LLMUnavailableError
from app.llm.base import ChatTurn
from app.llm.factory import llm_status
from app.llm.providers.openai_provider import OpenAIProvider
from app.schemas.llm_outputs import InsightText

REPLY = {"headline": "Revenue peaked in October.", "bullets": ["December was second."]}


class Stub:
    """Records requests; rejects json_schema formats when `reject_schema` is set."""

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self.reject_schema = False
        self.content = json.dumps(REPLY)


@pytest.fixture
def stub() -> Iterator[tuple[Stub, str]]:
    state = Stub()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            state.requests.append(body)
            fmt = body.get("response_format", {}).get("type")
            if state.reject_schema and fmt == "json_schema":
                self._send(
                    400,
                    {
                        "error": {
                            "message": "response_format json_schema is not supported",
                            "type": "invalid_request_error",
                        }
                    },
                )
                return
            self._send(200, {
                "id": "c1", "object": "chat.completion", "created": 0, "model": body["model"],
                "choices": [{"index": 0, "finish_reason": "stop",
                             "message": {"role": "assistant", "content": state.content, "refusal": None}}],
            })  # fmt: skip

        def _send(self, status: int, payload: dict[str, Any]) -> None:
            data = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args: Any) -> None:
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield state, f"http://127.0.0.1:{server.server_port}/v1"
    server.shutdown()


def _ask(provider: OpenAIProvider) -> InsightText:
    return provider.generate_structured(system="sys", messages=[ChatTurn("user", "q")], output_type=InsightText)


def test_structured_output_via_json_schema(stub: tuple[Stub, str]) -> None:
    state, url = stub
    provider = OpenAIProvider(api_key="k", model="gemini-3.8-flash", timeout=10, base_url=url, name="gemini")
    result = _ask(provider)
    assert result.headline == REPLY["headline"]
    request = state.requests[0]
    assert request["model"] == "gemini-3.8-flash"
    assert request["response_format"]["type"] == "json_schema"
    assert request["response_format"]["json_schema"]["strict"] is True


def test_falls_back_to_json_mode_when_schema_unsupported(stub: tuple[Stub, str]) -> None:
    state, url = stub
    state.reject_schema = True
    state.content = "```json\n" + json.dumps(REPLY) + "\n```"  # local models often add fences
    provider = OpenAIProvider(api_key="ollama", model="qwen2.5-coder:7b", timeout=10, base_url=url, name="ollama")
    result = _ask(provider)
    assert result.bullets == REPLY["bullets"]
    fallback = state.requests[-1]
    assert fallback["response_format"] == {"type": "json_object"}
    assert "JSON schema" in fallback["messages"][0]["content"]


def test_unreachable_server_gives_a_helpful_message() -> None:
    provider = OpenAIProvider(
        api_key="ollama", model="m", timeout=30, base_url="http://127.0.0.1:9/v1", name="ollama",
        unreachable_hint="Could not reach Ollama. Is it running?",
    )  # fmt: skip
    provider._client = provider._client.with_options(max_retries=0)
    with pytest.raises(LLMUnavailableError, match="Is it running"):
        _ask(provider)


@pytest.mark.parametrize(
    ("env", "expected"),
    [
        ({"llm_provider": "ollama"}, (True, "ollama", "qwen2.5-coder:7b")),
        ({"llm_provider": "ollama", "llm_model": "llama3.1:8b"}, (True, "ollama", "llama3.1:8b")),
        ({"llm_provider": "gemini", "gemini_api_key": "free-key"}, (True, "gemini", "gemini-3.8-flash")),
        ({"llm_provider": "none"}, (False, "none", None)),
    ],
)
def test_provider_status(env: dict[str, str], expected: tuple[bool, str, str | None]) -> None:
    assert llm_status(Settings(**env)) == expected  # type: ignore[arg-type]


def test_gemini_without_key_is_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert llm_status(Settings(llm_provider="gemini", gemini_api_key=None))[0] is False
