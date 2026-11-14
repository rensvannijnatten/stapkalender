"""Beleefde HTTP-client: eigen User-Agent, max 1 request/seconde per host, retries met backoff."""

from __future__ import annotations

import logging
import time
from urllib.parse import urlparse

import requests

USER_AGENT = "wandeltochten-web/1.0 (+https://github.com/rensvannijnatten/stapkalender)"

log = logging.getLogger(__name__)


class PoliteSession:
    def __init__(self, min_interval: float = 1.0, retries: int = 4, backoff: float = 2.0, timeout: float = 30.0):
        self.min_interval = min_interval
        self.retries = retries
        self.backoff = backoff
        self.timeout = timeout
        self._last: dict[str, float] = {}
        self._s = requests.Session()
        self._s.headers["User-Agent"] = USER_AGENT
        self._s.headers["Accept-Language"] = "nl,fr;q=0.8,en;q=0.5"

    def _wait(self, host: str) -> None:
        last = self._last.get(host)
        if last is not None:
            delay = self.min_interval - (time.monotonic() - last)
            if delay > 0:
                time.sleep(delay)
        self._last[host] = time.monotonic()

    def get(self, url: str, **kwargs) -> requests.Response:
        host = urlparse(url).netloc
        err: Exception | None = None
        for attempt in range(self.retries + 1):
            self._wait(host)
            try:
                r = self._s.get(url, timeout=self.timeout, **kwargs)
                if r.status_code in (429, 500, 502, 503, 504):
                    raise requests.HTTPError(f"HTTP {r.status_code}", response=r)
                r.raise_for_status()
                return r
            except requests.RequestException as e:
                err = e
                status = getattr(getattr(e, "response", None), "status_code", None)
                if status is not None and 400 <= status < 500 and status != 429:
                    raise
                wait = self.backoff * (2**attempt)
                log.warning("Fout bij %s (%s), poging %d, wacht %.0fs", url, e, attempt + 1, wait)
                time.sleep(wait)
        assert err is not None
        raise err

    def get_text(self, url: str, **kwargs) -> str:
        r = self.get(url, **kwargs)
        if r.encoding is None or r.encoding.lower() == "iso-8859-1":
            r.encoding = r.apparent_encoding
        return r.text
