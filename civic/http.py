"""Polite cached HTTP: descriptive User-Agent, throttling, on-disk cache."""
import json
import time

import httpx

from .cache import HttpCache
from .config import USER_AGENT

HOUR, DAY = 3600, 86400
RETRY_WAITS = (3, 10, 30, 90)  # seconds before each retry of a 429, 5xx or network error; then give up


class Fetcher:
    sleep = staticmethod(time.sleep)  # replaceable in tests

    def __init__(self, cache: HttpCache, min_interval: float = 1.0, client: httpx.Client | None = None):
        self.cache = cache
        self.min_interval = min_interval
        self.client = client or httpx.Client(
            headers={"User-Agent": USER_AGENT, "API-Version": "v1"}, timeout=30, follow_redirects=True
        )
        self._last = 0.0

    def _send(self, method: str, url: str, **kw) -> httpx.Response:
        """One request, retried with backoff on 429, 5xx and network errors (public APIs hiccup; a long build must not lose a page to one)."""
        for attempt, wait in enumerate((*RETRY_WAITS, None)):
            try:
                resp = self.client.request(method, url, **kw)
                self._last = time.monotonic()
                if resp.status_code != 429 and resp.status_code < 500:
                    resp.raise_for_status()
                    return resp
                err = httpx.HTTPStatusError(f"{resp.status_code} for {url}", request=resp.request, response=resp)
            except (httpx.TransportError, httpx.TimeoutException) as e:
                err = e
            if wait is None:
                raise err
            self.sleep(wait)

    def get_text(self, url: str, params: dict | None = None, max_age: float = DAY, cache: bool = True) -> str:
        """cache=False: never read or write the on-disk cache (for URLs carrying personal data)."""
        key = url + ("?" + "&".join(f"{k}={v}" for k, v in sorted((params or {}).items())) if params else "")
        if cache:
            hit = self.cache.get(key, max_age)
            if hit is not None:
                return hit
        wait = self.min_interval - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        resp = self._send("GET", url, params=params)
        if cache:
            self.cache.put(key, resp.text)
        return resp.text

    def get_json(self, url: str, params: dict | None = None, max_age: float = DAY, cache: bool = True):
        return json.loads(self.get_text(url, params, max_age, cache))

    def post_text(self, url: str, data: dict, params: dict | None = None, max_age: float = HOUR) -> str:
        key = "POST " + url + ("?" + "&".join(f"{k}={v}" for k, v in sorted((params or {}).items())) if params else "")
        hit = self.cache.get(key, max_age)
        if hit is not None:
            return hit
        wait = self.min_interval - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        resp = self._send("POST", url, params=params, data=data)
        self.cache.put(key, resp.text)
        return resp.text
