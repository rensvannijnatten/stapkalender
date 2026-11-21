"""Haal alle bronnen op en schrijf site/data/tochten.json.

Exit-code 1 als een bron faalt of 0 tochten oplevert. De andere bronnen worden dan toch
bijgewerkt; voor de kapotte bron blijven de vorige gegevens staan. Is het totaal 0, dan
wordt er niets geschreven.

Gebruik:  python -m scraper.main [--days 60] [--only wsvl,kwbn,adeps] [--failed]

--failed draait alleen de bronnen die in de vorige tochten.json als mislukt staan
(voor een tweede poging later in dezelfde workflow-run).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import sys
from zoneinfo import ZoneInfo

from .geocode import Geocoder
from .http import PoliteSession
from .model import Tocht, content_hash
from .sources.adeps import AdepsSource
from .sources.kwbn import KWbNSource
from .sources.wsvl import WSVLSource

log = logging.getLogger("scraper")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TZ = ZoneInfo("Europe/Brussels")


def load_previous(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def failed_keys(doc: dict) -> set[str]:
    return {k for k, v in doc.get("sources", {}).items() if not v.get("ok")}


def merge(fresh: list[Tocht], previous: list[dict], now: str) -> list[dict]:
    """Dedupe op source_url en zet last_change alleen als de inhoud veranderd is."""
    prev_by_url = {p["source_url"]: p for p in previous}
    out: dict[str, dict] = {}
    for t in fresh:
        d = t.to_dict()
        prev = prev_by_url.get(t.source_url)
        if prev and content_hash(prev) == content_hash(d) and prev.get("last_change"):
            d["last_change"] = prev["last_change"]
        else:
            d["last_change"] = now
        out[t.source_url] = d
    return sorted(out.values(), key=lambda d: (d["date"], d["city"], d["name"]))


def run(args) -> int:
    data_dir = os.path.join(ROOT, "data")
    out_path = os.path.join(ROOT, "site", "data", "tochten.json")
    today = dt.datetime.now(TZ).date()
    end = today + dt.timedelta(days=args.days)
    now = dt.datetime.now(TZ).replace(microsecond=0).isoformat()

    session = PoliteSession()
    geocoder = Geocoder(session, os.path.join(data_dir, "geocache.json"))
    sources = [
        WSVLSource(session, data_dir),
        KWbNSource(session, data_dir, geocoder),
        AdepsSource(session, data_dir),
    ]
    prev_doc = load_previous(out_path)
    previous = prev_doc.get("tochten", [])
    if args.failed:
        keep = failed_keys(prev_doc)
        if not keep:
            log.info("Geen mislukte bronnen in de vorige run")
            return 0
        sources = [s for s in sources if s.key in keep]
    elif args.only:
        keep = set(args.only.split(","))
        sources = [s for s in sources if s.key in keep]

    fresh: list[Tocht] = []
    # bronnen die nu niet draaien behouden hun vorige status
    status: dict[str, dict] = {k: v for k, v in prev_doc.get("sources", {}).items()
                               if k not in {s.key for s in sources}}
    failed = False
    for src in sources:
        log.info("== %s", src.promoter)
        try:
            items = src.fetch(today, end)
            if not items:
                raise RuntimeError("0 tochten gevonden")
            fresh.extend(items)
            status[src.key] = {"ok": True, "count": len(items)}
            log.info("%s: %d tochten", src.promoter, len(items))
        except Exception as e:
            failed = True
            log.exception("%s MISLUKT: %s", src.promoter, e)
            kept = [p for p in previous if p["promoter"] == src.promoter
                    and today.isoformat() <= p["date"] <= end.isoformat()]
            fresh.extend(Tocht(**p) for p in kept)
            status[src.key] = {"ok": False, "count": len(kept), "error": str(e)[:300]}

    # bronnen die niet gedraaid hebben (--only) behouden hun vorige gegevens
    ran = {s.promoter for s in sources}
    fresh.extend(Tocht(**p) for p in previous
                 if p["promoter"] not in ran and today.isoformat() <= p["date"] <= end.isoformat())

    tochten = merge(fresh, previous, now)
    missing = sum(1 for t in tochten if t["lat"] is None)
    if missing:
        log.warning("%d tochten zonder coördinaten", missing)
    if not tochten:
        log.error("Totaal 0 tochten: niets geschreven")
        return 1

    doc = {
        "generated": now,
        "from": today.isoformat(),
        "until": end.isoformat(),
        "sources": status,
        "tochten": tochten,
    }
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    tmp = out_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(tmp, out_path)
    geocoder.save()
    log.info("Geschreven: %s (%d tochten)", out_path, len(tochten))
    return 1 if failed else 0


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--days", type=int, default=60)
    p.add_argument("--only", default="")
    p.add_argument("--failed", action="store_true")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    sys.exit(run(args))


if __name__ == "__main__":
    main()
