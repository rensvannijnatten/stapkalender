"""Maakt de PNG-iconen voor de PWA in site/icons/ (zelfde ontwerp als site/icon.svg).

Eenmalig nodig, niet in requirements.txt:
    pip install pillow
    python tools/make_icons.py
"""

import math
import os

from PIL import Image, ImageDraw

GREEN = (0x2F, 0x6B, 0x3F, 255)
WHITE = (255, 255, 255, 255)
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "site", "icons")
SS = 4  # supersampling voor gladde randen


def pin_polygon(cx, cy, r, tip_y, steps=180):
    """Druppelvormige pin: cirkel (cx, cy, r) met een punt naar beneden bij tip_y."""
    d = tip_y - cy
    a = math.asin(r / d)  # hoek van de raaklijnen vanaf de punt
    start = math.pi / 2 + (math.pi / 2 - a)  # raakpunt links-onder
    pts = [(cx, tip_y)]
    sweep = 2 * math.pi - 2 * (math.pi / 2 - a)
    for i in range(steps + 1):
        t = start + sweep * i / steps
        pts.append((cx + r * math.cos(t), cy + r * math.sin(t)))
    return pts


def draw(size, rounded, scale=1.0):
    S = size * SS
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    u = S / 64  # ontwerp is 64x64
    if rounded:
        d.rounded_rectangle([0, 0, S - 1, S - 1], radius=14 * u, fill=GREEN)
    else:
        d.rectangle([0, 0, S, S], fill=GREEN)

    def tr(x, y):  # schalen rond het midden (voor de maskable versie)
        return (32 + (x - 32) * scale) * u, (32 + (y - 32) * scale) * u

    poly = [tr(x, y) for x, y in pin_polygon(32, 30.5, 12, 52)]
    d.polygon(poly, fill=WHITE)
    cx, cy = tr(32, 30.5)
    r = 4.5 * scale * u
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=GREEN)
    return img.resize((size, size), Image.LANCZOS)


def main():
    os.makedirs(OUT, exist_ok=True)
    draw(192, rounded=True).save(os.path.join(OUT, "icon-192.png"))
    draw(512, rounded=True).save(os.path.join(OUT, "icon-512.png"))
    # maskable: volle achtergrond, pin binnen de veilige zone (80%)
    draw(512, rounded=False, scale=0.9).save(os.path.join(OUT, "icon-maskable-512.png"))
    # iOS rondt zelf af en wil geen transparantie
    draw(180, rounded=False).convert("RGB").save(os.path.join(OUT, "apple-touch-icon.png"))
    print("Iconen geschreven naar", OUT)


if __name__ == "__main__":
    main()
