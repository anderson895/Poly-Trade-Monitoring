"""One-off: gumawa ng maliliit na PNG icons para sa QSS subcontrols
(spinbox plus/minus, combobox chevron) — ang CSS border-triangle trick ay
hindi maaasahan sa Qt subcontrols kaya totoong images ang gamit.

Run:  .\\venv\\Scripts\\python.exe -m tests.make_arrows
"""
from pathlib import Path

from PIL import Image, ImageDraw

COLOR = (156, 163, 175, 255)  # theme.MUTED #9ca3af
S = 24          # canvas (2x para crisp kapag pinaliit ng QSS sa 12px)
T = 3           # kapal ng linya
ASSETS = Path("assets")
ASSETS.mkdir(exist_ok=True)


def canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)


# PLUS
img, d = canvas()
m = 5  # margin
d.rectangle([S // 2 - T // 2, m, S // 2 + T // 2, S - m], fill=COLOR)   # vertical
d.rectangle([m, S // 2 - T // 2, S - m, S // 2 + T // 2], fill=COLOR)   # horizontal
img.save(ASSETS / "plus.png")

# MINUS
img, d = canvas()
d.rectangle([m, S // 2 - T // 2, S - m, S // 2 + T // 2], fill=COLOR)
img.save(ASSETS / "minus.png")

# CHEVRON DOWN (para sa combobox)
img, d = canvas()
d.line([(6, 9), (S // 2, 16)], fill=COLOR, width=T)
d.line([(S // 2, 16), (S - 6, 9)], fill=COLOR, width=T)
img.save(ASSETS / "chevron_down.png")

print("[OK] assets/plus.png, minus.png, chevron_down.png created")
