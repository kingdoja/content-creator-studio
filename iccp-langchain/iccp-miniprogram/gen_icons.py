"""Generate 81x81 TabBar icons for the WeChat mini-program."""
from PIL import Image, ImageDraw
import os

SIZE = 81
PAD = 14
COLOR_NORMAL = (153, 153, 153)
COLOR_ACTIVE = (52, 120, 246)
OUT = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(OUT, exist_ok=True)


def _canvas():
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)


def draw_home(color):
    img, d = _canvas()
    cx, cy = SIZE // 2, SIZE // 2
    # roof triangle
    d.polygon([(cx, PAD), (SIZE - PAD, cy + 2), (PAD, cy + 2)], fill=color)
    # body rectangle
    bx1, by1 = PAD + 8, cy + 2
    bx2, by2 = SIZE - PAD - 8, SIZE - PAD
    d.rectangle([bx1, by1, bx2, by2], fill=color)
    # door cutout
    dw = 10
    d.rectangle([cx - dw // 2, by2 - 18, cx + dw // 2, by2], fill=(0, 0, 0, 0))
    return img


def draw_chat(color):
    img, d = _canvas()
    d.rounded_rectangle(
        [PAD, PAD, SIZE - PAD, SIZE - PAD - 8],
        radius=12,
        fill=color,
    )
    # tail triangle
    d.polygon([
        (PAD + 12, SIZE - PAD - 8),
        (PAD + 6, SIZE - PAD + 4),
        (PAD + 24, SIZE - PAD - 8),
    ], fill=color)
    # three dots
    dot_r = 3
    dot_y = (PAD + SIZE - PAD - 8) // 2
    for dx in (-12, 0, 12):
        cx = SIZE // 2 + dx
        d.ellipse([cx - dot_r, dot_y - dot_r, cx + dot_r, dot_y + dot_r],
                  fill=(255, 255, 255))
    return img


def draw_write(color):
    img, d = _canvas()
    # pencil body (rotated rectangle approximated as polygon)
    pts = [
        (SIZE - PAD - 4, PAD + 4),
        (SIZE - PAD, PAD + 8),
        (PAD + 12, SIZE - PAD - 4),
        (PAD + 8, SIZE - PAD),
    ]
    d.polygon(pts, fill=color)
    # pencil tip
    d.polygon([
        (PAD + 8, SIZE - PAD),
        (PAD + 12, SIZE - PAD - 4),
        (PAD + 2, SIZE - PAD + 4),
    ], fill=color)
    # paper background
    paper = [PAD, PAD + 6, SIZE - PAD - 14, SIZE - PAD - 2]
    d.rectangle(paper, outline=color, width=2)
    return img


def draw_user(color):
    img, d = _canvas()
    cx = SIZE // 2
    # head
    hr = 11
    hy = PAD + hr + 2
    d.ellipse([cx - hr, hy - hr, cx + hr, hy + hr], fill=color)
    # body arc
    bw = 22
    d.ellipse([cx - bw, hy + hr + 4, cx + bw, SIZE - PAD + 14], fill=color)
    # clip bottom
    d.rectangle([0, SIZE - PAD, SIZE, SIZE], fill=(0, 0, 0, 0))
    return img


icons = {
    "tab-home": draw_home,
    "tab-chat": draw_chat,
    "tab-write": draw_write,
    "tab-user": draw_user,
}

for name, fn in icons.items():
    fn(COLOR_NORMAL).save(os.path.join(OUT, f"{name}.png"))
    fn(COLOR_ACTIVE).save(os.path.join(OUT, f"{name}-active.png"))
    print(f"  {name}.png / {name}-active.png")

print(f"\nDone – 8 icons saved to {OUT}")
