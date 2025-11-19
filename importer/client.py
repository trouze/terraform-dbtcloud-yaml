"""HTTP client wrapper for dbt Cloud APIs."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Iterator, Literal, Optional

import httpx
from pydantic import BaseModel

from . import get_version
from .config import Settings

log = logging.getLogger(__name__)


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
                },
                timeout=settings.timeout,
                verify=settings.verify_ssl,
            ),
            "v3": httpx.Client(
                base_url=f"{settings.host}/api/v3/accounts/{settings.account_id}",
                headers={
                    "Authorization": f"Bearer {settings.api_token}",
                    "User-Agent": f"dbtcloud-importer/{get_version()}",
                },
                timeout=settings.timeout,
                verify=settings.verify_ssl,
            ),
        }

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
            resp = client.get(path, params=params)
            if resp.status_code < 400:
                return resp.json()

            attempt += 1
            retry_after = resp.headers.get("Retry-After")

            if resp.status_code == 429 and retry_after and self.settings.rate_limit_retry_after:
                sleep_time = float(retry_after)
                log.warning("Rate limit hit on %s %s. Sleeping %ss", version, path, sleep_time)
                time.sleep(sleep_time)
                continue

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


