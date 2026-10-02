"""Polite cached HTTP: descriptive User-Agent, throttling, on-disk cache."""
import json
import time

import httpx

from .cache import HttpCache
from .config import USER_AGENT

HOUR, DAY = 3600, 86400


class Fetcher:
    def __init__(self, cache: HttpCache, min_interval: float = 1.0, client: httpx.Client | None = None):
        self.cache = cache
        self.min_interval = min_interval
        self.client = client or httpx.Client(
            headers={"User-Agent": USER_AGENT, "API-Version": "v1"}, timeout=30, follow_redirects=True
        )
        self._last = 0.0

    def get_text(self, url: str, params: dict | None = None, max_age: float = DAY) -> str:
        key = url + ("?" + "&".join(f"{k}={v}" for k, v in sorted((params or {}).items())) if params else "")
        hit = self.cache.get(key, max_age)
        if hit is not None:
            return hit
        wait = self.min_interval - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        resp = self.client.get(url, params=params)
        self._last = time.monotonic()
        resp.raise_for_status()
        self.cache.put(key, resp.text)
        return resp.text

    def get_json(self, url: str, params: dict | None = None, max_age: float = DAY):
        return json.loads(self.get_text(url, params, max_age))

    def post_text(self, url: str, data: dict, params: dict | None = None, max_age: float = HOUR) -> str:
        key = "POST " + url + ("?" + "&".join(f"{k}={v}" for k, v in sorted((params or {}).items())) if params else "")
        hit = self.cache.get(key, max_age)
        if hit is not None:
            return hit
        wait = self.min_interval - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        resp = self.client.post(url, data=data, params=params)
        self._last = time.monotonic()
        resp.raise_for_status()
        self.cache.put(key, resp.text)
        return resp.text
