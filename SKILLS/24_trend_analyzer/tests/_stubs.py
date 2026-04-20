"""Shared test stubs for mocking Anthropic + httpx."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FakeAnthropicResponse:
    text: str
    input_tokens: int = 500
    output_tokens: int = 150

    @property
    def content(self):
        class _TextBlock:
            def __init__(self, t):
                self.text = t

        return [_TextBlock(self.text)]

    @property
    def usage(self):
        class _Usage:
            def __init__(self, i, o):
                self.input_tokens = i
                self.output_tokens = o

        return _Usage(self.input_tokens, self.output_tokens)


class FakeMessages:
    def __init__(self, payload: Any):
        self._payload = payload
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        body = (
            json.dumps(self._payload)
            if not isinstance(self._payload, str)
            else self._payload
        )
        return FakeAnthropicResponse(text=body)


@dataclass
class FakeAnthropic:
    payload: Any
    messages: FakeMessages = field(init=False)

    def __post_init__(self):
        self.messages = FakeMessages(self.payload)


def install_fake_anthropic(monkeypatch, payload: Any, api_key: str = "test-key") -> FakeAnthropic:
    """Replace ``anthropic.AsyncAnthropic`` so LLM calls return ``payload``.

    Returns the fake instance so tests can introspect the recorded calls.
    """
    import anthropic

    from core.config import settings

    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", api_key, raising=False)

    fake = FakeAnthropic(payload=payload)

    def _factory(*args, **kwargs):
        return fake

    monkeypatch.setattr(anthropic, "AsyncAnthropic", _factory)
    return fake


# ── httpx fake ─────────────────────────────────────────────────────────────


@dataclass
class FakeHTTPResponse:
    status_code: int = 200
    content: bytes = b""
    headers: dict = field(default_factory=dict)


class FakeAsyncClient:
    def __init__(self, response: FakeHTTPResponse):
        self._response = response
        self.requests: list[tuple[str, str]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url, **kwargs):
        self.requests.append(("GET", url))
        return self._response


def install_fake_httpx(monkeypatch, module, response: FakeHTTPResponse) -> FakeAsyncClient:
    """Patch ``httpx.AsyncClient`` inside ``module`` to return ``response``."""
    client = FakeAsyncClient(response)

    def _factory(*args, **kwargs):
        return client

    monkeypatch.setattr(module.httpx, "AsyncClient", _factory)
    return client
