"""Adeps Points Verts — via open data van ODWB (Open Data Wallonie-Bruxelles), licentie CC BY.

Dataset: https://www.odwb.be/explore/dataset/points-verts-de-ladeps/
Het veld `id` is hetzelfde id als in https://www.am-sport.cfwb.be/adeps/pv_detail.asp?i=<id>.
"""

from __future__ import annotations

import datetime as dt
import logging

from ..model import Tocht, clean, norm_distances
from .base import Source

log = logging.getLogger(__name__)

API = "https://www.odwb.be/api/explore/v2.1/catalog/datasets/points-verts-de-ladeps/records"
DETAIL = "https://www.am-sport.cfwb.be/adeps/pv_detail.asp?i={id}"
PAGE = 100


def _title(s: str) -> str:
    """'LE ROEULX' -> 'Le Roeulx', 'BRAINE-L\\'ALLEUD' -> "Braine-l'Alleud" (ongeveer)."""
    s = clean(s)
    if not s or not s.isupper():
        return s
    small = {"de", "du", "des", "la", "le", "les", "lez", "sur", "sous", "en", "aux", "au", "lès"}
    out = []
    for wi, word in enumerate(s.lower().split(" ")):
        parts = []
        for pi, p in enumerate(word.split("-")):
            parts.append(p if (pi or wi) and p in small else p[:1].upper() + p[1:])
        out.append("-".join(parts))
    return " ".join(out)


def _yes(v) -> bool:
    return clean(str(v or "")).lower() in ("oui", "yes", "ja", "true", "1")


def parse_record(r: dict) -> Tocht | None:
    activity = clean(r.get("activite"))
    if activity and "marche" not in activity.lower():
        return None
    date = clean(str(r.get("date") or ""))[:10]
    dt.date.fromisoformat(date)

    geo = r.get("geopoint") or {}
    lat = geo.get("lat") if geo else None
    lon = geo.get("lon") if geo else None
    if lat is None and r.get("latitude"):
        lat, lon = float(r["latitude"]), float(r["longitude"])

    city = _title(r.get("localite") or "") or clean(r.get("entite"))
    meeting = clean(r.get("lieu_de_rendez_vous"))
    address = ", ".join(x for x in (meeting, city) if x)

    distances = [5, 10, 20]
    if _yes(r.get("15km")):
        distances.append(15)

    statut = clean(r.get("statut"))
    cancelled = statut.lower().startswith("annul")
    warning = ""
    if statut and not cancelled and statut.upper() != "OK":
        warning = statut

    info = clean(r.get("infos_rendez_vous"))
    gare = clean(r.get("gare"))
    description_parts = []
    if info:
        description_parts.append(info)
    if gare:
        description_parts.append(f"Openbaar vervoer: {gare}")

    contact = " ".join(x for x in (clean(r.get("prenom")), clean(r.get("nom"))) if x)
    organizer = clean(r.get("groupement"))
    if contact:
        organizer = f"{organizer} ({contact})" if organizer else contact

    return Tocht(
        source_url=DETAIL.format(id=r["id"]),
        promoter="Adeps",
        land="BE",
        date=date,
        name="Point Vert Adeps",
        organizer=organizer,
        address=address,
        city=city,
        lat=float(lat) if lat is not None else None,
        lon=float(lon) if lon is not None else None,
        distances=norm_distances(distances),
        start_time="",
        description="\n".join(description_parts),
        website="",
        email="",
        phone1=clean(r.get("gsm")),
        phone2="",
        warning=warning,
        cancelled=cancelled,
    )


class AdepsSource(Source):
    key = "adeps"
    promoter = "Adeps"

    def fetch(self, start: dt.date, end: dt.date) -> list[Tocht]:
        where = f'date >= "{start.isoformat()}" and date <= "{end.isoformat()}"'
        out: list[Tocht] = []
        offset = 0
        while True:
            r = self.session.get(API, params={"where": where, "order_by": "date,id", "limit": PAGE, "offset": offset})
            data = r.json()
            results = data.get("results", [])
            for rec in results:
                t = parse_record(rec)
                if t:
                    out.append(t)
            offset += len(results)
            if not results or offset >= data.get("total_count", 0):
                break
        return out
