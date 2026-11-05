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


# the official diagram the sketch becomes: an ArchiMate application cooperation view
COMPONENTS = {"Portal": (710, 150), "CRM": (910, 150), "ERP": (1110, 150), "Identity": (710, 340), "Data": (910, 340), "Billing": (1110, 340)}
# (kind, from, to); serving = solid line + open arrowhead, flow = dashed line + filled arrowhead
RELATIONS = [
    ("flow", "Portal", "CRM"), ("flow", "CRM", "ERP"), ("serving", "Identity", "Portal"),
    ("serving", "Data", "CRM"), ("flow", "ERP", "Billing"), ("flow", "Billing", "Data"),
]
BW, BH = 150, 56


def relation(kind: str, a: tuple[float, float], b: tuple[float, float], ink: str, bg: str) -> str:
    (ax, ay), (bx, by) = a, b
    if ay == by:  # horizontal: leave and enter through the side edges
        s = 1 if bx > ax else -1
        x1, y1, x2, y2 = ax + s * BW / 2, ay, bx - s * BW / 2, by
    else:  # vertical: through top/bottom edges
        s = 1 if by > ay else -1
        x1, y1, x2, y2 = ax, ay + s * BH / 2, bx, by - s * BH / 2
    ang = math.atan2(y2 - y1, x2 - x1)
    ux, uy = math.cos(ang), math.sin(ang)
    back = (x2 - 11 * ux, y2 - 11 * uy)
    wing = [(back[0] - 6 * uy * s2, back[1] + 6 * ux * s2) for s2 in (1, -1)]
    dash = ' stroke-dasharray="6 4"' if kind == "flow" else ""
    end = back if kind == "flow" else (x2, y2)
    line = f'<path d="M{x1} {y1}L{end[0]:.1f} {end[1]:.1f}" stroke="{ink}" stroke-width="1.75"{dash}/>'
    if kind == "flow":
        head = f'<path fill="{ink}" d="M{x2} {y2}L{wing[0][0]:.1f} {wing[0][1]:.1f}L{wing[1][0]:.1f} {wing[1][1]:.1f}Z"/>'
    else:
        head = (
            f'<path fill="none" stroke="{ink}" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" '
            f'd="M{wing[0][0]:.1f} {wing[0][1]:.1f}L{x2} {y2}L{wing[1][0]:.1f} {wing[1][1]:.1f}"/>'
        )
    return line + head


def component(label: str, cx: float, cy: float, ink: str, bg: str) -> str:
    x, y = cx - BW / 2, cy - BH / 2
    ix, iy = x + BW - 26, y + 9
    lw = text_width(label, 18, 500)
    fits(lw, BW - 24, label)
    return (
        f'<rect x="{x}" y="{y}" width="{BW}" height="{BH}" rx="2" fill="{bg}" stroke="{ink}" stroke-width="1.75"/>'
        f'<g stroke="{ink}" stroke-width="1.4"><rect x="{ix + 4}" y="{iy}" width="13" height="15" fill="none"/>'
        f'<rect x="{ix}" y="{iy + 2.5}" width="8" height="4" fill="{bg}"/><rect x="{ix}" y="{iy + 8.5}" width="8" height="4" fill="{bg}"/></g>'
        + text(label, cx - lw / 2, cy + 13, 18, 500, ink)
    )


def hero(t: dict) -> str:
    W, H = 1200, 520
    ink, muted, accent, bg = t["ink"], t["muted"], t["accent"], t["bg"]
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

    # frame 1: a napkin sketch with handwritten notes fills the space; strokes and writing
    # are queued and timed later, once we know how long the whole sketch takes
    pen, queue, at = Pen(11), [], 2.0

    def stroke(d: str, dur: float, w: float = 2.2) -> None:
        nonlocal at
        queue.append(("draw", at, at + dur, d, w))
        at += dur * .75

    def write(s: str, x: float, y: float, size: float, weight: int = 500, rot: float = 0, room: float | None = None) -> None:
        nonlocal at
        if room:
            fits(text_width(s, size, weight, family="hand"), room, s)
        chars, cx = [], x
        for ch in s:
            if ch != " ":
                chars.append((at, text(ch, cx, y, size, weight, ink, family="hand")))
                at += .17
            cx += text_width(ch, size, weight, family="hand")
        queue.append(("write", rot, x, y, chars))
        at += .4

    def box(x: float, y: float, w: float, h: float, title: str, note: str) -> None:
        stroke(pen.rect(x, y, w, h), 2)
        write(title, x + 18, y + 44, 34, 600, room=w - 30)
        write(note, x + 18, y + 80, 25, room=w - 26)

    box(650, 48, 175, 100, "portal", "login? SSO?")
    box(990, 40, 190, 110, "CRM", "customers + deals")
    write("sync nightly", 842, 84, 25)
    stroke(pen.line([(838, 76), (958, 74)], step=30), .6, 2)
    write("realtime!", 850, 120, 27, 600)
    stroke(pen.circle(905, 262, 66), 2)
    write("data", 872, 270, 36, 600)
    stroke(pen.scrawl(872, 284, 58), .8, 1.6)
    write("who owns this?", 650, 262, 25, rot=-5)
    box(645, 362, 190, 110, "ERP", "orders, stock")
    box(1000, 372, 180, 100, "billing", "still manual :(")
    # a sticky note taped on
    queue.append(("raw", at, f'<g transform="rotate(5 1108 262)"><rect x="1080" y="204" width="56" height="16" fill="{muted}" fill-opacity=".3"/></g>'))
    stroke(pen.rect(1052, 214, 118, 96), 1.4, 1.8)
    write("AI agent", 1066, 254, 27, 600, rot=5, room=100)
    write("here??", 1066, 288, 27, 600, rot=5)
    for a, z in (((790, 154), (850, 210)), ((975, 226), (1030, 166)), ((848, 318), (790, 358)), ((1032, 368), (965, 314))):
        shaft, head = pen.arrow(a, z)
        stroke(shaft, 1.1)
        stroke(head, .4)
    end = round(at + 2)
    assert end <= 46, f"sketch runs too long: {end}%"

    sk = []
    for item in queue:
        if item[0] == "draw":
            _, s, e, d, w = item
            sk.append(tl.draw(s, e, d, ink, w, until=end))
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

    # frame 3: the official diagram
    t0 = end + 21
    b.append(tl.fade(t0, text("APPLICATION COOPERATION VIEW", 636, 54, 14, 600, muted, tracking=2.2)))
    for i, (kind, a, z) in enumerate(RELATIONS):
        b.append(tl.fade(t0 + 6 + i * 1.2, relation(kind, COMPONENTS[a], COMPONENTS[z], ink, bg)))
    for i, (label, (cx, cy)) in enumerate(COMPONENTS.items()):
        b.append(tl.appear(t0 + 1 + i * .8, component(label, cx, cy, ink, bg)))
    legend_y = 452
    legend = (
        relation("serving", (636 - BW / 2, legend_y), (690 + BW / 2, legend_y), muted, bg)
        + text("serving", 702, legend_y + 5, 15, 500, muted)
        + relation("flow", (790 - BW / 2, legend_y), (844 + BW / 2, legend_y), muted, bg)
        + text("flow", 856, legend_y + 5, 15, 500, muted)
    )
    b.append(tl.fade(t0 + 14, legend))
    assert t0 + 18 < tl.HOLD, "landscape starts too late"

    alt = (
        f"{' '.join(s for s, _ in HEADLINE)} {SUBLINE} "
        "Animation in three frames: a napkin sketch with handwritten notes (portal, CRM, ERP, billing, data, "
        "'who owns this?', 'AI agent here??'), then the wena logo, then a clean ArchiMate application "
        "cooperation view of Portal, CRM, ERP, Identity, Data and Billing with serving and flow relations."
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
