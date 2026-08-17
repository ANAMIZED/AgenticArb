"""AgenticArb Python SDK."""
from __future__ import annotations

from typing import Any, Optional

import httpx


class AgenticArbClient:
    def __init__(self, base_url: str = "http://localhost:8080", timeout: float = 60.0) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(base_url=self.base_url, timeout=timeout)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "AgenticArbClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def health(self) -> dict[str, Any]:
        r = self._client.get("/health")
        r.raise_for_status()
        return r.json()

    def status(self) -> dict[str, Any]:
        r = self._client.get("/v1/status")
        r.raise_for_status()
        return r.json()

    def scan(self) -> dict[str, Any]:
        r = self._client.post("/v1/scan")
        r.raise_for_status()
        return r.json()

    def cycle(self, payload: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        r = self._client.post("/v1/cycle", json=payload or {})
        r.raise_for_status()
        return r.json()
