"""Geocoding via Nominatim, met een gecommitte cache zodat elk adres maar één keer wordt opgezocht.

Gebruiksbeleid: https://operations.osmfoundation.org/policies/nominatim/
- max 1 request/seconde (PoliteSession regelt dat per host)
- eigen User-Agent met contact
- resultaten cachen
"""

from __future__ import annotations

import json
import logging
import os

from .http import PoliteSession

log = logging.getLogger(__name__)

NOMINATIM = "https://nominatim.openstreetmap.org/search"


class Geocoder:
    def __init__(self, session: PoliteSession, cache_path: str):
        self.session = session
        self.cache_path = cache_path
        self.cache: dict[str, list[float] | None] = {}
        if os.path.exists(cache_path):
            with open(cache_path, encoding="utf-8") as f:
                self.cache = json.load(f)
        self.lookups = 0

    def save(self) -> None:
        tmp = self.cache_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.cache, f, ensure_ascii=False, indent=1, sort_keys=True)
            f.write("\n")
        os.replace(tmp, self.cache_path)

    def _query(self, q: str, country: str) -> list[float] | None:
        key = f"{country.lower()}|{q}"
        if key in self.cache:
            return self.cache[key]
        self.lookups += 1
        r = self.session.get(
            NOMINATIM,
            params={"q": q, "format": "jsonv2", "limit": 1, "countrycodes": country.lower()},
        )
        data = r.json()
        result = [round(float(data[0]["lat"]), 6), round(float(data[0]["lon"]), 6)] if data else None
        self.cache[key] = result
        return result

    def locate(self, candidates: list[str], country: str) -> tuple[float, float] | None:
        """Probeer de kandidaten (van precies naar grof) tot er een treffer is."""
        for q in candidates:
            q = q.strip(" ,")
            if not q:
                continue
            try:
                res = self._query(q, country)
            except Exception as e:  # geocoding mag de scrape niet breken
                log.warning("Geocoding mislukt voor %r: %s", q, e)
                continue
            if res:
                return res[0], res[1]
        return None
