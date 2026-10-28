"""Draws the Coin Collector starter's pictures (starters/coins/pictures/*.png): pixel art, made here so anyone can
change it and draw it again. Python's standard library only.

    py -3 tuffcode/scripts/make-starter-pictures.py

hero.png  the hero walking: 4 frames side by side (standing, left foot up, standing, right foot up)
coin.png  a coin spinning: 4 frames side by side
bug.png   a ladybird scuttling: 2 frames side by side
Every pixel is drawn SCALE times bigger, so the game shows them sharp at their own size.
"""
import math
import os
import struct
import zlib

SCALE = 3
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "starters", "coins", "pictures")


def png(path, pixels):
    """pixels: rows of (r, g, b, a). Writes them as an RGBA PNG, each pixel SCALE x SCALE."""
    rows = []
    for row in pixels:
        line = b"".join(bytes(p) * SCALE for p in row)
        rows.extend([line] * SCALE)
    w, h = len(pixels[0]) * SCALE, len(pixels) * SCALE

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    raw = b"".join(b"\x00" + line for line in rows)
    data = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
    data += chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(data)


def rgba(hex_color):
    return tuple(int(hex_color[i:i + 2], 16) for i in (1, 3, 5)) + (255,)


CLEAR = (0, 0, 0, 0)


def from_text(rows, palette):
    """A picture drawn as text, one letter per pixel ('.' is see-through)."""
    width = len(rows[0])
    assert all(len(r) == width for r in rows), [len(r) for r in rows]
    return [[CLEAR if ch == "." else rgba(palette[ch]) for ch in row] for row in rows]


def side_by_side(frames):
    return [sum((f[y] for f in frames), []) for y in range(len(frames[0]))]


# ---------------------------------------------------------------- the hero: 16 x 16 a frame
HERO = {"k": "#1c1a24", "s": "#f4c79a", "h": "#6b3e26", "H": "#9a5f3a", "e": "#1c1a24", "r": "#e2543a",
        "R": "#b63d2a", "b": "#37518f", "o": "#3a2a22"}
TOP = [
    ".....kkkkkk.....",
    "....khhhhhhk....",
    "...khhhHHhhhk...",
    "...khhhhhhhhk...",
    "...kshhhhhhsk...",
    "...ksessssesk...",
    "...ksessssesk...",
    "...kssskksssk...",
    "....kssssssk....",
    "...kkrrrrrrkk...",
    "..krrrrrrrrrrk..",
    "..krRrrrrrrRrk..",
    "..ksRbbbbbbRsk..",
]
LEGS = {
    "stand": ["....kbbkkbbk....", "....kbbkkbbk....", "....kookkook...."],
    "left": ["....kbbkkbbk....", "....kookkbbk....", "........kook...."],
    "right": ["....kbbkkbbk....", "....kbbkkook....", "....kook........"],
}


def hero():
    return side_by_side([from_text(TOP + LEGS[legs], HERO) for legs in ("stand", "left", "stand", "right")])


# ---------------------------------------------------------------- the coin: 12 x 12 a frame
def coin_frame(half_width):
    size, c = 12, 6.0
    inside = lambda x, y: ((x + 0.5 - c) / half_width) ** 2 + ((y + 0.5 - c) / 5.6) ** 2 <= 1
    out = []
    for y in range(size):
        row = []
        for x in range(size):
            if not inside(x, y):
                row.append(CLEAR)
            elif not all(inside(x + dx, y + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                row.append(rgba("#7a5310"))  # the outline
            elif x + 0.5 > c + half_width * 0.45 or y >= 9:
                row.append(rgba("#c9952a"))  # the shaded edge
            elif x + 0.5 < c - half_width * 0.25 and y <= 5:
                row.append(rgba("#fff1b8"))  # the shine
            else:
                row.append(rgba("#f7c84a"))
        out.append(row)
    return out


def coin():
    return side_by_side([coin_frame(w) for w in (5.6, 3.4, 1.4, 3.4)])


# ---------------------------------------------------------------- the bug: a ladybird from above, 16 x 16 a frame
def bug_frame(step):
    size = 16
    red, dark, black, white = rgba("#e0453a"), rgba("#a82a22"), rgba("#1c1a24"), rgba("#ffffff")
    body = lambda x, y: ((x + 0.5 - 8) / 6.2) ** 2 + ((y + 0.5 - 9.5) / 5.8) ** 2 <= 1
    head = lambda x, y: ((x + 0.5 - 8) / 3.3) ** 2 + ((y + 0.5 - 3.6) / 2.3) ** 2 <= 1
    spots = [(5.2, 7.4), (10.8, 7.4), (4.6, 11.2), (11.4, 11.2), (8, 13.4)]
    out = [[CLEAR] * size for _ in range(size)]
    # legs: three a side, stepping back and forth between the two frames
    for i, y in enumerate((6, 9, 12)):
        lift = (i + step) % 2
        for x in (1, 14):
            out[y - lift][x] = black
            out[y - lift][x + (1 if x == 1 else -1)] = black
    for y in range(size):
        for x in range(size):
            if head(x, y):
                out[y][x] = black
            if body(x, y):
                edge = not all(body(x + dx, y + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
                spot = any((x + 0.5 - sx) ** 2 + (y + 0.5 - sy) ** 2 <= 1.7 for sx, sy in spots)
                out[y][x] = black if edge or spot or x in (7, 8) and y >= 5 else (dark if x >= 11 or y >= 13 else red)
    out[3][6] = out[3][9] = white  # its eyes
    return out


def bug():
    return side_by_side([bug_frame(0), bug_frame(1)])


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for name, pixels in (("hero", hero()), ("coin", coin()), ("bug", bug())):
        path = os.path.join(OUT, f"{name}.png")
        png(path, pixels)
        print(f"{os.path.relpath(path)}: {len(pixels[0]) * SCALE} x {len(pixels) * SCALE}")
