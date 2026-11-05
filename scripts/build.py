"""Generate the profile README artwork (light + dark SVGs) into ../assets.

Flat and free-form: type, space and one accent. No cards, borders, gradients or shadows.
Text is converted to outlines because GitHub shows SVGs as <img>, which cannot load fonts.
Links inside an SVG never work there, so every clickable thing is its own image.
CSS animation inside the SVG does play, and stops for visitors who prefer reduced motion.

    pip install fonttools brotli
    python scripts/build.py
"""

from __future__ import annotations

import base64
import hashlib
import math
import random
import re
from pathlib import Path
from xml.sax.saxutils import escape

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
OUT = ROOT.parent / "assets"

THEMES = {
    "light": {"ink": "#0A0A0A", "muted": "#737373", "faint": "#D4D4D4", "accent": "#6F49B1", "bg": "#FFFFFF"},
    "dark": {"ink": "#FAFAFA", "muted": "#A1A1A1", "faint": "#3A3A3A", "accent": "#D6C9F9", "bg": "#0D1117"},
}

# ---------------------------------------------------------------- content

HEADLINE = [("I connect people,", "ink"), ("processes and", "ink"), ("systems.", "accent")]
SUBLINE = "IT consultant and developer, growing into solution architecture."

INTERESTS = [
    "Human-agent interaction",
    "Application landscapes",
    "Enterprise architecture",
    "AI & machine learning",
    "Reinforcement learning",
    "Embedded systems",
    "Sociology",
    "Change management",
]

PROJECTS = [
    {"slug": "mtgf", "line": "Card search for people and AI agents"},
    {"slug": "ordo", "line": "A terminal where AI agents team up"},
    {"slug": "piikey", "line": "Keeps your data out of AI chats"},
    {"slug": "pokeum", "line": "Card recognition, fully self-hosted"},
]

LINKS = [("wena", "wena.one"), ("linkedin", "LinkedIn")]

# ---------------------------------------------------------------- type

_FONTS = {"sans": SRC / "space-grotesk-latin-wght-normal.woff2", "hand": SRC / "caveat.ttf"}
_fonts: dict[tuple[str, int], TTFont] = {}


def _font(weight: int, family: str = "sans") -> TTFont:
    if (family, weight) not in _fonts:
        _fonts[family, weight] = instantiateVariableFont(TTFont(_FONTS[family]), {"wght": weight})
    return _fonts[family, weight]


def text_width(s: str, size: float, weight: int = 400, tracking: float = 0, family: str = "sans") -> float:
    f = _font(weight, family)
    cmap, hmtx, upm = f.getBestCmap(), f["hmtx"], f["head"].unitsPerEm
    return sum(hmtx[cmap[ord(c)]][0] for c in s) * size / upm + tracking * max(len(s) - 1, 0)


def text(s: str, x: float, y: float, size: float, weight: int, fill: str, tracking: float = 0, family: str = "sans") -> str:
    """Outlined text as one <path>; y is the baseline."""
    f = _font(weight, family)
    cmap, hmtx, upm = f.getBestCmap(), f["hmtx"], f["head"].unitsPerEm
    gs = f.getGlyphSet()
    scale = size / upm
    pen = SVGPathPen(gs, ntos=lambda v: f"{v:.1f}".rstrip("0").rstrip("."))
    for ch in s:
        g = cmap[ord(ch)]
        gs[g].draw(TransformPen(pen, (scale, 0, 0, -scale, x, y)))
        x += hmtx[g][0] * scale + tracking
    return f'<path fill="{fill}" d="{pen.getCommands()}"/>'


def wrap(s: str, size: float, weight: int, max_w: float) -> list[str]:
    lines, cur = [], ""
    for word in s.split():
        trial = f"{cur} {word}".strip()
        if cur and text_width(trial, size, weight) > max_w:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    return lines + [cur]


def fits(width: float, limit: float, what: str) -> None:
    assert width <= limit, f"{what} overflows: {width:.0f} > {limit}"


def svg(w: float, h: float, body: str, title: str, css: str = "") -> str:
    style = f"<style>{css}</style>" if css else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:.0f} {h:.0f}" width="{w:.0f}" height="{h:.0f}" role="img">'
        f"<title>{escape(title)}</title>{style}{body}</svg>\n"
    )


class Timeline:
    """One looping sequence. Every element gets its own keyframes on the same clock, so the
    loop stays in sync. Elements appear at a given %, hold, and fade out either at their own
    `until` % or together at the end of the loop."""

    LOOP, HOLD, GONE = 16, 88, 95  # seconds per loop; % where the final fade starts and ends

    def __init__(self) -> None:
        self.css: list[str] = []

    def rule(self, frames: str) -> str:
        k = f"k{len(self.css)}"
        self.css.append(f"@keyframes {k}{{{frames}}}.{k}{{animation:{k} {self.LOOP}s linear infinite}}")
        return k

    def _out(self, until: float | None) -> tuple[float, float]:
        return (until, until + 4) if until else (self.HOLD, self.GONE)

    def appear(self, at: float, body: str, until: float | None = None) -> str:
        """Fade and grow in at `at` %."""
        hold, gone = self._out(until)
        k = self.rule(
            f"0%,{at}%{{opacity:0;transform:scale(.6)}}"
            f"{at + 4}%,{hold}%{{opacity:1;transform:none}}"
            f"{gone}%,100%{{opacity:0;transform:none}}"
        )
        return f'<g class="{k}" style="transform-box:fill-box;transform-origin:center">{body}</g>'

    def fade(self, at: float, body: str, until: float | None = None) -> str:
        """Fade in at `at` % (quick, no movement: used for handwriting and diagram lines)."""
        hold, gone = self._out(until)
        k = self.rule(f"0%,{at:.2f}%{{opacity:0}}{at + .6:.2f}%,{hold}%{{opacity:1}}{gone}%,100%{{opacity:0}}")
        return f'<g class="{k}">{body}</g>'

    def draw(self, start: float, end: float, d: str, stroke: str, width: float = 2, until: float | None = None) -> str:
        """Stroke a path from `start` % to `end` %."""
        hold, gone = self._out(until)
        k = self.rule(
            f"0%,{start}%{{stroke-dashoffset:100;opacity:1}}"
            f"{end}%,{hold}%{{stroke-dashoffset:0;opacity:1}}"
            f"{gone}%,100%{{stroke-dashoffset:0;opacity:0}}"
        )
        return (
            f'<path class="{k}" pathLength="100" stroke-dasharray="100" d="{d}" fill="none" '
            f'stroke="{stroke}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"/>'
        )

    def style(self, reduced: str = "") -> str:
        rise = (
            ".rise{opacity:0;animation:rise .8s cubic-bezier(.2,.7,.2,1) forwards;animation-delay:var(--o,0s)}"
            "@keyframes rise{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:none}}"
        )
        # reduced motion: no animation; `reduced` picks which still frame is shown
        still = f"@media (prefers-reduced-motion:reduce){{*{{animation:none!important;opacity:1!important}}{reduced}}}"
        return rise + "".join(self.css) + still


# ---------------------------------------------------------------- marks

WENA_D = re.search(r'\sd="([^"]+)"', (SRC / "wena-mark.svg").read_text()).group(1)
POKEUM = (
    '<path fill="{c}" fill-rule="evenodd" d="M52 108A76 76 0 1 1 96 176.93V202A22 22 0 0 1 52 202Z'
    "M128 76A32 32 0 1 0 128 140A32 32 0 1 0 128 76ZM128 95A13 13 0 1 1 128 121A13 13 0 1 1 128 95Z\"/>"
)
PIIKEY = (
    '<g fill="{c}" transform="translate(-13 0)"><path fill-rule="evenodd" d="M146 40a52 52 0 1 0 0 104'
    'a52 52 0 1 0 0-104zM146 68a24 24 0 1 1 0 48a24 24 0 1 1 0-48z"/>'
    '<rect x="84" y="40" width="28" height="176" rx="14"/><rect x="100" y="152" width="44" height="20" rx="8"/>'
    '<rect x="100" y="186" width="30" height="20" rx="8"/></g>'
)


def wena_mark(x: float, y: float, h: float, fill: str) -> str:
    return f'<svg x="{x:.1f}" y="{y:.1f}" width="{h * 694 / 436:.1f}" height="{h}" viewBox="0 0 694 436"><path fill="{fill}" d="{WENA_D}"/></svg>'


def mark(slug: str, x: float, y: float, size: float, fill: str) -> str:
    if slug in ("pokeum", "piikey"):
        inner = (POKEUM if slug == "pokeum" else PIIKEY).format(c=fill)
        return f'<svg x="{x}" y="{y}" width="{size}" height="{size}" viewBox="0 0 256 256">{inner}</svg>'
    # one-colour PNG marks (black on transparent), recoloured to `fill` with alpha kept
    data = base64.b64encode((SRC / f"{slug}-mark.png").read_bytes()).decode()
    r, g, b = (int(fill[i:i + 2], 16) / 255 for i in (1, 3, 5))
    fid = f"ink-{slug}"
    return (
        f'<filter id="{fid}"><feColorMatrix type="matrix" values="0 0 0 0 {r:.3f}  0 0 0 0 {g:.3f}  0 0 0 0 {b:.3f}  0 0 0 1 0"/></filter>'
        f'<image x="{x}" y="{y}" width="{size}" height="{size}" filter="url(#{fid})" href="data:image/png;base64,{data}"/>'
    )


def arrow(x: float, y: float, s: float, stroke: str) -> str:
    """Up-right arrow with (x, y) the bottom-left corner of an s by s box."""
    return (
        f'<path fill="none" stroke="{stroke}" stroke-width="{s * .16:.1f}" stroke-linecap="round" stroke-linejoin="round" '
        f'd="M{x} {y}L{x + s} {y - s}M{x + s * .3:.1f} {y - s}H{x + s}V{y - s * .3:.1f}"/>'
    )


# ---------------------------------------------------------------- hero (split: words left, animation right)


def smooth(pts: list[tuple[float, float]]) -> str:
    """Catmull-Rom curve through points, as cubic Beziers."""
    d = f"M{pts[0][0]:.1f} {pts[0][1]:.1f}"
    for i in range(len(pts) - 1):
        p0, p1, p2 = pts[max(i - 1, 0)], pts[i], pts[i + 1]
        p3 = pts[min(i + 2, len(pts) - 1)]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d += f"C{c1[0]:.1f} {c1[1]:.1f} {c2[0]:.1f} {c2[1]:.1f} {p2[0]:.1f} {p2[1]:.1f}"
    return d


class Pen:
    """Hand-drawn strokes: every line wobbles a little, like a pen on a napkin."""

    def __init__(self, seed: int) -> None:
        self.rng = random.Random(seed)

    def j(self, v: float = 2.5) -> float:
        return self.rng.uniform(-v, v)

    def line(self, pts: list[tuple[float, float]], step: float = 28) -> str:
        out = []
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            n = max(1, int(math.hypot(x2 - x1, y2 - y1) / step))
            out += [(x1 + (x2 - x1) * i / n + self.j(), y1 + (y2 - y1) * i / n + self.j()) for i in range(n)]
        out.append((pts[-1][0] + self.j(), pts[-1][1] + self.j()))
        return smooth(out)

    def rect(self, x: float, y: float, w: float, h: float) -> str:
        # one pen stroke: starts a little in and overshoots the first corner on the way back
        return self.line([(x + 6, y + self.j(4)), (x + w, y), (x + w, y + h), (x, y + h), (x, y), (x + 22, y + self.j(4))])

    def circle(self, cx: float, cy: float, r: float) -> str:
        pts = []
        for i in range(17):
            a = -1.9 + i * (2 * math.pi * 1.08) / 16
            rr = r * (1 + self.rng.uniform(-.07, .07))
            pts.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr * .9))
        return smooth(pts)

    def scrawl(self, x: float, y: float, w: float) -> str:
        """Handwriting-like squiggle standing in for a note."""
        pts, i = [], 0
        while i * 7 <= w:
            pts.append((x + i * 7 + self.j(1.5), y + (5 if i % 2 else -5) * self.rng.uniform(.4, 1.1)))
            i += 1
        return smooth(pts)

    def arrow(self, a: tuple[float, float], b: tuple[float, float]) -> tuple[str, str]:
        mx, my = (a[0] + b[0]) / 2 + self.j(18), (a[1] + b[1]) / 2 + self.j(18)
        shaft = self.line([a, (mx, my), b], step=40)
        ang = math.atan2(b[1] - my, b[0] - mx)
        h = [(b[0] - 14 * math.cos(ang + s), b[1] - 14 * math.sin(ang + s)) for s in (.5, -.5)]
        head = f"M{h[0][0]:.1f} {h[0][1]:.1f}L{b[0]:.1f} {b[1]:.1f}L{h[1][0]:.1f} {h[1][1]:.1f}"
        return shaft, head

    def blob(self, cx: float, cy: float, rx: float, ry: float, turns: float = 1.15) -> str:
        """A loose, lopsided loop that doesn't quite close: thinking-in-circles."""
        pts, n = [], 20
        for i in range(n + 1):
            a = -2.2 + i * 2 * math.pi * turns / n
            k = 1 + self.rng.uniform(-.16, .16)
            pts.append((cx + math.cos(a) * rx * k, cy + math.sin(a) * ry * k))
        return smooth(pts)

    def curve(self, pts: list[tuple[float, float]]) -> tuple[str, str]:
        """A meandering arrow through rough waypoints."""
        pts = [(x + self.j(6), y + self.j(6)) for x, y in pts]
        (px, py), (bx, by) = pts[-2], pts[-1]
        ang = math.atan2(by - py, bx - px)
        h = [(bx - 14 * math.cos(ang + s), by - 14 * math.sin(ang + s)) for s in (.5, -.5)]
        return smooth(pts), f"M{h[0][0]:.1f} {h[0][1]:.1f}L{bx:.1f} {by:.1f}L{h[1][0]:.1f} {h[1][1]:.1f}"

    def star(self, cx: float, cy: float, r: float) -> str:
        pts = []
        for i in range(11):
            a = -math.pi / 2 + i * 4 * math.pi / 5
            pts.append((cx + math.cos(a) * r + self.j(2), cy + math.sin(a) * r + self.j(2)))
        return "M" + "L".join(f"{x:.1f} {y:.1f}" for x, y in pts)

    def spiral(self, cx: float, cy: float, r: float) -> str:
        pts = [(cx + math.cos(a) * r * a / 14 + self.j(1), cy + math.sin(a) * r * a / 14 + self.j(1)) for a in [i * .45 for i in range(32)]]
        return smooth(pts)


# the designed landscape the sketch becomes: a layered ArchiMate view.
# name: (kind, centre x, centre y, width)
LAYERS = [("BUSINESS", 90), ("APPLICATION", 245), ("TECHNOLOGY", 405)]
ELEMENTS = {
    "Customer": ("actor", 690, 90, 112), "Support": ("process", 830, 90, 112),
    "Sales": ("process", 970, 90, 112), "Invoicing": ("process", 1110, 90, 112),
    "Portal": ("component", 690, 200, 112), "AI agent": ("component", 830, 200, 112),
    "CRM": ("component", 970, 200, 112), "ERP": ("component", 1110, 200, 112),
    "Identity": ("component", 690, 290, 112), "Data": ("component", 830, 290, 112),
    "Analytics": ("component", 970, 290, 112), "Billing": ("component", 1110, 290, 112),
    "Cloud platform": ("node", 760, 405, 252), "Data platform": ("node", 1040, 405, 252),
}
RELATIONS = [  # (kind, from, to)
    ("serving", "Support", "Customer"), ("triggering", "Sales", "Invoicing"),
    ("serving", "Portal", "Customer"), ("serving", "AI agent", "Support"),
    ("serving", "CRM", "Sales"), ("serving", "ERP", "Invoicing"),
    ("flow", "Portal", "AI agent"), ("flow", "AI agent", "CRM"), ("flow", "CRM", "ERP"),
    ("serving", "Identity", "Portal"), ("serving", "Data", "AI agent"),
    ("serving", "Analytics", "CRM"), ("flow", "ERP", "Billing"), ("flow", "Data", "Analytics"),
    ("serving", "Cloud platform", "Identity"), ("serving", "Cloud platform", "Data"),
    ("serving", "Data platform", "Analytics"), ("serving", "Data platform", "Billing"),
]
HIGHLIGHT = "AI agent"  # drawn in the accent colour, with its relations
EH, NH = 46, 50  # element / node height


def _height(kind: str) -> float:
    return NH if kind == "node" else EH


def relation(kind: str, x1: float, y1: float, x2: float, y2: float, ink: str, bg: str) -> str:
    """ArchiMate relation between two points. serving: solid + open head; flow: dashed + filled
    head; triggering: solid + filled head."""
    ang = math.atan2(y2 - y1, x2 - x1)
    ux, uy = math.cos(ang), math.sin(ang)
    back = (x2 - 10 * ux, y2 - 10 * uy)
    wing = [(back[0] - 5.5 * uy * s, back[1] + 5.5 * ux * s) for s in (1, -1)]
    filled = kind != "serving"
    end = back if filled else (x2, y2)
    dash = ' stroke-dasharray="5 4"' if kind == "flow" else ""
    out = f'<path d="M{x1:.1f} {y1:.1f}L{end[0]:.1f} {end[1]:.1f}" stroke="{ink}" stroke-width="1.6"{dash}/>'
    wings = f"M{wing[0][0]:.1f} {wing[0][1]:.1f}L{x2:.1f} {y2:.1f}L{wing[1][0]:.1f} {wing[1][1]:.1f}"
    if filled:
        return out + f'<path fill="{ink}" d="{wings}Z"/>'
    return out + f'<path fill="none" stroke="{ink}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" d="{wings}"/>'


def connect(kind: str, src: str, dst: str, ink: str, bg: str) -> str:
    sk, sx, sy, sw = ELEMENTS[src]
    dk, dx, dy, dw = ELEMENTS[dst]
    if abs(sy - dy) < 1:  # same row: side to side
        s = 1 if dx > sx else -1
        return relation(kind, sx + s * sw / 2, sy, dx - s * dw / 2, dy, ink, bg)
    x = dx if sk == "node" else sx  # nodes span several components: drop straight onto the target
    s = 1 if dy > sy else -1
    return relation(kind, x, sy + s * _height(sk) / 2, x, dy - s * _height(dk) / 2, ink, bg)


def element(name: str, ink: str, bg: str) -> str:
    kind, cx, cy, w = ELEMENTS[name]
    h = _height(kind)
    x, y = cx - w / 2, cy - h / 2
    ix, iy = x + w - 24, y + 7
    if kind == "node":
        d = 7
        shape = (
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{bg}" stroke="{ink}" stroke-width="1.6"/>'
            f'<path fill="none" stroke="{ink}" stroke-width="1.6" stroke-linejoin="round" d="M{x} {y}l{d} {-d}h{w}v{h}l{-d} {d}M{x + w} {y}l{d} {-d}"/>'
        )
        icon = f'<rect x="{ix}" y="{iy + 3}" width="12" height="10" fill="none"/><path fill="none" d="M{ix} {iy + 3}l3 -3h12v10l-3 3M{ix + 12} {iy + 3}l3 -3"/>'
    else:
        rx = 12 if kind == "process" else 2
        shape = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{bg}" stroke="{ink}" stroke-width="1.6"/>'
        if kind == "component":
            icon = (
                f'<rect x="{ix + 4}" y="{iy}" width="12" height="14" fill="none"/>'
                f'<rect x="{ix}" y="{iy + 2.5}" width="7" height="3.5" fill="{bg}"/><rect x="{ix}" y="{iy + 8}" width="7" height="3.5" fill="{bg}"/>'
            )
        elif kind == "process":
            icon = f'<path fill="none" d="M{ix - 2} {iy + 4}h10v-4l7 7l-7 7v-4h-10z"/>'
        else:  # actor: stick figure
            icon = (
                f'<circle cx="{ix + 8}" cy="{iy + 3}" r="3" fill="none"/>'
                f'<path fill="none" d="M{ix + 8} {iy + 6}v6M{ix + 3} {iy + 8.5}h10M{ix + 8} {iy + 12}l-4 5M{ix + 8} {iy + 12}l4 5"/>'
            )
    lw = text_width(name, 16, 500)
    fits(lw, w - 26, name)
    return (
        shape
        + f'<g stroke="{ink}" stroke-width="1.3" stroke-linejoin="round" stroke-linecap="round">{icon}</g>'
        + text(name, cx - lw / 2, cy + 12, 16, 500, ink)
    )


def hero(t: dict) -> str:
    W, H = 1200, 520
    ink, muted, faint, accent, bg = t["ink"], t["muted"], t["faint"], t["accent"], t["bg"]
    tl = Timeline()
    b = []

    # left: words
    for i, (s, tone) in enumerate(HEADLINE):
        fits(text_width(s, 64, 700, -2), 560, s)
        b.append(f'<g class="rise" style="--o:{.2 + i * .1:.1f}s">' + text(s, -3, 184 + i * 72, 64, 700, t[tone], tracking=-2) + "</g>")
    b.append(
        '<g class="rise" style="--o:.6s">'
        + "".join(text(s, 0, 390 + i * 36, 24, 400, muted) for i, s in enumerate(wrap(SUBLINE, 24, 400, 500)))
        + "</g>"
    )

    # frame 1: unstructured thinking on a napkin. Strokes and handwriting are queued and
    # timed once we know how long the whole sketch takes.
    pen, queue, at = Pen(23), [], 2.0

    def stroke(d: str, dur: float, w: float = 2.2, rot: tuple[float, float, float] | None = None) -> None:
        nonlocal at
        queue.append(("draw", at, at + dur, d, w, rot))
        at += dur * .75

    def write(s: str, x: float, y: float, size: float, weight: int = 500, rot: float = 0) -> None:
        nonlocal at
        chars, cx = [], x
        for ch in s:
            if ch != " ":
                chars.append((at, text(ch, cx, y, size, weight, ink, family="hand")))
                at += .16
            cx += text_width(ch, size, weight, family="hand")
        queue.append(("write", rot, x, y, chars))
        at += .3

    def sticky(x: float, y: float, w: float, h: float, rot: float, lines: list[str]) -> None:
        cx, cy = x + w / 2, y + h / 2
        tape = f'<rect x="{cx - 30}" y="{y - 9}" width="60" height="18" fill="{muted}" fill-opacity=".3"/>'
        queue.append(("raw", at, f'<g transform="rotate({rot} {cx} {cy})">{tape}</g>'))
        stroke(pen.rect(x, y, w, h), 1.2, 1.8, rot=(rot, cx, cy))
        for i, s in enumerate(lines):
            write(s, x + 14, y + 40 + i * 32, 27, 600, rot=rot)

    stroke(pen.blob(712, 92, 82, 52), 2)
    write("customers??", 652, 100, 30, 600, rot=-7)
    write("sync nightly", 806, 70, 24)
    stroke(pen.line([(802, 62), (918, 58)], step=30), .5, 2)
    write("realtime!", 830, 104, 27, 600, rot=3)
    sticky(1010, 40, 150, 100, -6, ["AI agent", "here??"])
    write("portal / app / both?", 646, 232, 26, rot=4)
    stroke(pen.blob(818, 236, 40, 24, 1.05), 1, 1.8)
    a, h = pen.curve([(780, 110), (880, 150), (960, 200), (1040, 205)])
    stroke(a, 1.2)
    stroke(h, .3)
    write("CRM", 1052, 214, 34, 700)
    stroke(pen.line([(1044, 180), (1124, 176), (1128, 228)], step=20), .6, 1.8)
    stroke(pen.star(982, 300, 16), .7, 1.8)
    write("??", 1148, 300, 40, 700, rot=10)
    sticky(652, 330, 160, 104, 7, ["invoices", "manual :("])
    a, h = pen.curve([(760, 262), (820, 320), (880, 360)])
    stroke(a, .9)
    stroke(h, .3)
    write("who owns the data?", 862, 408, 27, 600, rot=-3)
    stroke(pen.line([(860, 420), (1060, 410)], step=40), .5, 1.8)
    stroke(pen.line([(870, 430), (1040, 422)], step=40), .5, 1.8)
    stroke(pen.spiral(1150, 456, 22), .8, 1.8)
    end = round(at + 2)
    assert end <= 46, f"sketch runs too long: {end}%"

    sk = []
    for item in queue:
        if item[0] == "draw":
            _, s, e, d, w, rot = item
            path = tl.draw(s, e, d, ink, w, until=end)
            sk.append(f'<g transform="rotate({rot[0]} {rot[1]} {rot[2]})">{path}</g>' if rot else path)
        elif item[0] == "write":
            _, rot, x, y, chars = item
            body = "".join(tl.fade(c_at, glyph, until=end) for c_at, glyph in chars)
            sk.append(f'<g transform="rotate({rot} {x} {y})">{body}</g>' if rot else body)
        else:
            _, s, body = item
            sk.append(tl.fade(s, body, until=end))
    b.append(f'<g class="sketch">{"".join(sk)}</g>')

    # frame 2: the wena mark fades in large over the sketch, holds, and fades away
    wh = 220
    ww = wh * 694 / 436
    ease = "animation-timing-function:cubic-bezier(.4,0,.2,1)"
    k = tl.rule(
        f"0%,{end}%{{opacity:0;transform:scale(.92);{ease}}}"
        f"{end + 9}%,{end + 15}%{{opacity:1;transform:none;{ease}}}"
        f"{end + 22}%,100%{{opacity:0;transform:scale(1.03)}}"
    )
    b.append(f'<g class="logo {k}" style="transform-box:fill-box;transform-origin:center">{wena_mark(910 - ww / 2, 260 - wh / 2, wh, accent)}</g>')

    # frame 3: the designed landscape, built up layer by layer
    t0 = end + 21
    for i, (label, cy) in enumerate(LAYERS):
        lw = text_width(label, 12, 600, 2)
        b.append(tl.fade(t0 + i * 3, f'<g transform="rotate(-90 616 {cy + lw / 2:.1f})">{text(label, 616, cy + lw / 2, 12, 600, muted, tracking=2)}</g>'))
    for y in (136, 340):
        b.append(tl.fade(t0, f'<path d="M634 {y}H1170" stroke="{faint}" stroke-width="1.5" stroke-dasharray="2 6" stroke-linecap="round"/>'))
    for i, (kind, src, dst) in enumerate(RELATIONS):
        tone = accent if HIGHLIGHT in (src, dst) else ink
        b.append(tl.fade(t0 + 8 + i * .45, connect(kind, src, dst, tone, bg)))
    layer_of = {name: next(i for i, (_, cy) in enumerate(LAYERS) if abs(ELEMENTS[name][2] - cy) <= 60) for name in ELEMENTS}
    for i, name in enumerate(ELEMENTS):
        b.append(tl.appear(t0 + layer_of[name] * 3 + i * .3, element(name, accent if name == HIGHLIGHT else ink, bg)))
    legend_y = 480
    lx, legend = 634, []
    for kind in ("serving", "flow", "triggering"):
        legend.append(relation(kind, lx, legend_y, lx + 46, legend_y, muted, bg) + text(kind, lx + 56, legend_y + 5, 14, 500, muted))
        lx += 56 + text_width(kind, 14, 500) + 32
    b.append(tl.fade(t0 + 18, "".join(legend)))
    assert t0 + 22 < tl.HOLD, "landscape starts too late"

    alt = (
        f"{' '.join(s for s, _ in HEADLINE)} {SUBLINE} "
        "Animation in three frames: messy napkin notes with sticky notes and tape ('customers??', 'AI agent here??', "
        "'who owns the data?'), then the wena logo, then a layered ArchiMate landscape: business processes served by "
        "application components, including an AI agent, running on two technology platforms."
    )
    reduced = ".sketch,.logo{display:none}"
    return svg(W, H, "".join(b), alt, tl.style(reduced))


# ---------------------------------------------------------------- sections


def eyebrow(label: str, x: float, y: float, t: dict) -> str:
    return text(label, x, y, 16, 600, t["muted"], tracking=2.6)


def interests(t: dict) -> str:
    W, size, lead, gap = 1200, 36, 56, 22
    ink, accent = t["ink"], t["accent"]
    b = [eyebrow("INTERESTED IN", 0, 18, t)]
    x, y = 0.0, 80
    slash_w = text_width("/", size, 400)
    for i, word in enumerate(INTERESTS):
        w = text_width(word, size, 500, -.6)
        if x and x + w > W:
            x, y = 0.0, y + lead
        b.append(text(word, x, y, size, 500, ink, tracking=-.6))
        x += w
        if i < len(INTERESTS) - 1:
            b.append(text("/", x + gap, y, size, 400, accent))
            x += gap * 2 + slash_w
    return svg(W, y + 14, "".join(b), "Interested in: " + ", ".join(INTERESTS) + ".")


def building(t: dict) -> str:
    return svg(1200, 24, eyebrow("BUILDING", 0, 18, t), "Building")


def project(p: dict, t: dict) -> str:
    W, M = 280, 72
    ink, muted, accent = t["ink"], t["muted"], t["accent"]
    nw = text_width(p["slug"], 30, 700, -.6)
    b = [
        mark(p["slug"], 0, 0, M, ink),
        text(p["slug"], 0, 126, 30, 700, ink, tracking=-.6),
        arrow(nw + 10, 122, 13, accent),
    ]
    lines = wrap(p["line"], 20, 400, W - 24)
    assert len(lines) <= 2, f"{p['slug']} line is too long"
    for i, s in enumerate(lines):
        b.append(text(s, 0, 162 + i * 28, 20, 400, muted))
    return svg(W, 196, "".join(b), f"{p['slug']}: {p['line']}")


def link(icon: str, label: str, t: dict) -> str:
    h, ic = 40, 22
    ink, accent = t["ink"], t["accent"]
    if icon == "wena":
        iw, icon_svg = ic * 694 / 436, wena_mark(0, (h - ic) / 2, ic, ink)
    else:
        iw = ic
        icon_svg = (
            f'<rect x="0" y="{(h - ic) / 2}" width="{ic}" height="{ic}" rx="4" fill="{ink}"/>'
            + text("in", 3.5, (h - ic) / 2 + ic * .8, ic * .78, 700, t["bg"], tracking=-.5)
        )
    tx = iw + 12
    tw = text_width(label, 22, 500)
    body = icon_svg + text(label, tx, 28, 22, 500, accent) + arrow(tx + tw + 8, 27, 12, accent)
    return svg(tx + tw + 8 + 14, h, body, label)


# ---------------------------------------------------------------- build


def main() -> None:
    OUT.mkdir(exist_ok=True)
    for old in OUT.glob("*.svg"):
        old.unlink()
    for name, t in THEMES.items():
        (OUT / f"hero-{name}.svg").write_text(hero(t), encoding="utf-8")
        (OUT / f"interests-{name}.svg").write_text(interests(t), encoding="utf-8")
        (OUT / f"building-{name}.svg").write_text(building(t), encoding="utf-8")
        for p in PROJECTS:
            (OUT / f"project-{p['slug']}-{name}.svg").write_text(project(p, t), encoding="utf-8")
        for icon, label in LINKS:
            (OUT / f"link-{icon}-{name}.svg").write_text(link(icon, label, t), encoding="utf-8")
    names = {}
    for f in sorted(OUT.glob("*.svg")):
        # GitHub redirects image URLs to raw.githubusercontent.com and drops any query string,
        # so only a new file name makes browsers fetch a changed image
        hashed = f.with_name(f"{f.stem}.{hashlib.sha256(f.read_bytes()).hexdigest()[:8]}.svg")
        f.rename(hashed)
        names[f.stem] = hashed.name
        print(f"{hashed.stat().st_size / 1024:6.1f} KB  {hashed.name}")
    stamp_readme(names)


def stamp_readme(names: dict[str, str]) -> None:
    """Point every asset reference in README.md at the current hashed file name."""
    readme = ROOT.parent / "README.md"
    md = readme.read_text(encoding="utf-8")
    md = re.sub(r"assets/([a-z-]+)(?:\.[0-9a-f]{8})?\.svg(?:\?v=\w+)?", lambda m: f"assets/{names[m.group(1)]}", md)
    readme.write_text(md, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
