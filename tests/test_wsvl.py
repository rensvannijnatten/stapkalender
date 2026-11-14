from pathlib import Path

from scraper.sources.wsvl import parse_detail, parse_list

FX = Path(__file__).parent / "fixtures" / "wsvl"


def read(name: str) -> str:
    return (FX / name).read_text(encoding="utf-8")


def test_list_first_page():
    events, has_next = parse_list(read("list_first.html"), page=1)
    assert len(events) == 15
    assert has_next
    assert all(u.startswith("https://www.wandel.be/wandelkalender/") and u.endswith("/") for u in events)
    assert events["https://www.wandel.be/wandelkalender/10333/"] == ["Gewijzigd"]


def test_list_last_page_has_no_next():
    events, has_next = parse_list(read("list_last.html"), page=12)
    assert len(events) == 3
    assert not has_next


def test_detail_regular():
    url = "https://www.wandel.be/wandelkalender/8573/"
    t = parse_detail(read("detail_8573.html"), url)
    assert t.name == "Gent bij Nacht"
    assert t.date == "2026-12-12"
    assert t.promoter == "Wandelsport Vlaanderen" and t.land == "BE"
    assert t.city == "Gent"
    assert t.address == "Odisee Technologiecampus Gent, Gebroeders de Smetstraat 1, 9000 Gent"
    assert round(t.lat, 4) == 51.0612 and round(t.lon, 4) == 3.7087
    assert t.distances == [6, 9, 12]
    assert t.start_time == "14:30-20:30"
    assert t.organizer == "Florastappers Gent vzw"
    assert t.website == "http://www.florastappersgent.be"
    assert t.email == "florastappersgent@proximus.be"
    assert t.phone1 and t.phone2
    assert t.description.startswith("Start 12 km tot 20.00u.")
    assert not t.cancelled and t.warning == ""
    assert t.id and len(t.id) == 12


def test_detail_with_control_character_in_jsonld():
    t = parse_detail(read("detail_8714.html"), "https://www.wandel.be/wandelkalender/8714/")
    assert t.name == "Move4betterlife"
    assert t.date == "2026-11-21"
    assert t.lat is not None
    assert t.distances == [6, 10, 12, 16, 20]


def test_detail_changed_status_gives_warning():
    t = parse_detail(read("detail_10333_gewijzigd.html"), "https://www.wandel.be/wandelkalender/10333/", ["Gewijzigd"])
    assert t.warning.startswith("Gewijzigd")
    assert not t.cancelled
    assert t.start_time == "10:00"


def test_detail_cancelled_via_jsonld_or_badge():
    html = read("detail_8573.html").replace("schema.org/EventScheduled", "schema.org/EventCancelled")
    assert parse_detail(html, "u").cancelled
    assert parse_detail(read("detail_8573.html"), "u", ["Afgelast"]).cancelled
