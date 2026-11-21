from scraper.main import merge
from scraper.model import Tocht, make_id, norm_distances, parse_km


def t(**kw):
    base = dict(source_url="https://x/1", promoter="KWbN", land="NL", date="2026-11-20", name="A", city="B")
    base.update(kw)
    return Tocht(**base)


def test_id_is_stable_hash_of_url():
    assert t().id == make_id("https://x/1") == t(name="other").id


def test_merge_dedupes_on_source_url():
    out = merge([t(), t(name="dubbel")], [], "2026-11-14T03:00:00+01:00")
    assert len(out) == 1


def test_merge_keeps_last_change_when_unchanged():
    prev = t().to_dict() | {"last_change": "2026-11-01T03:00:00+01:00"}
    out = merge([t()], [prev], "2026-11-14T03:00:00+01:00")
    assert out[0]["last_change"] == "2026-11-01T03:00:00+01:00"


def test_merge_updates_last_change_when_changed():
    prev = t().to_dict() | {"last_change": "2026-11-01T03:00:00+01:00"}
    out = merge([t(start_time="08:00")], [prev], "2026-11-14T03:00:00+01:00")
    assert out[0]["last_change"] == "2026-11-14T03:00:00+01:00"


def test_parse_km_and_norm():
    assert parse_km("10,0km 09:00-13:00 uur") == 10.0
    assert parse_km("12.5 km") == 12.5
    assert norm_distances([10.0, 5.0, 12.5, 5.0, None]) == [5, 10, 12.5]


def test_failed_keys():
    from scraper.main import failed_keys
    doc = {"sources": {"wsvl": {"ok": True, "count": 3},
                       "kwbn": {"ok": False, "count": 2, "error": "timeout"}}}
    assert failed_keys(doc) == {"kwbn"}
    assert failed_keys({}) == set()
