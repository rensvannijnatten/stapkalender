"""Maakt alle app-iconen uit één ontwerp (variant 1: witte marker met groene wandelschoen).

Schrijft:
  site/icon.svg                      favicon (afgeronde hoeken)
  site/icons/icon-192.png            manifest, "any"
  site/icons/icon-512.png            manifest, "any"
  site/icons/icon-maskable-512.png   manifest, "maskable" (volle achtergrond, inhoud in veilige zone)
  site/icons/apple-touch-icon.png    iOS (volle achtergrond; iOS rondt zelf af)

PNG's worden gerenderd met qlmanage (ingebouwd in macOS):
    python tools/make_icons.py
"""

import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_icon_variants import GREEN, WHITE, boot_in, pin  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
ICONS = os.path.join(SITE, "icons")


def design(rounded: bool, scale: float = 1.0) -> str:
    rx = ' rx="14"' if rounded else ""
    content = pin(32, 26, 19, 58, WHITE) + boot_in(32, 26, 31, GREEN, WHITE)
    if scale != 1.0:
        off = 32 * (1 - scale)
        content = f'<g transform="translate({off:.2f} {off:.2f}) scale({scale})">{content}</g>'
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
        f'<rect width="64" height="64"{rx} fill="{GREEN}"/>{content}</svg>\n'
    )


def render(svg: str, size: int, dest: str) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "icon.svg")
        with open(src, "w", encoding="utf-8") as f:
            f.write(svg)
        subprocess.run(["qlmanage", "-t", "-s", str(size), "-o", tmp, src],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        out = src + ".png"
        if not os.path.exists(out):
            raise RuntimeError(f"qlmanage maakte geen PNG voor {dest}")
        shutil.move(out, dest)


def main() -> None:
    if shutil.which("qlmanage") is None:
        sys.exit("qlmanage niet gevonden; dit script werkt alleen op macOS.")
    os.makedirs(ICONS, exist_ok=True)
    rounded = design(rounded=True)
    full = design(rounded=False)
    with open(os.path.join(SITE, "icon.svg"), "w", encoding="utf-8") as f:
        f.write(rounded)
    render(rounded, 192, os.path.join(ICONS, "icon-192.png"))
    render(rounded, 512, os.path.join(ICONS, "icon-512.png"))
    render(design(rounded=False, scale=0.9), 512, os.path.join(ICONS, "icon-maskable-512.png"))
    render(full, 180, os.path.join(ICONS, "apple-touch-icon.png"))
    print("Iconen geschreven naar", ICONS)


if __name__ == "__main__":
    main()
