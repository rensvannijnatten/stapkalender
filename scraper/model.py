"""Datamodel voor één tocht + hulpfuncties die alle bronnen delen."""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field

DUTCH_MONTHS = {
    "januari": 1, "februari": 2, "maart": 3, "april": 4, "mei": 5, "juni": 6,
    "juli": 7, "augustus": 8, "september": 9, "oktober": 10, "november": 11, "december": 12,
}


def make_id(source_url: str) -> str:
    return hashlib.sha1(source_url.encode("utf-8")).hexdigest()[:12]


@dataclass
class Tocht:
    source_url: str
    promoter: str
    land: str
    date: str
    name: str
    organizer: str = ""
    address: str = ""
    city: str = ""
    lat: float | None = None
    lon: float | None = None
    distances: list[float] = field(default_factory=list)
    start_time: str = ""
    description: str = ""
    website: str = ""
    email: str = ""
    phone1: str = ""
    phone2: str = ""
    warning: str = ""
    cancelled: bool = False
    last_change: str = ""
    id: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = make_id(self.source_url)

    def to_dict(self) -> dict:
        return asdict(self)

    def content_hash(self) -> str:
        d = self.to_dict()
        d.pop("last_change", None)
        return content_hash(d)


def content_hash(d: dict) -> str:
    items = sorted((k, v) for k, v in d.items() if k != "last_change")
    return hashlib.sha1(repr(items).encode("utf-8")).hexdigest()


def clean(text: str | None) -> str:
    """Witruimte normaliseren."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def parse_km(text: str) -> float | None:
    """'10,0km' / '4 km' / '12.5 km' -> 10.0 / 4.0 / 12.5"""
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*km", text, re.I)
    if not m:
        return None
    return float(m.group(1).replace(",", "."))


def norm_distances(values) -> list[float]:
    out = sorted({round(v, 1) for v in values if v is not None and v > 0})
    return [int(v) if v == int(v) else v for v in out]


def clean_url(url: str) -> str:
    url = clean(url)
    if url and not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    return url
