"""Polite HTTP client: descriptive User-Agent, robots.txt, ≤1 request/sec per host, conditional requests."""
from __future__ import annotations

import time
import urllib.robotparser
from urllib.parse import urlsplit

import httpx

USER_AGENT = (
    "AsiaCarbonAtlas/0.1 (non-commercial research; "
    "+https://github.com/haing-dev/asia-carbon-atlas)"
)
MIN_INTERVAL = 1.0  # seconds between requests to the same host


class PoliteClient:
    def __init__(self, timeout: float = 60.0):
        self.client = httpx.Client(
            headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate, br"},
            timeout=timeout,
            follow_redirects=True,
        )
        self._last: dict[str, float] = {}
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}

    def _allowed(self, url: str) -> bool:
        parts = urlsplit(url)
        base = f"{parts.scheme}://{parts.netloc}"
        if base not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                r = self.client.get(base + "/robots.txt")
                rp.parse(r.text.splitlines() if r.status_code == 200 else [])
            except httpx.HTTPError:
                rp = None  # robots unreachable: treat as allowed, as browsers do
            self._robots[base] = rp
        rp = self._robots[base]
        return True if rp is None else rp.can_fetch(USER_AGENT, url)

    def _wait(self, host: str) -> None:
        elapsed = time.monotonic() - self._last.get(host, 0.0)
        if elapsed < MIN_INTERVAL:
            time.sleep(MIN_INTERVAL - elapsed)
        self._last[host] = time.monotonic()

    def get(self, url: str, etag: str | None = None, last_modified: str | None = None, **kw) -> httpx.Response:
        if not self._allowed(url):
            raise PermissionError(f"robots.txt disallows {url}")
        headers = kw.pop("headers", {})
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified
        self._wait(urlsplit(url).netloc)
        return self.client.get(url, headers=headers, **kw)

    def head(self, url: str, **kw) -> httpx.Response:
        if not self._allowed(url):
            raise PermissionError(f"robots.txt disallows {url}")
        self._wait(urlsplit(url).netloc)
        return self.client.head(url, **kw)
