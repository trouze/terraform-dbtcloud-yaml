"""Regression tests for API rate-limit retry handling."""

from __future__ import annotations

from typing import Any

import pytest

from importer.client import ApiError, DbtCloudClient, _RATE_LIMITER
from importer.config import Settings


class _FakeResponse:
    def __init__(
        self,
        status_code: int,
        *,
        payload: dict[str, Any] | None = None,
        text: str = "",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text
        self.headers = headers or {}

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeHttpClient:
    def __init__(self, responses: list[_FakeResponse]) -> None:
        self._responses = responses
        self.calls = 0

    def get(self, _path: str, params: dict[str, Any] | None = None) -> _FakeResponse:
        _ = params
        idx = min(self.calls, len(self._responses) - 1)
        self.calls += 1
        return self._responses[idx]

    def close(self) -> None:
        return


def _reset_rate_limiter() -> None:
    with _RATE_LIMITER._condition:  # type: ignore[attr-defined]
        _RATE_LIMITER._cooldown_until = 0.0  # type: ignore[attr-defined]
        _RATE_LIMITER._recent_429_count = 0  # type: ignore[attr-defined]


def test_429_retry_after_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("importer.client.time.sleep", lambda _s: None)
    _reset_rate_limiter()

    settings = Settings(
        host="https://example.com",
        account_id=1,
        api_token="token",
        max_retries=2,
        backoff_factor=0.01,
    )
    client = DbtCloudClient(settings)
    fake_client = _FakeHttpClient(
        [
            _FakeResponse(429, text="rate limited", headers={"Retry-After": "0"}),
            _FakeResponse(429, text="rate limited", headers={"Retry-After": "0"}),
            _FakeResponse(429, text="rate limited", headers={"Retry-After": "0"}),
        ]
    )
    client._clients["v2"] = fake_client  # type: ignore[assignment]

    with pytest.raises(ApiError):
        client.get("/projects/", version="v2")

    # Initial try + max_retries attempts, then fail.
    assert fake_client.calls == 3


def test_invalid_retry_after_falls_back_and_recovers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("importer.client.time.sleep", lambda _s: None)
    _reset_rate_limiter()

    settings = Settings(
        host="https://example.com",
        account_id=1,
        api_token="token",
        max_retries=3,
        backoff_factor=0.01,
    )
    client = DbtCloudClient(settings)
    fake_client = _FakeHttpClient(
        [
            _FakeResponse(429, text="rate limited", headers={"Retry-After": "not-a-number"}),
            _FakeResponse(200, payload={"data": [{"id": 1}]}),
        ]
    )
    client._clients["v2"] = fake_client  # type: ignore[assignment]

    payload = client.get("/projects/", version="v2")

    assert payload == {"data": [{"id": 1}]}
    assert fake_client.calls == 2
