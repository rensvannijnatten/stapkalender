"""Wandelsport Vlaanderen — https://wandel.be/wandelkalender/

Lijst: /wandelkalender/?date_after=dd-mm-jjjj&date_before=dd-mm-jjjj&page=N (server-side gepagineerd)
Detail: /wandelkalender/<id>/ met een schema.org Event in JSON-LD (datum, coördinaten, status).
Statusbadges ("Gewijzigd", ...) staan alleen op de lijstpagina.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import re

from bs4 import BeautifulSoup, Tag

from ..model import Tocht, clean, clean_url, norm_distances, parse_km
from .base import Source

log = logging.getLogger(__name__)

BASE = "https://wandel.be"
LIST_URL = BASE + "/wandelkalender/?date_after={start:%d-%m-%Y}&date_before={end:%d-%m-%Y}&page={page}"
DETAIL_RE = re.compile(r"^https?://(?:www\.)?wandel\.be/wandelkalender/(\d+)/?$")
CANCEL_RE = re.compile(r"afgelast|geannuleerd|annul", re.I)
MAX_PAGES = 100


def detail_url(event_id: str) -> str:
    return f"https://www.wandel.be/wandelkalender/{event_id}/"


def parse_list(html: str, page: int = 1) -> tuple[dict[str, list[str]], bool]:
    """-> ({detail_url: [statussen]}, er_is_een_volgende_pagina)"""
    soup = BeautifulSoup(html, "lxml")
    events: dict[str, list[str]] = {}
    for card in soup.select("div.b-event"):
        a = card.find("a", href=DETAIL_RE)
        if not a:
            continue
        url = detail_url(DETAIL_RE.match(a["href"]).group(1))
        events[url] = [clean(s.get_text()) for s in card.select(".b-event__status")]
    has_next = bool(events) and soup.find("a", href=re.compile(rf"[?&]page={page + 1}(?:&|$)")) is not None
    return events, has_next


def _event_jsonld(soup: BeautifulSoup) -> dict:
    for s in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(s.string or "", strict=False)
        except ValueError:
            continue
        if isinstance(data, dict) and data.get("@type") == "Event":
            return data
    raise ValueError("Geen schema.org Event in JSON-LD")


def _section(soup: BeautifulSoup, title: str) -> Tag | None:
    """De container-div van een sectie met kop `title` (span/p.fs-3)."""
    for el in soup.select(".fs-3.fw-bold"):
        if clean(el.get_text()).lower() == title.lower():
            return el.parent
    return None


def parse_detail(html: str, url: str, statuses: list[str] | None = None) -> Tocht:
    soup = BeautifulSoup(html, "lxml")
    ev = _event_jsonld(soup)
    statuses = statuses or []

    name = clean(ev.get("name")) or clean(soup.h1.get_text() if soup.h1 else "")
    date = clean(ev.get("startDate"))[:10]
    dt.date.fromisoformat(date)  # valideert

    loc = ev.get("location") or {}
    geo = loc.get("geo") or {}
    lat = float(geo["latitude"]) if geo.get("latitude") else None
    lon = float(geo["longitude"]) if geo.get("longitude") else None

    # Startplaats-blok: [locatienaam, straat, "postcode plaats"]
    address_parts: list[str] = []
    city = ""
    sec = _section(soup, "Startplaats")
    if sec:
        lines = [clean(d.get_text(" ")) for d in sec.select(".list-group > div")]
        lines = [x for x in lines if x]
        address_parts = lines
        if lines:
            m = re.match(r"^\d{4}\s+(.+)$", lines[-1])
            if m:
                city = m.group(1)
    if not address_parts:
        addr = loc.get("address") or {}
        address_parts = [clean(loc.get("name")), clean(addr.get("streetAddress")),
                         clean(f"{addr.get('postalCode', '')} {addr.get('addressLocality', '')}")]
    if not city:
        city = clean((loc.get("address") or {}).get("addressLocality"))

    distances: list[float] = []
    sec = _section(soup, "Afstanden")
    if sec:
        distances = norm_distances(parse_km(clean(d.get_text())) for d in sec.select(".rounded-pill"))

    start_time = ""
    sec = _section(soup, "Starturen")
    if sec and sec.p:
        start_time = clean(sec.p.get_text()).replace(".", ":")

    description = ""
    main_col = soup.select_one(".order-lg-0")
    if main_col:
        first = main_col.find("div", class_="pb-5", recursive=False)
        if first and not first.find(class_="fs-3"):
            description = clean(first.get_text(" "))
    if not description:
        description = clean(ev.get("description"))

    organizer = clean((ev.get("organizer") or {}).get("name"))
    website = email = ""
    phones: list[str] = []
    side = soup.select_one(".order-lg-1")
    if side:
        img = side.find("img", alt="Website")
        if img and img.find_next("a"):
            website = clean_url(img.find_next("a").get("href", ""))
        for a in side.select('a[href^="tel:"]'):
            p = clean(a.get_text())
            if p and p not in phones:
                phones.append(p)
        mail = side.select_one('a[href^="mailto:"]')
        if mail:
            email = clean(mail.get_text())
        if not organizer:
            h = side.select_one(".h5 a")
            organizer = clean(h.get_text()) if h else ""

    status_text = " ".join(statuses)
    cancelled = (
        "cancelled" in str(ev.get("eventStatus", "")).lower()
        or bool(CANCEL_RE.search(status_text))
        or bool(re.search(r"\bafgelast\b", name, re.I))
    )
    warning = ""
    if not cancelled and any(s.lower() == "gewijzigd" for s in statuses):
        warning = "Gewijzigd door de organisator, kijk op de website voor de laatste info."
    elif not cancelled and statuses:
        warning = status_text

    return Tocht(
        source_url=url,
        promoter="Wandelsport Vlaanderen",
        land="BE",
        date=date,
        name=name,
        organizer=organizer,
        address=", ".join(address_parts),
        city=city,
        lat=lat,
        lon=lon,
        distances=distances,
        start_time=start_time,
        description=description,
        website=website,
        email=email,
        phone1=phones[0] if phones else "",
        phone2=phones[1] if len(phones) > 1 else "",
        warning=warning,
        cancelled=cancelled,
    )


class WSVLSource(Source):
    key = "wsvl"
    promoter = "Wandelsport Vlaanderen"

    def fetch(self, start: dt.date, end: dt.date) -> list[Tocht]:
        events: dict[str, list[str]] = {}
        for page in range(1, MAX_PAGES + 1):
            html = self.session.get_text(LIST_URL.format(start=start, end=end, page=page))
            found, has_next = parse_list(html, page)
            new = {u: s for u, s in found.items() if u not in events}
            events.update(new)
            if not new or not has_next:
                break
        log.info("WSVL: %d tochten in lijst", len(events))
        out: list[Tocht] = []
        for url, statuses in events.items():
            html = self.session.get_text(url)
            t = parse_detail(html, url, statuses)
            if start.isoformat() <= t.date <= end.isoformat():
                out.append(t)
        return out
