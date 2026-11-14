import json
from pathlib import Path

import pytest

from scraper.sources.kwbn import geocode_candidates, parse_dates, parse_detail, parse_sitemap

FX = Path(__file__).parent / "fixtures" / "kwbn"


def read(name: str) -> str:
    return (FX / name).read_text(encoding="utf-8")


def test_sitemap_only_event_detail_urls():
    urls = parse_sitemap(read("sitemap.xml"))
    assert list(urls) == [
        "https://www.wandel.nl/evenementen/linschotenloopwandeltocht/",
        "https://www.wandel.nl/evenementen/kerstwandelingbakkeveen/",
    ]
    assert urls["https://www.wandel.nl/evenementen/linschotenloopwandeltocht/"].startswith("2025-12-21")


@pytest.mark.parametrize(
    "text,expected",
    [
        ("zondag, 15 november 2026", ("2026-11-15", "2026-11-15", False)),
        ("zaterdag, 21 november 2026 en zondag, 22 november 2026", ("2026-11-21", "2026-11-22", True)),
        ("van vrijdag, 9 oktober 2026 tot en met zaterdag, 10 oktober 2026", ("2026-10-09", "2026-10-10", True)),
        ("vrijdag, 4 september 2026 op zaterdag, 5 september 2026", ("2026-09-04", "2026-09-05", False)),
    ],
)
def test_parse_dates(text, expected):
    assert parse_dates(text) == expected


def test_detail_regular():
    url = "https://www.wandel.nl/evenementen/60e-olat-winterserie-vanuit-eersel-eersel/"
    t, multi = parse_detail(read("detail_eersel.html"), url)
    assert not multi
    assert t.name == "60e Dagwandeltocht vanuit Eersel"
    assert t.date == "2026-11-15"
    assert t.promoter == "KWbN" and t.land == "NL"
    assert t.address == "De Keizer, Postelseweg 88, 5521RD Eersel"
    assert t.city == "Eersel"
    assert t.distances == [10, 15, 20, 30, 40]
    assert t.start_time == "08:00-13:00"
    assert t.organizer == "Wandelsportvereniging OLAT"
    assert t.website == "https://www.olat.nl/winterserie"
    assert t.email == "dagtochten@olat.nl"
    assert t.description.startswith("Beleef de Kempen")
    assert t.lat is None  # KWbN geeft geen coördinaten
    assert not t.cancelled and t.warning == ""


def test_detail_changed():
    t, multi = parse_detail(read("detail_bleiswijk_gewijzigd.html"), "u")
    assert t.warning.startswith("Gewijzigd")
    assert t.phone1 == "06 23842661"
    assert not multi


def test_detail_multi_day_is_flagged():
    _t, multi = parse_detail(read("detail_dieren_meerdaags.html"), "u")
    assert multi


def test_detail_cancelled_badge():
    html = read("detail_eersel.html").replace(
        '<article class="c-experience__content">',
        '<span class="c-badge c-badge--error mt">Afgelast</span><article class="c-experience__content">', 1)
    t, _ = parse_detail(html, "u")
    assert t.cancelled


def test_geocode_candidates_go_from_precise_to_coarse():
    t, _ = parse_detail(read("detail_eersel.html"), "u")
    assert geocode_candidates(t) == ["Postelseweg 88, 5521 RD Eersel", "5521 RD", "Eersel"]
