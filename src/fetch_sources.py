"""3개 스크리너의 GitHub Pages JSON을 수집한다."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

SOURCES = {
    "smart_money": "https://vipasset1004-lucky.github.io/smart-money-screener/results.json",
    "new_high":    "https://vipasset1004-lucky.github.io/new-high-screener/results.json",
    "divergence":  "https://vipasset1004-lucky.github.io/divergence-screener/divergence_results.json",
}


@dataclass
class SourcePayload:
    name: str
    url: str
    ok: bool
    data: dict[str, Any] | None = None
    error: str | None = None
    fetched_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def _fetch_json(url: str, timeout: int = 30) -> dict[str, Any]:
    req = Request(url, headers={"User-Agent": "jjingalnom-screener/1.0", "Cache-Control": "no-cache"})
    with urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    return json.loads(raw.decode("utf-8"))


def fetch_one(name: str, url: str, retries: int = 3) -> SourcePayload:
    last_err = "unknown"
    for attempt in range(1, retries + 1):
        try:
            data = _fetch_json(url)
            return SourcePayload(name=name, url=url, ok=True, data=data)
        except (HTTPError, URLError, json.JSONDecodeError, TimeoutError) as e:
            last_err = f"{type(e).__name__}: {e}"
            if attempt < retries:
                time.sleep(2 ** attempt)
    return SourcePayload(name=name, url=url, ok=False, error=last_err)


def fetch_all() -> dict[str, SourcePayload]:
    return {name: fetch_one(name, url) for name, url in SOURCES.items()}


if __name__ == "__main__":
    results = fetch_all()
    for name, payload in results.items():
        if payload.ok:
            keys = list(payload.data.keys()) if isinstance(payload.data, dict) else "(list root)"
            print(f"[OK]   {name}: top-level keys = {keys}")
        else:
            print(f"[FAIL] {name}: {payload.error}")
