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

    LOOP, HOLD, GONE = 22, 92, 97  # seconds per loop; % where the final fade starts and ends

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


# the designed landscape the sketch becomes: a layered ArchiMate view of the same scenario,
# with the Azure services that run it (official Azure architecture icons, used unmodified).
AZURE = SRC / "azure"
_azure_uses = 0


def azure_icon(slug: str, x: float, y: float, size: float) -> str:
    """Embed an Azure icon as-is; only its ids are made unique within the page."""
    global _azure_uses
    _azure_uses += 1
    src = (AZURE / f"{slug}.svg").read_text(encoding="utf-8")
    view = re.search(r'viewBox="([^"]+)"', src).group(1)
    inner = re.search(r"<svg[^>]*>(.*)</svg>", src, re.S).group(1)
    for i in set(re.findall(r'id="([^"]+)"', inner)):
        inner = inner.replace(f'id="{i}"', f'id="az{_azure_uses}-{i}"').replace(f"#{i})", f"#az{_azure_uses}-{i})")
    return f'<svg x="{x}" y="{y}" width="{size}" height="{size}" viewBox="{view}">{inner}</svg>'


LAYERS = [("BUSINESS", 72), ("APPLICATION", 205), ("TECHNOLOGY", 410)]
COLS = (682, 826, 970, 1114)
# name: (kind, centre x, centre y, width, height, Azure icon, Azure service name)
ELEMENTS = {
    "Tenant": ("actor", COLS[0], 72, 120, 46, None, None),
    "Report repair": ("process", COLS[1], 72, 120, 46, None, None),
    "Plan repair": ("process", COLS[2], 72, 120, 46, None, None),
    "Contractor": ("actor", COLS[3], 72, 120, 46, None, None),
    "Tenant app": ("component", COLS[0], 205, 120, 84, "static-web-apps", "Static Web Apps"),
    "AI triage": ("component", COLS[1], 205, 120, 84, "openai", "Azure OpenAI"),
    "Work orders": ("component", COLS[2], 205, 120, 84, "logic-apps", "Logic Apps"),
    "Contractor app": ("component", COLS[3], 205, 120, 84, "app-service", "App Service"),
    "Azure platform": ("node", 898, 410, 552, 140, None, None),
}
PLATFORM = [("sql-database", "SQL Database"), ("service-bus", "Service Bus"), ("key-vault", "Key Vault"),
            ("monitor", "Monitor"), ("communication-services", "Comm. Services")]
RELATIONS = [  # (kind, from, to)
    ("assignment", "Tenant", "Report repair"), ("triggering", "Report repair", "Plan repair"),
    ("assignment", "Contractor", "Plan repair"),
    ("serving", "Tenant app", "Tenant"), ("serving", "AI triage", "Report repair"),
    ("serving", "Work orders", "Plan repair"), ("serving", "Contractor app", "Contractor"),
    ("flow", "Tenant app", "AI triage"), ("flow", "AI triage", "Work orders"), ("flow", "Work orders", "Contractor app"),
    ("serving", "Azure platform", "Tenant app"), ("serving", "Azure platform", "AI triage"),
    ("serving", "Azure platform", "Work orders"), ("serving", "Azure platform", "Contractor app"),
]
NODE_DEPTH = 7


def relation(kind: str, x1: float, y1: float, x2: float, y2: float, ink: str) -> str:
    """ArchiMate relation between two points. serving: solid + open head; flow: dashed + filled
    head; triggering: solid + filled head; assignment: dot at the source + filled head."""
    ang = math.atan2(y2 - y1, x2 - x1)
    ux, uy = math.cos(ang), math.sin(ang)
    back = (x2 - 10 * ux, y2 - 10 * uy)
    wing = [(back[0] - 5.5 * uy * s, back[1] + 5.5 * ux * s) for s in (1, -1)]
    filled = kind != "serving"
    end = back if filled else (x2, y2)
    dash = ' stroke-dasharray="5 4"' if kind == "flow" else ""
    out = f'<path d="M{x1:.1f} {y1:.1f}L{end[0]:.1f} {end[1]:.1f}" stroke="{ink}" stroke-width="1.6"{dash}/>'
    if kind == "assignment":
        out += f'<circle cx="{x1:.1f}" cy="{y1:.1f}" r="3.5" fill="{ink}"/>'
    wings = f"M{wing[0][0]:.1f} {wing[0][1]:.1f}L{x2:.1f} {y2:.1f}L{wing[1][0]:.1f} {wing[1][1]:.1f}"
    if filled:
        return out + f'<path fill="{ink}" d="{wings}Z"/>'
    return out + f'<path fill="none" stroke="{ink}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" d="{wings}"/>'


def connect(kind: str, src: str, dst: str, ink: str) -> str:
    sk, sx, sy, sw, sh, *_ = ELEMENTS[src]
    dk, dx, dy, dw, dh, *_ = ELEMENTS[dst]
    if abs(sy - dy) < 1:  # same row: side to side
        s = 1 if dx > sx else -1
        return relation(kind, sx + s * sw / 2, sy, dx - s * dw / 2, dy, ink)
    x = dx if sk == "node" else sx  # the node spans every component: drop straight onto the target
    s = 1 if dy > sy else -1
    top = NODE_DEPTH if sk == "node" else 0
    return relation(kind, x, sy + s * (sh / 2 + top), x, dy - s * dh / 2, ink)


def element(name: str, ink: str, muted: str, bg: str) -> str:
    kind, cx, cy, w, h, az, az_name = ELEMENTS[name]
    x, y = cx - w / 2, cy - h / 2
    ix, iy = x + w - 24, y + 8
    label_y, size = cy + 12, 15
    extra = ""
    if kind == "node":
        d = NODE_DEPTH
        shape = (
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{bg}" stroke="{ink}" stroke-width="1.6"/>'
            f'<path fill="none" stroke="{ink}" stroke-width="1.6" stroke-linejoin="round" d="M{x} {y}l{d} {-d}h{w}v{h}l{-d} {d}M{x + w} {y}l{d} {-d}"/>'
        )
        icon = f'<rect x="{ix}" y="{iy + 3}" width="12" height="10" fill="none"/><path fill="none" d="M{ix} {iy + 3}l3 -3h12v10l-3 3M{ix + 12} {iy + 3}l3 -3"/>'
        slot = (w - 40) / len(PLATFORM)
        for i, (slug, label) in enumerate(PLATFORM):
            sx = x + 20 + slot * (i + .5)
            lw = text_width(label, 12, 500)
            fits(lw, slot - 6, label)
            extra += azure_icon(slug, sx - 20, y + 42, 40) + text(label, sx - lw / 2, y + 104, 12, 500, muted)
        return (
            shape + f'<g stroke="{ink}" stroke-width="1.3" stroke-linejoin="round">{icon}</g>'
            + text(name, x + 16, y + 26, 15, 600, ink) + extra
        )
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
    if az:
        extra = azure_icon(az, x + 10, y + 10, 28)
        nw = text_width(az_name, 12, 500)
        fits(nw, w - 12, az_name)
        extra += text(az_name, cx - nw / 2, y + 74, 12, 500, muted)
        label_y, size = y + 56, 14
    lw = text_width(name, size, 600 if az else 500)
    fits(lw, w - 14, name)
    return (
        shape + f'<g stroke="{ink}" stroke-width="1.3" stroke-linejoin="round" stroke-linecap="round">{icon}</g>'
        + extra + text(name, cx - lw / 2, label_y, size, 600 if az else 500, ink)
    )


def hero(t: dict) -> str:
    W, H = 1200, 540
    ink, muted, faint, accent, bg = t["ink"], t["muted"], t["faint"], t["accent"], t["bg"]
    tl = Timeline()
    b = []

    # left: words
    for i, (s, tone) in enumerate(HEADLINE):
        fits(text_width(s, 64, 700, -2), 560, s)
        b.append(f'<g class="rise" style="--o:{.2 + i * .1:.1f}s">' + text(s, -3, 194 + i * 72, 64, 700, t[tone], tracking=-2) + "</g>")
    b.append(
        '<g class="rise" style="--o:.6s">'
        + "".join(text(s, 0, 400 + i * 36, 24, 400, muted) for i, s in enumerate(wrap(SUBLINE, 24, 400, 500)))
        + "</g>"
    )

    # frame 1: a client's question, thought out loud on a napkin. Strokes and handwriting
    # are queued and timed once we know how long the whole sketch takes.
    pen, queue, at = Pen(23), [], 2.0

    def stroke(d: str, dur: float, w: float = 2.2, rot: tuple[float, float, float] | None = None) -> None:
        nonlocal at
        queue.append(("draw", at, at + dur, d, w, rot))
        at += dur * .75

    def write(s: str, x: float, y: float, size: float, weight: int = 500, rot: float = 0) -> float:
        nonlocal at
        chars, cx = [], x
        for ch in s:
            if ch != " ":
                chars.append((at, text(ch, cx, y, size, weight, ink, family="hand")))
                at += .11
            cx += text_width(ch, size, weight, family="hand")
        queue.append(("write", rot, x, y, chars))
        at += .3
        return cx  # where the writing ended

    def strike(x1: float, x2: float, y: float) -> None:
        stroke(pen.line([(x1 - 4, y), (x2 + 4, y - 3)], step=30), .5, 2.2)

    def sticky(x: float, y: float, w: float, h: float, rot: float, lines: list[str]) -> None:
        cx, cy = x + w / 2, y + h / 2
        tape = f'<rect x="{cx - 30}" y="{y - 9}" width="60" height="18" fill="{muted}" fill-opacity=".3"/>'
        queue.append(("raw", at, f'<g transform="rotate({rot} {cx} {cy})">{tape}</g>'))
        stroke(pen.rect(x, y, w, h), 1, 1.8, rot=(rot, cx, cy))
        for i, s in enumerate(lines):
            write(s, x + 14, y + 38 + i * 30, 26, 600, rot=rot)

    # the question
    e1 = write("Repairs take weeks.", 640, 62, 36, 700)
    e2 = write("How do we fix that?", 640, 102, 36, 700)
    stroke(pen.line([(636, 116), (max(e1, e2) + 6, 112)], step=40), .6, 2)
    stroke(pen.line([(646, 124), (max(e1, e2) - 20, 121)], step=40), .5, 1.8)
    # their ideas, crossed out and corrected
    e = write("tenants call us", 646, 176, 26)
    strike(646, e, 168)
    e = write("app + photo!", e + 18, 178, 28, 700, rot=-3)
    stroke(pen.blob(e - 62, 168, 80, 28, 1.05), .8, 1.8)
    sticky(1000, 150, 170, 92, 5, ["AI sorts it", "by urgency?"])
    a, h = pen.curve([(e + 14, 176), (930, 186), (994, 192)])
    stroke(a, .7)
    stroke(h, .3)
    write("planner assigns", 646, 266, 26)
    e = write("by hand", 646, 300, 26)
    strike(646, e, 292)
    write("rules + AI", e + 16, 302, 28, 700, rot=-2)
    e = write("excel sheet", 870, 286, 26, rot=4)
    stroke(pen.line([(866, 262), (e + 4, 298)], step=30), .4, 2.2)
    stroke(pen.line([(866, 298), (e + 4, 264)], step=30), .4, 2.2)
    a, h = pen.curve([(1080, 250), (1070, 300), (1030, 350)])
    stroke(a, .6)
    stroke(h, .3)
    e = write("contractor app?", 870, 380, 28, 700)
    stroke(pen.line([(862, 348), (e + 8, 344), (e + 10, 392)], step=24), .6, 1.8)
    write("status updates", 646, 380, 26)
    write("to the tenant!!", 646, 412, 26, 700)
    a, h = pen.curve([(700, 424), (760, 470), (840, 452)])
    stroke(a, .6)
    stroke(h, .3)
    sticky(1012, 418, 150, 84, -5, ["costs??"])
    sec = 100 / tl.LOOP  # % of the loop per second
    end = round(at + 1.6 * sec, 2)  # the finished sketch stays up for 1.6 s before it fades
    assert end <= 60, f"sketch runs too long: {end}%"

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

    # frame 2: the outline of the wena mark is drawn as one smooth line, filled in, and then
    # erased the same way it was drawn (the fill lifts and the line's tail catches up)
    wh = 220
    ww = wh * 694 / 436
    a = end + .2 * sec
    drawn = a + 1.1 * sec
    filled = drawn + .35 * sec
    erase = filled + .45 * sec
    d = erase + .9 * sec
    ease = "animation-timing-function:cubic-bezier(.65,0,.35,1)"
    line = tl.rule(
        f"0%,{a:.2f}%{{stroke-dashoffset:100;{ease}}}"
        f"{drawn:.2f}%,{erase:.2f}%{{stroke-dashoffset:0;{ease}}}"
        f"{d:.2f}%,100%{{stroke-dashoffset:-100}}"
    )
    fill = tl.rule(
        f"0%,{drawn:.2f}%{{opacity:0;{ease}}}"
        f"{filled:.2f}%,{erase:.2f}%{{opacity:1;{ease}}}"
        f"{erase + .35 * sec:.2f}%,100%{{opacity:0}}"
    )
    b.append(
        f'<svg class="logo" x="{910 - ww / 2:.1f}" y="{270 - wh / 2:.1f}" width="{ww:.1f}" height="{wh}" viewBox="0 0 694 436" overflow="visible">'
        f'<path class="{fill}" d="{WENA_D}" fill="{accent}"/>'
        f'<path class="{line}" d="{WENA_D}" pathLength="100" stroke-dasharray="100 100" fill="none" stroke="{accent}" '
        'stroke-width="9" stroke-linecap="round" stroke-linejoin="round"/></svg>'
    )

    # frame 3: the designed landscape, built up layer by layer
    t0 = d + .3 * sec
    for i, (label, cy) in enumerate(LAYERS):
        lw = text_width(label, 12, 600, 2)
        b.append(tl.fade(t0 + i * 3, f'<g transform="rotate(-90 612 {cy + lw / 2:.1f})">{text(label, 612, cy + lw / 2, 12, 600, muted, tracking=2)}</g>'))
    for y in (122, 300):
        b.append(tl.fade(t0, f'<path d="M622 {y}H1180" stroke="{faint}" stroke-width="1.5" stroke-dasharray="2 6" stroke-linecap="round"/>'))
    for i, (kind, src, dst) in enumerate(RELATIONS):
        b.append(tl.fade(t0 + 8 + i * .5, connect(kind, src, dst, ink)))
    layer_of = {name: next(i for i, (_, cy) in enumerate(LAYERS) if abs(ELEMENTS[name][2] - cy) <= 80) for name in ELEMENTS}
    for i, name in enumerate(ELEMENTS):
        b.append(tl.appear(t0 + layer_of[name] * 3 + i * .3, element(name, ink, muted, bg)))
    legend_y = 522
    lx, legend = 622, []
    for kind in ("serving", "flow", "triggering", "assignment"):
        legend.append(relation(kind, lx, legend_y, lx + 40, legend_y, muted) + text(kind, lx + 50, legend_y + 5, 14, 500, muted))
        lx += 50 + text_width(kind, 14, 500) + 26
    fits(lx, 1210, "legend")
    b.append(tl.fade(t0 + 16, "".join(legend)))
    assert t0 + 18 < tl.HOLD, "landscape starts too late"

    alt = (
        f"{' '.join(s for s, _ in HEADLINE)} {SUBLINE} "
        "Animation in three frames. First a napkin sketch of a client question, 'Repairs take weeks. How do we fix that?', "
        "with ideas scribbled and crossed out: tenants calling becomes an app with a photo, AI sorts by urgency, the "
        "planner's excel sheet is crossed out for rules and AI, a contractor app, status updates to the tenant. Then the "
        "wena logo. Then the designed ArchiMate landscape: tenant and contractor, the report and plan repair processes, "
        "served by a tenant app on Static Web Apps, AI triage on Azure OpenAI, work orders on Logic Apps and a "
        "contractor app on App Service, all on an Azure platform with SQL Database, Service Bus, Key Vault, Monitor "
        "and Communication Services."
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
