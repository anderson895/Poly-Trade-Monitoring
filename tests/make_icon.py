"""One-off: gawing square app icon ang icon.png (crop sa robot, alis puting
background sa gilid) at i-export bilang multi-size icon.ico.

Run:  .\\venv\\Scripts\\python.exe -m tests.make_icon
"""
from PIL import Image

SRC = "icon.png"

img = Image.open(SRC).convert("RGBA")

# Transparent ang background (RGBA) — ang alpha channel mismo ang mask.
# May faint semi-transparent glow sa gilid kaya may threshold (alpha > 40).
mask = img.getchannel("A").point(lambda p: 255 if p > 40 else 0)
bbox = mask.getbbox()
print(f"source: {img.size}, content bbox: {bbox}")
img = img.crop(bbox)

# Gawing square: i-pad ng TRANSPARENT sa mas maikling side, +6% margin
w, h = img.size
side = int(max(w, h) * 1.06)
canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
canvas.paste(img, ((side - w) // 2, (side - h) // 2), img)
print(f"square canvas: {canvas.size}")

canvas.save("icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48),
                               (64, 64), (128, 128), (256, 256)])
canvas.resize((512, 512), Image.LANCZOS).save("icon_square.png")
print("[OK] icon.ico + icon_square.png created")
