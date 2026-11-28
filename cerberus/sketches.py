"""Hand-drawn icons in the style of the logo (a pencil sketch), used instead of emoji.

Each icon is a few pencil strokes on a 24x24 grid. `svg()` gives an inline picture for
HTML the app writes itself (life list, badges, Social posts), coloured by the text
around it. `data_uri()` gives a standalone copy for CSS, where it's used as a mask so
the icon takes the colour of whatever it's on (the bottom tab bar, the photo button).

The look copies the dog icon: freehand lines rather than ruler-straight ones, gone over
twice (a firm line, then a lighter one a little off, so the ends and corners don't quite
meet), plus some pencil hatching for shade. The helpers below (`_line`, `_shape`,
`_curve`, `_ring`, `_dot`, `_hatch`) turn simple coordinates into those freehand strokes.
Their small wobbles come from a random generator seeded with the coordinates, so every
icon comes out the same each time. They are plain vectors (no blur filters), so they
stay sharp on any screen.

To add an icon: add its strokes to SKETCHES (stroke="currentColor" and fill="none" are
set for you), and any hatching to SHADING.
"""
from __future__ import annotations

import base64
import math
import random

Point = tuple[float, float]

# The logo's dachshund head (assets/logo.svg), shrunk to fit the 24x24 grid. Its own
# stroke widths win over the ones `_strokes` sets, which gives it its bold double line.
_DOG = (
    '<svg x="1" y="0.5" width="22" height="23" viewBox="0 0 180 200">'
    '<path stroke-width="10" d="M158 192 C160 160 168 128 160 100 C154 78 140 60 118 56 '
    "C100 53 86 60 78 72 C66 80 46 86 26 92 C16 95 12 104 18 110 C26 118 44 120 62 122 "
    'C76 124 88 132 96 142 C104 156 108 174 108 192"/>'
    '<path stroke-width="9.5" d="M112 70 C128 66 142 78 144 98 C147 122 142 146 130 156 '
    'C120 164 106 158 104 146 C101 128 104 104 110 84"/>'
    '<ellipse cx="74" cy="88" rx="9" ry="8" fill="currentColor" stroke="none"/>'
    '<ellipse cx="20" cy="100" rx="13" ry="11" fill="currentColor" stroke="none"/>'
    "</svg>"
)

# --- freehand drawing helpers ------------------------------------------------------

WOBBLE = .16  # how far (in grid units) a hand-drawn point strays from where it's aimed


def _rng(*key) -> random.Random:
    """The same 'random' wobble every time for the same stroke."""
    return random.Random(repr(key))


def _n(v: float) -> str:
    text = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text


def _pt(p: Point) -> str:
    return f"{_n(p[0])} {_n(p[1])}"


def _jitter(points: list[Point], r: random.Random, amount: float = WOBBLE) -> list[Point]:
    return [(x + r.uniform(-amount, amount), y + r.uniform(-amount, amount)) for x, y in points]


def _bowed(p: Point, q: Point, r: random.Random, bow: float = .05) -> str:
    """A 'straight' line from p to q as a hand draws it: very slightly curved."""
    dx, dy = q[0] - p[0], q[1] - p[1]
    length = math.hypot(dx, dy) or 1
    off = r.uniform(-bow, bow) * length
    c = ((p[0] + q[0]) / 2 - dy / length * off, (p[1] + q[1]) / 2 + dx / length * off)
    return f"Q{_pt(c)} {_pt(q)}"


def _past(p: Point, q: Point, by: float) -> Point:
    """The point `by` units beyond q, carrying on from p (a pencil overshooting)."""
    dx, dy = q[0] - p[0], q[1] - p[1]
    length = math.hypot(dx, dy) or 1
    return q[0] + dx / length * by, q[1] + dy / length * by


def _line(x1: float, y1: float, x2: float, y2: float) -> str:
    """A freehand line, running a touch past both ends."""
    r = _rng("line", x1, y1, x2, y2)
    p, q = _jitter([(x1, y1), (x2, y2)], r, WOBBLE * .7)
    p, q = _past(q, p, r.uniform(0, .3)), _past(p, q, r.uniform(.05, .35))
    return f'<path d="M{_pt(p)} {_bowed(p, q, r)}"/>'


def _shape(points: list[Point], closed: bool = False, fill: bool = False) -> str:
    """Straight-sided outline through `points`, corners kept, each side slightly bowed.
    A closed one runs on past where it started, so the ends overlap."""
    r = _rng("shape", points, closed)
    pts = _jitter(points, r)
    d = f"M{_pt(pts[0])}"
    for p, q in zip(pts, pts[1:]):
        d += " " + _bowed(p, q, r)
    if closed:
        end = (pts[0][0] + r.uniform(-.12, .12), pts[0][1] + r.uniform(-.12, .12))
        d += " " + _bowed(pts[-1], end, r)
        if not fill:
            d += " " + _bowed(end, _toward(end, pts[1], r.uniform(.35, .7)), r)
    extra = ' fill="currentColor"' if fill else ""
    return f'<path d="{d}"{extra}/>'


def _pinched(tips: list[Point], centre: Point, pull: float = .72) -> str:
    """A star with curved-in sides (a sparkle): each side bends towards `centre`."""
    r = _rng("pinched", tips, centre)
    pts = _jitter(tips, r)
    d = f"M{_pt(pts[0])}"
    for p, q in zip(pts, pts[1:] + pts[:1]):
        mx, my = (p[0] + q[0]) / 2, (p[1] + q[1]) / 2
        k = pull + r.uniform(-.05, .05)
        c = (mx + (centre[0] - mx) * k, my + (centre[1] - my) * k)
        d += f" Q{_pt(c)} {_pt(q)}"
    return f'<path d="{d}"/>'


def _toward(p: Point, q: Point, by: float) -> Point:
    dx, dy = q[0] - p[0], q[1] - p[1]
    length = math.hypot(dx, dy) or 1
    by = min(by, length * .5)
    return p[0] + dx / length * by, p[1] + dy / length * by


def _smooth(pts: list[Point], before: Point, after: Point) -> str:
    """A smooth line through pts (Catmull-Rom as cubic Beziers); `before` and `after`
    only steer its direction at the two ends."""
    full = [before, *pts, after]
    d = f"M{_pt(pts[0])}"
    for i in range(1, len(full) - 2):
        p0, p1, p2, p3 = full[i - 1], full[i], full[i + 1], full[i + 2]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d += f" C{_pt(c1)} {_pt(c2)} {_pt(p2)}"
    return d


def _curve(points: list[Point], closed: bool = False) -> str:
    """A freehand curve through `points`. A closed one overlaps itself where it meets."""
    r = _rng("curve", points, closed)
    pts = _jitter(points, r)
    if closed:
        last = (pts[0][0] + r.uniform(-.15, .15), pts[0][1] + r.uniform(-.15, .15))
        tail = _toward(last, pts[1], r.uniform(.5, 1))
        d = _smooth([*pts, last, tail], pts[-1], pts[1])
    else:
        start, end = _past(pts[1], pts[0], .25), _past(pts[-2], pts[-1], .25)
        d = _smooth(pts, _past(pts[1], pts[0], 1), _past(pts[-2], pts[-1], 1))
        d = d.replace(f"M{_pt(pts[0])}", f"M{_pt(start)} L{_pt(pts[0])}", 1)
        d += f" L{_pt(end)}"
    return f'<path d="{d}"/>'


def _ellipse(cx: float, cy: float, rx: float, ry: float, a0: float = 0, a1: float = 360,
             steps: int = 24) -> list[Point]:
    """Points along an ellipse from angle a0 to a1 (degrees, clockwise from 3 o'clock)."""
    return [(cx + rx * math.cos(math.radians(a0 + (a1 - a0) * i / steps)),
             cy + ry * math.sin(math.radians(a0 + (a1 - a0) * i / steps)))
            for i in range(steps + 1)]


def _ring(cx: float, cy: float, rx: float, ry: float | None = None) -> str:
    """A hand-drawn circle or ellipse: a little lopsided, its ends overlapping."""
    ry = rx if ry is None else ry
    r = _rng("ring", cx, cy, rx, ry)
    start = r.uniform(-150, -100)
    count = 7 if max(rx, ry) < 3 else 9
    pts = []
    for i in range(count):
        a = math.radians(start + 360 * i / count)
        k = 1 + r.uniform(-.035, .035)
        pts.append((cx + rx * k * math.cos(a), cy + ry * k * math.sin(a)))
    a = math.radians(start + r.uniform(20, 40))
    tail = (cx + rx * .98 * math.cos(a), cy + ry * .98 * math.sin(a))
    over = (pts[0][0] + r.uniform(-.1, .1), pts[0][1] + r.uniform(-.1, .1))
    return f'<path d="{_smooth([*pts, over, tail], pts[-1], pts[1])}"/>'


def _arc(cx: float, cy: float, rx: float, ry: float, a0: float, a1: float) -> str:
    """Part of a hand-drawn ellipse, from angle a0 to a1 (degrees)."""
    return _curve(_ellipse(cx, cy, rx, ry, a0, a1, max(3, round(abs(a1 - a0) / 40))))


def _dot(cx: float, cy: float, rx: float, ry: float | None = None) -> str:
    """A solid pencil dot, like the dog's eye."""
    ry = rx if ry is None else ry
    r = _rng("dot", cx, cy, rx, ry)
    return (f'<ellipse cx="{_n(cx)}" cy="{_n(cy)}" rx="{_n(rx * r.uniform(.92, 1.06))}" '
            f'ry="{_n(ry * r.uniform(.92, 1.06))}" transform="rotate({_n(r.uniform(-20, 20))} '
            f'{_n(cx)} {_n(cy)})" fill="currentColor" stroke="none"/>')


def _hatch(polygon: list[Point], gap: float = 1.6, angle: float = 45) -> str:
    """Pencil hatching inside `polygon`: parallel strokes `gap` apart, slanting up to the
    right at `angle` degrees, each stopping a little short of the edge, unevenly."""
    r = _rng("hatch", polygon, gap, angle)
    t = math.radians(angle)
    ux, uy = math.cos(t), -math.sin(t)  # along a stroke
    nx, ny = -uy, ux                    # across the strokes
    across = [x * nx + y * ny for x, y in polygon]
    d = ""
    offset = min(across) + gap * r.uniform(.35, .65)
    edges = list(zip(polygon, polygon[1:] + polygon[:1]))
    while offset < max(across):
        hits = []
        for (x1, y1), (x2, y2) in edges:
            s1, s2 = x1 * nx + y1 * ny - offset, x2 * nx + y2 * ny - offset
            if (s1 < 0) != (s2 < 0):
                k = s1 / (s1 - s2)
                hits.append((x1 + (x2 - x1) * k, y1 + (y2 - y1) * k))
        hits.sort(key=lambda p: p[0] * ux + p[1] * uy)
        for p, q in zip(hits[::2], hits[1::2]):
            length = math.hypot(q[0] - p[0], q[1] - p[1])
            a, b = r.uniform(.2, .5), r.uniform(.15, .45)
            if length - a - b < .5:
                continue
            p, q = _toward(p, q, a), _toward(q, p, b)
            d += f"M{_pt(p)} L{_pt(q)} "
        offset += gap * r.uniform(.85, 1.15)
    return f'<path d="{d.strip()}"/>' if d else ""


def _paw_prints(x: float, y: float, s: float) -> str:
    """A small solid paw print, for tracks."""
    return (_dot(x + 12 * s, y + 15.5 * s, 4 * s, 3.2 * s)
            + "".join(_dot(x + px * s, y + py * s, 1.8 * s, 2.1 * s)
                      for px, py in ((6.8, 10), (10, 6.8), (14, 6.8), (17.2, 10))))


# --- the icons ----------------------------------------------------------------------

SKETCHES: dict[str, str] = {
    # --- the bottom tab bar ---
    "binoculars": (  # Spotted!
        _ring(7.4, 15, 3.6) + _ring(16.6, 15, 3.6)
        + _shape([(4.4, 12.6), (6, 5.5), (9.2, 5.5), (10.6, 12)])
        + _shape([(13.4, 12), (14.8, 5.5), (18, 5.5), (19.6, 12.6)]) + _line(10.8, 13.4, 13.2, 13.4)
    ),
    "notebook": (  # Life list
        _shape([(6, 3.5), (17.2, 3.5), (18.5, 4.8), (18.5, 19.2), (17.2, 20.5), (6, 20.5)], closed=True)
        + _line(8.6, 3.6, 8.6, 20.4) + _shape([(11, 8.2), (12.3, 9.6), (15.4, 6.4)])
        + _line(11, 13, 16, 13) + _line(11, 16.5, 14.8, 16.5)
    ),
    "person": (  # Profile
        _ring(12, 8, 3.6) + _curve([(5, 20.2), (6.6, 16.2), (12, 14), (17.4, 16.2), (19, 20.2)])
    ),
    "people": (  # Social
        _ring(9, 8.6, 3) + _curve([(3.4, 19.6), (5, 15.8), (9, 14.4), (13, 15.8), (14.6, 19.6)])
        + _ring(16.6, 9.4, 2.4) + _curve([(15.4, 14.4), (18.6, 15.2), (20.7, 19)])
    ),
    "sliders": (  # Settings
        _line(4, 7, 20, 7) + _line(4, 12, 20, 12) + _line(4, 17, 20, 17)
        + _dot(9, 7, 2) + _dot(15.5, 12, 2) + _dot(7, 17, 2)
    ),
    # --- around the app ---
    "dog": _DOG,
    "camera": (
        _shape([(3.5, 8.5), (5, 7), (7.6, 7), (9.1, 4.9), (14.9, 4.9), (16.4, 7), (19, 7),
                (20.5, 8.5), (20.5, 17.7), (19, 19.2), (5, 19.2), (3.5, 17.7)], closed=True)
        + _ring(12, 12.8, 3.4) + _dot(17.6, 9.6, .7)
    ),
    "swap": (
        _arc(12, 12, 7, 7, 200, 318) + _shape([(17.8, 3.4), (17.8, 7.2), (14, 7.2)])
        + _arc(12, 12, 7, 7, 20, 138) + _shape([(6.2, 20.6), (6.2, 16.8), (10, 16.8)])
    ),
    "check": _shape([(5, 12.6), (9.2, 17), (19, 6.6)]),
    "magnifier": _ring(10.4, 10.4, 5.8) + _line(14.7, 14.7, 20.2, 20.2) + _line(15.6, 14.4, 19.8, 18.6),
    "sparkle": (
        _pinched([(12, 3.5), (18.5, 10), (12, 16.5), (5.5, 10)], (12, 10))
        + _line(18.5, 16.5, 18.5, 20.5) + _line(16.5, 18.5, 20.5, 18.5)
    ),
    "bulb": (
        _curve([(9, 15.6), (6.7, 13.2), (6, 10), (7.8, 5.8), (12, 4), (16.2, 5.8), (18, 10),
                (17.3, 13.2), (15, 15.6)])
        + _shape([(15, 15.4), (15, 17.8), (9, 17.8), (9, 15.4)]) + _line(9.6, 20.6, 14.4, 20.6)
    ),
    "heart": (
        _curve([(12, 19.6), (6.4, 15), (4.2, 10.8), (4.8, 7.2), (8.2, 5.4), (12, 7.6)])
        + _curve([(12, 7.6), (15.8, 5.4), (19.2, 7.2), (19.8, 10.8), (17.6, 15), (12, 19.6)])
    ),
    "pin": (
        _curve([(12, 21), (8.6, 16.6), (6.1, 12.6), (6, 9.6), (7.8, 5.6), (12, 3.8), (16.2, 5.6),
                (18, 9.6), (17.9, 12.6), (15.4, 16.6), (12, 21)])
        + _ring(12, 9.8, 2.2)
    ),
    "pencil": (
        _shape([(4.5, 19.5), (5.5, 14.9), (15.4, 5), (16.9, 4.4), (18.4, 5.6), (18.7, 7.1),
                (18.4, 8), (8.6, 18)], closed=True)
        + _line(13.4, 7, 16.4, 10) + _shape([(4.8, 17.6), (6.4, 19.2), (4.5, 19.5)], fill=True)
    ),
    "plus": _line(12, 5, 12, 19) + _line(5, 12, 19, 12),
    "bin": (
        _line(5, 7, 19, 7) + _shape([(9.6, 7), (9.6, 4.6), (14.4, 4.6), (14.4, 7)])
        + _shape([(6.6, 7), (7.6, 19.6), (16.4, 19.6), (17.4, 7)])
        + _line(10.2, 10.6, 10.2, 16.6) + _line(13.8, 10.6, 13.8, 16.6)
    ),
    "warning": (
        _shape([(12, 4), (21, 19.6), (3, 19.6)], closed=True) + _line(12, 10, 12, 14.4)
        + _dot(12, 17.1, 1)
    ),
    # --- badges (logic.BADGES) ---
    "paw": (
        _ring(12, 15.5, 4.3, 3.5) + _ring(6.8, 10, 1.8) + _ring(10, 6.8, 1.9)
        + _ring(14, 6.8, 1.9) + _ring(17.2, 10, 1.8)
    ),
    "bone": (
        _line(8.6, 7.3, 16.7, 15.4) + _line(7.3, 8.6, 15.4, 16.7)
        + _ring(5.6, 7.6, 1.9) + _ring(7.6, 5.6, 1.9) + _ring(16.4, 18.4, 1.9) + _ring(18.4, 16.4, 1.9)
    ),
    "lead": (
        _ring(6, 6.7, 2.4, 3.1) + _curve([(7.4, 9.4), (9.4, 12.2), (13, 13), (15.4, 15), (16.2, 16.6)])
        + _ring(17, 18.4, 1.8)
    ),
    "frisbee": (
        _ring(13, 14, 8, 3.6) + _ring(13, 13.4, 4.4, 1.7) + _line(2.6, 8, 7, 8) + _line(4.6, 5, 9, 5)
    ),
    "ball": (
        _ring(12, 12, 7.6) + _curve([(5.2, 8.6), (7.6, 10.6), (8.2, 13.6), (6.6, 17.2)])
        + _curve([(18.8, 15.4), (16.4, 13.4), (15.8, 10.4), (17.4, 6.8)])
    ),
    "sun": (
        _ring(12, 12, 4) + _line(12, 2.8, 12, 5.2) + _line(12, 18.8, 12, 21.2)
        + _line(2.8, 12, 5.2, 12) + _line(18.8, 12, 21.2, 12) + _line(5.5, 5.5, 7.2, 7.2)
        + _line(16.8, 16.8, 18.5, 18.5) + _line(5.5, 18.5, 7.2, 16.8) + _line(16.8, 7.2, 18.5, 5.5)
    ),
    "nose": (
        _curve([(5.6, 9.6), (7.4, 7.2), (12, 6.4), (16.6, 7.2), (18.4, 9.6), (16.8, 13.2),
                (12, 15.6), (7.2, 13.2)], closed=True)
        + _dot(10, 11.2, 1.25, .8) + _dot(14, 11.2, 1.25, .8)
        + _line(12, 15.6, 12, 18.4) + _curve([(8.8, 19.2), (12, 20.2), (15.2, 19.2)])
    ),
    "tracks": (_paw_prints(1, 11, .5) + _paw_prints(5.5, 5.5, .5) + _paw_prints(11, 9.5, .5)
               + _paw_prints(13.5, 1.5, .5)),
    "zoom": _line(2.6, 8, 9.6, 8) + _line(4.6, 12, 10.6, 12) + _line(2.6, 16, 9.6, 16) + _ring(16.6, 12, 3.8),
    "medal": (
        _shape([(7.6, 3), (10.6, 10.4)]) + _shape([(10.2, 3), (12.4, 8.2)])
        + _shape([(16.4, 3), (13.4, 10.4)]) + _ring(12, 15.2, 5) + _ring(12, 15.2, 2.4)
    ),
    "rosette": (
        _ring(12, 9, 5.4) + _ring(12, 9, 2.6)
        + _shape([(9.4, 13.8), (8, 21), (10.4, 19.6), (11.6, 14.4)])
        + _shape([(14.6, 13.8), (16, 21), (13.6, 19.6), (12.4, 14.4)])
    ),
    "moon": (
        _curve([(14.6, 4), (9.4, 4.7), (5.6, 8.4), (4.5, 13.2), (6.5, 17.8), (10.8, 20.3),
                (15.8, 20), (20.2, 16.6)])
        + _curve([(20.2, 16.6), (15.8, 16.9), (12.5, 14), (11.7, 9.4), (14.6, 4)])
        + _line(19, 3.6, 19, 7) + _line(17.3, 5.3, 20.7, 5.3)
    ),
    "compass": (
        _ring(12, 12, 8.4) + _shape([(12, 6.2), (14.3, 12), (12, 17.8), (9.7, 12)], closed=True)
        + _shape([(12, 6.4), (14.1, 12), (9.9, 12)], fill=True) + _dot(12, 12, .5)
    ),
    "kennel": (
        _shape([(3.6, 11.4), (12, 4.4), (20.4, 11.4)])
        + _shape([(5.6, 9.8), (5.6, 19.6), (18.4, 19.6), (18.4, 9.8)])
        + _curve([(9.4, 19.6), (9.4, 16), (10.3, 14.2), (12, 13.4), (13.7, 14.2), (14.6, 16), (14.6, 19.6)])
    ),
    "tail": (
        _curve([(4.4, 18.6), (8.8, 17.8), (11.8, 14.8), (13, 10.4), (15.2, 6.4), (19.6, 5)])
        + _curve([(17, 9.6), (18.6, 10.6), (19.3, 12.2)]) + _curve([(20, 8), (21, 9), (21.4, 10.2)])
    ),
    "star": _shape([(12, 3.4), (14.6, 8.9), (20.6, 9.7), (16.2, 13.8), (17.3, 19.7), (12, 16.8),
                    (6.7, 19.7), (7.8, 13.8), (3.4, 9.7), (9.4, 8.9)], closed=True),
    "target": (
        _ring(11, 13, 7.6) + _ring(11, 13, 4.4) + _dot(11, 13, 1.5)
        + _line(12.4, 11.6, 20.4, 3.6) + _shape([(17.2, 3.4), (20.6, 3.4), (20.6, 6.8)])
    ),
    "dogstar": (
        _shape([(4.6, 17), (9.6, 9.6), (15, 12.6), (19.4, 4.8)])
        + _dot(4.6, 17, 1.6) + _dot(9.6, 9.6, 1.6) + _dot(15, 12.6, 1.6) + _dot(19.4, 4.8, 1.6)
        + _line(15, 17, 17, 19.4)
    ),
    "first": (
        _line(8.4, 3, 11.2, 9.4) + _line(15.6, 3, 12.8, 9.4) + _ring(12, 14.8, 5.6)
        + _shape([(10.6, 13.6), (12.4, 12), (12.4, 17.8)])
    ),
    "trophy": (
        _line(7.2, 4, 16.8, 4)
        + _curve([(7.4, 4.2), (7.4, 8.6), (8.8, 11.8), (12, 13.2), (15.2, 11.8), (16.6, 8.6), (16.6, 4.2)])
        + _curve([(7.4, 6), (5.2, 6.2), (5, 8.4), (7.8, 10.2)])
        + _curve([(16.6, 6), (18.8, 6.2), (19, 8.4), (16.2, 10.2)])
        + _line(12, 13.2, 12, 16.6) + _shape([(9.4, 16.6), (14.6, 16.6), (14.6, 20), (9.4, 20)], closed=True)
        + _line(8, 20.2, 16, 20.2)
    ),
    "suitcase": (
        _shape([(4, 8.4), (20, 8.4), (20, 18.8), (18.6, 20.2), (5.4, 20.2), (4, 18.8)], closed=True)
        + _shape([(9, 8.4), (9, 5.4), (15, 5.4), (15, 8.4)]) + _line(8, 8.6, 8, 20) + _line(16, 8.6, 16, 20)
    ),
    "map": (
        _shape([(3.6, 6.4), (9, 4.2), (15, 6.6), (20.4, 4.4), (20.4, 17.6), (15, 19.8), (9, 17.4),
                (3.6, 19.6)], closed=True)
        + _line(9, 4.4, 9, 17.4) + _line(15, 6.8, 15, 19.8)
    ),
    "telescope": (
        _shape([(4, 13.6), (16.8, 6.4), (18.6, 9.6), (5.8, 16.8)], closed=True)
        + _line(18.6, 9.6, 20.6, 8.5) + _line(16.6, 6.6, 18.6, 5.5)
        + _line(11, 13.4, 8.4, 20.4) + _line(11, 13.4, 14.4, 20.4)
    ),
    "gem": (
        _shape([(7, 4.6), (17, 4.6), (20.4, 9.2), (12, 20), (3.6, 9.2)], closed=True)
        + _line(3.6, 9.2, 20.4, 9.2) + _shape([(9.6, 4.8), (8.4, 9.2), (12, 20)])
        + _shape([(14.4, 4.8), (15.6, 9.2), (12, 20)])
    ),
    "crown": (
        _shape([(3.6, 17.6), (2.8, 7.6), (8, 11.6), (12, 5), (16, 11.6), (21.2, 7.6), (20.4, 17.6)],
               closed=True)
        + _line(4, 20.2, 20, 20.2) + _dot(2.8, 6.4, .9) + _dot(12, 3.8, .9) + _dot(21.2, 6.4, .9)
    ),
}

# Pencil shading, drawn once (not gone over twice) with a thinner, lighter line.
SHADING: dict[str, str] = {
    "binoculars": (_hatch([(5.2, 11.2), (6.6, 6.3), (8.7, 6.3), (9.9, 11.2)])
                   + _hatch([(14.1, 11.2), (15.3, 6.3), (17.4, 6.3), (18.8, 11.2)])),
    "notebook": _hatch([(6.2, 3.8), (8.4, 3.8), (8.4, 20.2), (6.2, 20.2)], gap=1.44),
    "person": _hatch([(6.2, 19.8), (7.6, 16.8), (12, 14.9), (16.4, 16.8), (17.8, 19.8)]),
    "people": _hatch(_ellipse(16.6, 9.4, 1.9, 1.9), gap=1.32) + _hatch([(4.6, 19.2), (5.8, 16.4), (9, 15.3), (12.2, 16.4), (13.4, 19.2)]),
    "camera": _hatch(_ellipse(12, 12.8, 2.6, 2.6, -60, 150), gap=1.32),
    "magnifier": _hatch(_ellipse(10.4, 10.4, 4.8, 4.8, -40, 140)),
    "sparkle": _hatch([(12, 6.6), (15.2, 10), (12, 13.4), (8.8, 10)], gap=1.32),
    "bulb": _hatch(_ellipse(12, 10, 5.1, 5.1, -70, 50)),
    "heart": _hatch([(12.6, 9.2), (15.6, 6.6), (18.5, 7.8), (18.9, 11), (16.8, 14.4), (12.8, 17.8)]),
    "pin": _hatch([(14.4, 5.4), (16.9, 7.6), (17.2, 11.4), (15, 15.6), (12.6, 19), (14.2, 12.6), (14.6, 9.8)]),
    "pencil": _hatch([(6.4, 15.2), (14.6, 7), (16.4, 8.8), (8.2, 17)], gap=1.5, angle=-45),
    "warning": _hatch([(12.8, 6.6), (19.4, 18.6), (14.6, 18.6)], gap=1.44),
    "paw": _hatch(_ellipse(12, 15.5, 3.4, 2.6)),
    "bone": _hatch([(8.6, 7.9), (16.1, 15.4), (15.4, 16.1), (7.9, 8.6)], gap=1.08, angle=-45),
    "frisbee": _hatch(_ellipse(13, 13.4, 3.7, 1.25), gap=1.2),
    "ball": _hatch([(17.6, 7.2), (19, 9), (19.4, 12.2), (18.6, 14.8), (16.6, 13.2), (16.1, 10.4)], gap=1.32),
    "sun": _hatch(_ellipse(12, 12, 3.1, 3.1), gap=1.44),
    "nose": _hatch([(6.6, 9.4), (8, 7.8), (12, 7.2), (16, 7.8), (17.4, 9.4), (16, 12.4), (12, 14.6), (8, 12.4)], gap=1.44),
    "zoom": _hatch(_ellipse(16.6, 12, 2.9, 2.9, -60, 150), gap=1.32),
    "medal": _hatch(_ellipse(12, 15.2, 1.7, 1.7), gap=1.08) + _hatch([(8.4, 3.6), (10, 3.6), (11.6, 7.4), (10.8, 8.8)], gap=1.2),
    "rosette": (_hatch([(9.7, 14.6), (8.6, 20), (10.2, 19.1), (11.1, 15)], gap=1.2)
                + _hatch([(14.3, 14.6), (15.4, 20), (13.8, 19.1), (12.9, 15)], gap=1.2)),
    "moon": _hatch([(13.4, 5.2), (11.4, 9.6), (12.2, 14.2), (15.6, 17.4), (19.4, 17.4), (15.8, 19.4), (10.8, 19.6), (6.8, 17.2), (5.2, 13.2), (6.2, 8.8), (9.6, 5.4)]),
    "compass": _hatch([(12, 13), (13.4, 12.6), (12, 16.6), (10.6, 12.6)], gap=0.96, angle=-45),
    "kennel": _hatch([(10, 19.4), (10, 16.2), (10.8, 14.8), (12, 14.2), (13.2, 14.8), (14, 16.2), (14, 19.4)], gap=1.14),
    "star": _hatch([(12, 5.6), (13.9, 9.7), (18.6, 10.4), (15.3, 13.5), (16.1, 18.1), (12, 15.8)], gap=1.44),
    "target": _hatch(_ellipse(11, 13, 3.6, 3.6), gap=1.44),
    "first": _hatch(_ellipse(12, 14.8, 4.8, 4.8, -20, 110)),
    "trophy": _hatch([(12.4, 4.7), (15.9, 4.7), (15.9, 8.6), (14.7, 11.2), (12.4, 12.4)], gap=1.38),
    "suitcase": _hatch([(16.5, 8.9), (19.5, 8.9), (19.5, 18.6), (18.4, 19.7), (16.5, 19.7)], gap=1.38),
    "map": _hatch([(9.5, 5), (14.5, 7), (14.5, 19.1), (9.5, 17.1)], gap=1.5),
    "telescope": _hatch([(4.8, 13.8), (16.5, 7.2), (17.8, 9.4), (6.1, 16)], gap=1.32, angle=-45),
    "gem": _hatch([(4.6, 9.8), (8, 9.8), (11, 18.4)], gap=1.2),
    "crown": _hatch([(3.4, 15), (20.6, 15), (20.4, 17.2), (3.6, 17.2)], gap=1.2),
}


# Crisp vectors, no blur filters, so they stay sharp at any size and screen density.
# The hand-drawn look comes from going over each line twice, like a pencil: a firm line,
# then a lighter one a fraction off and turned a hair, so the ends and corners don't
# quite meet (the dog's own stroke widths win over these, so it keeps its bold look).
# The hatching goes on once, thin and light.
def _strokes(name: str) -> str:
    """The icon drawn twice (once firmly, once lighter and a fraction off), then shaded."""
    body = SKETCHES[name]
    shade = SHADING.get(name, "")
    return (f'<g stroke-width="1.25">{body}</g>'
            f'<g stroke-width="1.05" opacity=".42" '
            f'transform="translate(.5 -.4) rotate(-1.5 12 12)">{body}</g>'
            + (f'<g stroke-width=".5" opacity=".55">{shade}</g>' if shade else ""))


def svg(name: str, css: str = "sketch") -> str:
    """An inline sketch for the app's own HTML. It takes the colour of the text around it
    and is 1.2em square unless the class `css` says otherwise (see MOBILE_CSS)."""
    return (f'<svg class="{css}" viewBox="0 0 24 24" aria-hidden="true" fill="none" '
            f'stroke="currentColor" stroke-linecap="round" stroke-linejoin="round">'
            f"{_strokes(name)}</svg>")


def data_uri(name: str) -> str:
    """A standalone black copy as a base64 data URI, for CSS `mask-image` (base64, so the
    stylesheet has no "<" in it: st.html drops a stylesheet that does). It says it's 96px
    so browsers never draw it small and stretch it up."""
    picture = (f'<svg xmlns="http://www.w3.org/2000/svg" width="96" height="96" '
               f'viewBox="0 0 24 24" fill="none" '
               f'stroke="black" stroke-linecap="round" stroke-linejoin="round" color="black">'
               f"{_strokes(name)}</svg>")
    return "data:image/svg+xml;base64," + base64.b64encode(picture.encode()).decode()
