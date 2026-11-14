import json
from pathlib import Path

from scraper.sources.adeps import parse_record

FX = Path(__file__).parent / "fixtures" / "adeps"


def records():
    return json.loads((FX / "records_2026-11-15.json").read_text(encoding="utf-8"))["results"]


def by_id(i):
    return next(r for r in records() if r["id"] == i)


def test_all_records_parse():
    out = [parse_record(r) for r in records()]
    assert len(out) == 6 and all(out)
    assert {t.date for t in out} == {"2026-11-15"}


def test_regular_record():
    t = parse_record(by_id(24785))
    assert t.source_url == "https://www.am-sport.cfwb.be/adeps/pv_detail.asp?i=24785"
    assert t.promoter == "Adeps" and t.land == "BE"
    assert t.city == "Bois-de-Lessines"
    assert t.distances == [5, 10, 15, 20]  # 15km = Oui
    assert t.lat is not None and t.lon is not None
    assert not t.cancelled
    assert t.phone1


def test_cancelled_record():
    t = parse_record(by_id(24784))
    assert t.cancelled
    assert t.city == "Mazée"
    assert t.distances == [5, 10, 20]  # 15km = Non
    assert "Bancontact" in t.description


def test_non_walking_activity_is_skipped():
    r = dict(by_id(24785), activite="VTT")
    assert parse_record(r) is None
