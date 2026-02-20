"""HTTP client wrapper for dbt Cloud APIs."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, Iterator, Literal, Optional

import httpx
from pydantic import BaseModel

from . import get_version
from .config import Settings

log = logging.getLogger(__name__)


class _AdaptiveRateLimiter:
    """Coordinate 429 backoff across concurrent worker threads."""

    def __init__(self, max_sleep_seconds: float = 30.0) -> None:
        self._condition = threading.Condition()
        self._cooldown_until = 0.0
        self._recent_429_count = 0
        self._max_sleep_seconds = max_sleep_seconds

    def wait_for_window(self) -> None:
        """Block until the shared rate-limit cooldown window has elapsed."""
        with self._condition:
            while True:
                now = time.monotonic()
                remaining = self._cooldown_until - now
                if remaining <= 0:
                    return
                self._condition.wait(timeout=remaining)

    def register_429(self, retry_after: Optional[float], fallback_backoff: float) -> float:
        """Expand the cooldown window after a 429 and return sleep duration."""
        with self._condition:
            self._recent_429_count += 1
            base_delay = retry_after if retry_after and retry_after > 0 else fallback_backoff
            # Escalate modestly for repeated 429s to prevent thread herding.
            penalty = min(1.0 + (self._recent_429_count - 1) * 0.25, 3.0)
            sleep_time = min(base_delay * penalty, self._max_sleep_seconds)
            self._cooldown_until = max(self._cooldown_until, time.monotonic() + sleep_time)
            self._condition.notify_all()
            return sleep_time

    def register_success(self) -> None:
        """Decay 429 pressure after successful requests."""
        with self._condition:
            if self._recent_429_count > 0:
                self._recent_429_count -= 1


_RATE_LIMITER = _AdaptiveRateLimiter()


class ApiError(RuntimeError):
    """Raised when the dbt Cloud API returns a non-success status."""

    def __init__(self, response: httpx.Response) -> None:
        self.status_code = response.status_code
        self.response_text = response.text
        super().__init__(f"dbt Cloud API error {self.status_code}: {self.response_text[:200]}")


class DbtCloudClient:
    """Typed wrapper around the dbt Cloud v2/v3 APIs with pagination helpers."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._clients: Dict[str, httpx.Client] = {
            "v2": httpx.Client(
                base_url=f"{settings.host}/api/v2/accounts/{settings.account_id}",
                headers={
                    "Authorization": f"Token {settings.api_token}",
                    "User-Agent": f"dbtcloud-importer/{get_version()}",
                    "Accept-Encoding": "gzip, deflate",
                },
                timeout=settings.timeout,
                verify=settings.verify_ssl,
            ),
            "v3": httpx.Client(
                base_url=f"{settings.host}/api/v3/accounts/{settings.account_id}",
                headers={
                    "Authorization": f"Bearer {settings.api_token}",
                    "User-Agent": f"dbtcloud-importer/{get_version()}",
                    "Accept-Encoding": "gzip, deflate",
                },
                timeout=settings.timeout,
                verify=settings.verify_ssl,
            ),
        }

    @classmethod
    def from_settings(cls, settings: Settings) -> "DbtCloudClient":
        """Create a new client instance (useful for per-thread clients)."""
        return cls(settings)

    def close(self) -> None:
        for client in self._clients.values():
            client.close()

    def get(
        self,
        path: str,
        *,
        version: Literal["v2", "v3"] = "v2",
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        client = self._clients[version]
        attempt = 0

        while True:
            _RATE_LIMITER.wait_for_window()
            resp = client.get(path, params=params)
            if resp.status_code < 400:
                _RATE_LIMITER.register_success()
                return resp.json()

            # Don't retry on 404 - resource doesn't exist
            if resp.status_code == 404:
                raise ApiError(resp)

            attempt += 1
            retry_after = resp.headers.get("Retry-After")

            if resp.status_code == 429 and retry_after and self.settings.rate_limit_retry_after:
                if attempt > self.settings.max_retries:
                    raise ApiError(resp)
                try:
                    sleep_time = float(retry_after)
                except ValueError:
                    sleep_time = self.settings.backoff_factor * (2 ** (attempt - 1))
                sleep_time = _RATE_LIMITER.register_429(
                    retry_after=sleep_time,
                    fallback_backoff=self.settings.backoff_factor * (2 ** (attempt - 1)),
                )
                log.warning(
                    "Rate limit hit (429) on %s %s (attempt %s/%s). "
                    "Sleeping %.2fs with shared backoff",
                    version,
                    path,
                    attempt,
                    self.settings.max_retries,
                    sleep_time,
                )
                time.sleep(sleep_time)
                continue

            # 409 Conflict can indicate rate limiting or concurrency issues
            if resp.status_code == 409:
                log.warning(
                    "Conflict (409) on %s %s - possible rate limit or concurrent request issue. "
                    "Response: %s",
                    version,
                    path,
                    resp.text[:200] if resp.text else "(empty)",
                )
                # Continue to retry logic below

            if attempt > self.settings.max_retries:
                raise ApiError(resp)

            backoff = self.settings.backoff_factor * (2 ** (attempt - 1))
            log.info(
                "Retrying %s %s after status %s (attempt %s, sleeping %.2fs)",
                version,
                path,
                resp.status_code,
                attempt,
                backoff,
            )
            time.sleep(backoff)

    def paginate(
        self,
        path: str,
        *,
        version: Literal["v2", "v3"] = "v2",
        params: Optional[Dict[str, Any]] = None,
        page_size: int = 100,
        data_key: str = "data",
    ) -> Iterator[Dict[str, Any]]:
        """Yield records from a paginated endpoint using limit/offset semantics."""
        params = dict(params or {})
        offset = params.pop("offset", 0)
        limit = params.pop("limit", page_size)

        while True:
            page_params = {**params, "limit": limit, "offset": offset}
            payload = self.get(path, version=version, params=page_params)
            items = payload.get(data_key, [])
            if not isinstance(items, list):
                log.warning("Unexpected payload structure for %s: %s", path, payload)
                break

            for item in items:
                yield item

            if len(items) < limit:
                break

            offset += limit


class PaginatedResponse(BaseModel):
    data: list[dict[str, Any]]
    status: Optional[int] = None


