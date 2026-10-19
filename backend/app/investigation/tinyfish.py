"""Documented TinyFish Search/Fetch REST calls. No Agent or LLM endpoint."""
import json
import re

import httpx

from .schemas import RetrievalCall

SEARCH_URL = "https://api.search.tinyfish.ai"
FETCH_URL = "https://api.fetch.tinyfish.ai"
MAX_RESPONSE_BYTES = 3 * 1024 * 1024


class TinyFishError(Exception):
    """Public, fixed error codes only; never includes request headers/body."""


class TinyFishClient:
    def __init__(self, api_key: str, http_client: httpx.AsyncClient | None = None):
        self._api_key = api_key
        self._http_client = http_client
        self.calls: list[RetrievalCall] = []

    @property
    def configured(self) -> bool:
        return bool(self._api_key and self._api_key.lower() not in {"your_actual_key", "your_api_key", "replace_me"})

    async def _request(self, client, operation, method, url, **kwargs):
        try:
            async with client.stream(method, url, headers={"X-API-Key": self._api_key},
                                     timeout=httpx.Timeout(50 if operation == "fetch" else 20, connect=10), **kwargs) as response:
                request_id = response.headers.get("x-request-id", "")
                self.calls.append(RetrievalCall(operation=operation, http_status=response.status_code,
                    request_id=request_id if re.fullmatch(r"[\w-]{1,128}", request_id) else None))
                if response.status_code != 200:
                    code = {401: "authentication_failed", 403: "access_denied", 402: "quota_exhausted", 429: "rate_limited"}.get(response.status_code, "upstream_http_error")
                    raise TinyFishError(code)
                chunks, size = [], 0
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > MAX_RESPONSE_BYTES:
                        raise TinyFishError("response_too_large")
                    chunks.append(chunk)
                # JSON over HTTP is UTF-8; do not use an upstream charset hint to
                # reinterpret Unicode as Windows-1252/Latin-1.
                data = json.loads(b"".join(chunks).decode("utf-8-sig"))
                if not isinstance(data, dict) or not isinstance(data.get("results"), list):
                    raise TinyFishError("invalid_response")
                return data
        except httpx.TimeoutException:
            raise TinyFishError("timeout") from None
        except httpx.RequestError:
            raise TinyFishError("network_error") from None
        except (ValueError, UnicodeError):
            raise TinyFishError("invalid_response") from None

    async def _json(self, operation, method, url, **kwargs):
        if not self.configured:
            raise TinyFishError("not_configured")
        if self._http_client is not None:
            return await self._request(self._http_client, operation, method, url, **kwargs)
        # Fixed provider endpoints; do not forward API credentials across redirects
        # or pick up ambient HTTP proxy settings. Never log provider bodies/errors.
        async with httpx.AsyncClient(follow_redirects=False, trust_env=False) as client:
            return await self._request(client, operation, method, url, **kwargs)

    async def search(self, query: str) -> list[dict]:
        data = await self._json("search", "GET", SEARCH_URL, params={"query": query, "language": "en"})
        return [row for row in data["results"][:20] if isinstance(row, dict)]

    async def fetch(self, urls: list[str]) -> dict:
        data = await self._json("fetch", "POST", FETCH_URL, json={
            "urls": urls[:4], "format": "markdown", "ttl": 0,
            "links": False, "image_links": False, "per_url_timeout_ms": 30000,
        })
        if not isinstance(data.get("errors", []), list):
            raise TinyFishError("invalid_response")
        return data
