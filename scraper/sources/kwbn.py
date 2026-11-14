"""KWbN — https://www.wandel.nl/evenementen/

robots.txt verbiedt /umbraco/ (de API achter de lijstpagina), dus:
- alle evenement-URL's komen uit https://www.wandel.nl/sitemap.xml (met lastmod);
- elke detailpagina wordt alleen opnieuw opgehaald als lastmod veranderd is (cache in data/kwbn_cache.json);
- de bron geeft geen coördinaten: geocoding via Nominatim (zie geocode.py).

Meerdaagse evenementen ("za en zo", "van ... tot en met ...") worden overgeslagen.
Nachttochten ("zaterdag ... op zondag ...") tellen als één dag (de startdag).
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
import re

from bs4 import BeautifulSoup

from ..geocode import Geocoder
from ..model import DUTCH_MONTHS, Tocht, clean, clean_url, norm_distances, parse_km
from .base import Source

log = logging.getLogger(__name__)

SITEMAP = "https://www.wandel.nl/sitemap.xml"
EVENT_URL_RE = re.compile(r"^https://www\.wandel\.nl/evenementen/[^/]+/$")
DATE_RE = re.compile(r"(\d{1,2})\s+(" + "|".join(DUTCH_MONTHS) + r")\s+(\d{4})", re.I)
POSTCODE_RE = re.compile(r"\b(\d{4})\s?([A-Z]{2})\b")
MAX_ERROR_RATIO = 0.2


def parse_sitemap(xml: str) -> dict[str, str]:
    """-> {event_url: lastmod}"""
    soup = BeautifulSoup(xml, "xml")
    out: dict[str, str] = {}
    for url in soup.find_all("url"):
        loc = clean(url.loc.get_text()) if url.loc else ""
        if EVENT_URL_RE.match(loc):
            out[loc] = clean(url.lastmod.get_text()) if url.lastmod else ""
    return out


def parse_dates(text: str) -> tuple[str, str, bool]:
    """'zondag, 15 november 2026' -> ('2026-11-15', '2026-11-15', False)
    Meerdere dagen -> (eerste, laatste, True). 'X op Y' (nachttocht) telt als één dag."""
    dates = [dt.date(int(y), DUTCH_MONTHS[m.lower()], int(d)) for d, m, y in DATE_RE.findall(text)]
    if not dates:
        raise ValueError(f"Geen datum gevonden in {text!r}")
    first, last = min(dates), max(dates)
    night = re.search(r"\d{4}\s+op\s+\w+dag", text) and (last - first).days <= 1
    multi = first != last and not night
    return first.isoformat(), last.isoformat(), multi


def _split_city(address: str) -> str:
    m = POSTCODE_RE.search(address)
    if m:
        return clean(address[m.end():]).strip(", ")
    parts = [p.strip() for p in address.split(",") if p.strip()]
    return parts[-1] if parts else ""


def parse_detail(html: str, url: str) -> tuple[Tocht, bool]:
    """-> (tocht, is_meerdaags)"""
    soup = BeautifulSoup(html, "lxml")
    h1 = soup.select_one("h1.c-experience__heading") or soup.h1
    if not h1:
        raise ValueError("Geen titel gevonden")
    name = clean(h1.get_text())

    header: dict[str, str] = {}
    for item in soup.select("dl.c-list-info--experience .o-list-cols__list-item"):
        term = clean(item.dt.get_text()) if item.dt else ""
        header[term] = " | ".join(clean(dd.get_text(" ")) for dd in item.find_all("dd"))
    date, _end, multi = parse_dates(header.get("Datum", ""))

    # Bezoekersinformatie (aside): Startpunt, Organisatie, Website, email, Telefoonnummer
    venue = street = ""
    organizer = website = email = ""
    phones: list[str] = []
    aside = soup.select_one("aside dl.o-key-value-list") or soup
    for dt_ in aside.find_all("dt", recursive=False):
        label = clean(dt_.get_text())
        dd = dt_.find_next_sibling("dd")
        if not dd:
            continue
        if label == "Startpunt":
            inner_dt = dd.find("dt")
            inner_dd = dd.find("dd")
            venue = clean(inner_dt.get_text()) if inner_dt else ""
            street = clean(inner_dd.get_text(" ")) if inner_dd else ""
        elif label == "Organisatie":
            org = dd.select_one(".u-text-bold")
            organizer = clean(org.get_text()) if org else ""
            for kdt in dd.find_all("dt"):
                k = clean(kdt.get_text()).lower()
                kdd = kdt.find_next_sibling("dd")
                if not kdd:
                    continue
                a = kdd.find("a")
                if k == "website" and a:
                    website = clean_url(a.get("href", ""))
                elif k == "email" and a:
                    email = clean(a.get_text())
                elif k.startswith("telefoon"):
                    p = clean(a.get_text() if a else kdd.get_text())
                    if p and p not in phones:
                        phones.append(p)
    if not organizer:
        organizer = header.get("Organisatie", "")
    if not venue:
        venue = header.get("Locatie", "")

    distances: list[float] = []
    starts: list[str] = []
    ends: list[str] = []
    for item in soup.select("dl.c-list-info .o-list-cols__list-item"):
        if not item.dt or clean(item.dt.get_text()) != "Afstanden":
            continue
        for dd in item.find_all("dd"):
            txt = clean(dd.get_text(" "))
            distances.append(parse_km(txt))
            times = re.findall(r"\b(\d{1,2})[:.](\d{2})\b", txt)
            if times:
                starts.append(f"{int(times[0][0]):02d}:{times[0][1]}")
                ends.append(f"{int(times[-1][0]):02d}:{times[-1][1]}")
    start_time = ""
    if starts:
        lo, hi = min(starts), max(ends)
        start_time = lo if lo == hi else f"{lo}-{hi}"

    desc_parts = []
    for sel in (".c-experience__text", ".c-intro-text"):
        el = soup.select_one(sel)
        if el:
            for br in el.find_all("br"):
                br.replace_with("\n")
            t = "\n".join(clean(x) for x in el.get_text().split("\n"))
            t = re.sub(r"\n{2,}", "\n\n", t).strip()
            if t and t not in desc_parts:
                desc_parts.append(t)

    badges = [clean(b.get_text()) for b in soup.select(".c-badge")]
    error_badges = [clean(b.get_text()) for b in soup.select(".c-badge--error")]
    cancelled = bool(error_badges) or bool(re.search(r"\b(afgelast|geannuleerd|gaat niet door)\b", name, re.I))
    warning = ""
    if not cancelled and any(b.lower() == "gewijzigd" for b in badges):
        warning = "Gewijzigd door de organisator, kijk op de website voor de laatste info."

    address = ", ".join(x for x in (venue, street) if x)
    tocht = Tocht(
        source_url=url,
        promoter="KWbN",
        land="NL",
        date=date,
        name=name,
        organizer=organizer,
        address=address,
        city=_split_city(street) or venue,
        distances=norm_distances(distances),
        start_time=start_time,
        description="\n\n".join(desc_parts),
        website=website,
        email=email,
        phone1=phones[0] if phones else "",
        phone2=phones[1] if len(phones) > 1 else "",
        warning=warning,
        cancelled=cancelled,
    )
    return tocht, multi


def geocode_candidates(t: Tocht) -> list[str]:
    street = t.address.split(", ", 1)[1] if ", " in t.address else t.address
    street = POSTCODE_RE.sub(lambda m: f"{m.group(1)} {m.group(2)}", street)
    cands = [street]
    m = POSTCODE_RE.search(street)
    if m:
        cands.append(f"{m.group(1)} {m.group(2)}")
    if t.city:
        cands.append(t.city)
    return list(dict.fromkeys(c for c in cands if c))


class KWbNSource(Source):
    key = "kwbn"
    promoter = "KWbN"

    def __init__(self, session, data_dir: str, geocoder: Geocoder | None = None):
        super().__init__(session, data_dir)
        self.cache_path = os.path.join(data_dir, "kwbn_cache.json")
        self.geocoder = geocoder or Geocoder(session, os.path.join(data_dir, "geocache.json"))

    def _load_cache(self) -> dict:
        if os.path.exists(self.cache_path):
            with open(self.cache_path, encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _save_cache(self, cache: dict) -> None:
        tmp = self.cache_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=1, sort_keys=True)
            f.write("\n")
        os.replace(tmp, self.cache_path)

    def fetch(self, start: dt.date, end: dt.date) -> list[Tocht]:
        urls = parse_sitemap(self.session.get_text(SITEMAP))
        if not urls:
            raise RuntimeError("Sitemap bevat geen evenementen")
        log.info("KWbN: %d evenementen in sitemap", len(urls))
        old = self._load_cache()
        cache: dict = {}
        fetched = errors = 0
        today = start.isoformat()
        for url, lastmod in urls.items():
            entry = old.get(url)
            if entry and (entry.get("lastmod") == lastmod or (entry.get("date") or "9999") < today):
                cache[url] = entry
                continue
            fetched += 1
            try:
                t, multi = parse_detail(self.session.get_text(url), url)
            except Exception as e:
                errors += 1
                log.warning("KWbN: %s overgeslagen: %s", url, e)
                if entry:
                    cache[url] = entry  # vorige versie houden
                continue
            cache[url] = {"lastmod": lastmod, "date": t.date, "multi_day": multi, "tocht": t.to_dict()}
            if fetched % 50 == 0:
                log.info("KWbN: %d detailpagina's opgehaald", fetched)
                self._save_cache(cache | {u: e for u, e in old.items() if u in urls and u not in cache})
        self._save_cache(cache)
        log.info("KWbN: %d opgehaald, %d fouten", fetched, errors)
        if fetched and errors / fetched > MAX_ERROR_RATIO:
            raise RuntimeError(f"KWbN: te veel fouten ({errors}/{fetched})")

        out: list[Tocht] = []
        for entry in cache.values():
            if entry.get("multi_day") or not entry.get("tocht"):
                continue
            if not (start.isoformat() <= entry["date"] <= end.isoformat()):
                continue
            t = Tocht(**entry["tocht"])
            loc = self.geocoder.locate(geocode_candidates(t), "nl")
            if loc:
                t.lat, t.lon = loc
            out.append(t)
        self.geocoder.save()
        return out
