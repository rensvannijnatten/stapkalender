"""Schrijft 5 icoonvarianten (marker + wandelschoen) als SVG naar tools/icon-varianten/,
plus een preview.html om ze naast elkaar te bekijken.

    python tools/make_icon_variants.py
    python3 -m http.server 8766 --directory tools/icon-varianten
"""

import math
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon-varianten")

GREEN = "#2F6B3F"
GREEN_DARK_MODE = "#5FAE73"
CREAM = "#F6F4EE"
INK = "#1C2B22"
WHITE = "#FFFFFF"
LIGHT = "#E6EFE8"

# Wandelschoen in een 100x100-vak, neus naar rechts, staat op y=88.
BOOT_UPPER = (
    "M30 10 H54 Q57 10 57 13 L58 42 C66 46 78 50 86 55 C93 59 95 64 95 70 V74 H22 "
    "C20 66 20 56 22 44 C24 30 26 18 28 12 Q28.5 10 30 10 Z"
)
BOOT_SOLE = "M18 74 H97 Q99 74 99 77 V81 Q99 88 92 88 H24 Q16 88 16 81 V77 Q16 74 18 74 Z"
LACES = [(45, 19, 57, 17), (45, 27, 57.5, 26), (46, 35, 58, 35), (50, 43, 62, 46)]
TREAD_X = [27, 40, 53, 66, 79]


def boot(x, y, size, color, cut):
    """Schoen op (x, y) met breedte/hoogte `size`; `cut` = kleur van uitsparingen (veters, profiel)."""
    s = size / 100
    laces = "".join(
        f'<line x1="{a}" y1="{b}" x2="{c}" y2="{d}" />' for a, b, c, d in LACES
    )
    tread = "".join(f'<rect x="{tx}" y="84.5" width="6" height="4" />' for tx in TREAD_X)
    return (
        f'<g transform="translate({x} {y}) scale({s})">'
        f'<path d="{BOOT_UPPER}" fill="{color}"/>'
        f'<path d="{BOOT_SOLE}" fill="{color}"/>'
        f'<g stroke="{cut}" stroke-width="3.6" stroke-linecap="round">{laces}</g>'
        f'<line x1="20" y1="74" x2="96" y2="74" stroke="{cut}" stroke-width="3"/>'
        f'<g fill="{cut}">{tread}</g>'
        "</g>"
    )


def boot_in(cx, cy, size, color, cut):
    """Schoen gecentreerd rond (cx, cy); vorm loopt van x 16-99 en y 10-88 in het 100-vak."""
    s = size / 100
    return boot(cx - 57.5 * s, cy - 49 * s, size, color, cut)


def pin(cx, cy, r, tip_y, color):
    """Druppelvormige marker: cirkel (cx, cy, r) met punt bij (cx, tip_y)."""
    d = tip_y - cy
    phi = math.acos(r / d)
    a1 = math.pi / 2 + phi
    a2 = math.pi / 2 - phi
    x1, y1 = cx + r * math.cos(a1), cy + r * math.sin(a1)
    x2, y2 = cx + r * math.cos(a2), cy + r * math.sin(a2)
    return (
        f'<path d="M{cx:.2f} {tip_y:.2f} L{x1:.2f} {y1:.2f} '
        f'A{r} {r} 0 1 1 {x2:.2f} {y2:.2f} Z" fill="{color}"/>'
    )


def bg(color, rounded=True):
    rx = ' rx="14"' if rounded else ""
    return f'<rect width="64" height="64"{rx} fill="{color}"/>'


def svg(body):
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">{body}</svg>\n'


VARIANTS = {
    # 1. Witte marker op groen, groene schoen in de kop
    "1-marker-groen": svg(
        bg(GREEN) + pin(32, 26, 19, 58, WHITE) + boot_in(32, 26, 31, GREEN, WHITE)
    ),
    # 2. Groene marker op crème, witte schoen in de kop
    "2-marker-licht": svg(
        bg(CREAM) + pin(32, 26, 19, 58, GREEN) + boot_in(32, 26, 31, WHITE, GREEN)
    ),
    # 3. Grote witte schoen met kleine marker erboven
    "3-schoen-met-marker": svg(
        bg(GREEN)
        + boot_in(27, 39, 46, WHITE, GREEN)
        + pin(48, 15, 8, 30, LIGHT)
        + f'<circle cx="48" cy="15" r="3.2" fill="{GREEN}"/>'
    ),
    # 4. Marker met schoen + stippelpad dat ernaartoe loopt
    "4-marker-met-pad": svg(
        bg(GREEN)
        + '<path d="M8 58 C16 52 14 44 24 46 S34 54 37 52" fill="none" stroke="#CFE3D4" '
        'stroke-width="3" stroke-linecap="round" stroke-dasharray="0.1 6"/>'
        + pin(40, 22, 16, 50, WHITE)
        + boot_in(40, 22, 26, GREEN, WHITE)
    ),
    # 5. Donker: lichtgroene marker op donkergroen, donkere schoen in de kop
    "5-marker-donker": svg(
        bg(INK) + pin(32, 26, 19, 58, GREEN_DARK_MODE) + boot_in(32, 26, 31, INK, GREEN_DARK_MODE)
    ),
}

PREVIEW = """<!doctype html>
<html lang="nl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Icoonvarianten</title>
<style>
body { margin: 0; padding: 16px; font-family: system-ui, sans-serif; background: #F6F4EE; color: #1C2B22; }
h1 { font-size: 22px; margin: 0 0 12px; }
.v { display: grid; grid-template-columns: 160px repeat(4, auto); gap: 16px; align-items: center;
     background: #fff; border: 1px solid #DAD6CB; border-radius: 14px; padding: 12px; margin-bottom: 12px; }
.v h2 { font-size: 17px; margin: 0; }
img.big { width: 160px; height: 160px; }
img.mid { width: 60px; height: 60px; }
img.small { width: 32px; height: 32px; }
.round { width: 60px; height: 60px; border-radius: 50%; overflow: hidden; }
.round img { width: 60px; height: 60px; transform: scale(1.0); }
.dark { background: #141A16; padding: 8px; border-radius: 10px; }
</style></head><body>
<h1>Icoonvarianten — marker met wandelschoen</h1>
%ROWS%
</body></html>
"""


def main():
    os.makedirs(OUT, exist_ok=True)
    rows = []
    for name, content in VARIANTS.items():
        with open(os.path.join(OUT, name + ".svg"), "w", encoding="utf-8") as f:
            f.write(content)
        rows.append(
            f'<div class="v"><div><h2>{name}</h2><img class="big" src="{name}.svg" alt=""></div>'
            f'<img class="mid" src="{name}.svg" alt="">'
            f'<img class="small" src="{name}.svg" alt="">'
            f'<div class="round"><img src="{name}.svg" alt=""></div>'
            f'<div class="dark"><img class="mid" src="{name}.svg" alt=""></div></div>'
        )
    with open(os.path.join(OUT, "preview.html"), "w", encoding="utf-8") as f:
        f.write(PREVIEW.replace("%ROWS%", "\n".join(rows)))
    print("Geschreven naar", OUT)


if __name__ == "__main__":
    main()
