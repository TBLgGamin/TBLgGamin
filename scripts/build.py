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

_FONT_PATH = SRC / "space-grotesk-latin-wght-normal.woff2"
_fonts: dict[int, TTFont] = {}


def _font(weight: int) -> TTFont:
    if weight not in _fonts:
        _fonts[weight] = instantiateVariableFont(TTFont(_FONT_PATH), {"wght": weight})
    return _fonts[weight]


def text_width(s: str, size: float, weight: int = 400, tracking: float = 0) -> float:
    f = _font(weight)
    cmap, hmtx, upm = f.getBestCmap(), f["hmtx"], f["head"].unitsPerEm
    return sum(hmtx[cmap[ord(c)]][0] for c in s) * size / upm + tracking * max(len(s) - 1, 0)


def text(s: str, x: float, y: float, size: float, weight: int, fill: str, tracking: float = 0) -> str:
    """Outlined text as one <path>; y is the baseline."""
    f = _font(weight)
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
    """One looping sequence. Every element gets its own keyframes on the same clock,
    so the loop stays in sync: things appear in order, hold, then all fade out together."""

    LOOP, HOLD, GONE = 10, 88, 95  # seconds per loop; % where the fade-out starts and ends

    def __init__(self) -> None:
        self.css: list[str] = []

    def _rule(self, frames: str) -> str:
        k = f"k{len(self.css)}"
        self.css.append(f"@keyframes {k}{{{frames}}}.{k}{{animation:{k} {self.LOOP}s linear infinite}}")
        return k

    def appear(self, at: float, body: str) -> str:
        """Fade and grow in at `at` %."""
        k = self._rule(
            f"0%,{at}%{{opacity:0;transform:scale(.6)}}"
            f"{at + 4}%,{self.HOLD}%{{opacity:1;transform:none}}"
            f"{self.GONE}%,100%{{opacity:0}}"
        )
        return f'<g class="{k}" style="transform-box:fill-box;transform-origin:center">{body}</g>'

    def draw(self, start: float, end: float, d: str, stroke: str, width: float = 2) -> str:
        """Stroke a path from `start` % to `end` %."""
        k = self._rule(
            f"0%,{start}%{{stroke-dashoffset:100;opacity:1}}"
            f"{end}%,{self.HOLD}%{{stroke-dashoffset:0;opacity:1}}"
            f"{self.GONE}%,100%{{stroke-dashoffset:0;opacity:0}}"
        )
        return (
            f'<path class="{k}" pathLength="100" stroke-dasharray="100" d="{d}" fill="none" '
            f'stroke="{stroke}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"/>'
        )

    def style(self) -> str:
        rise = (
            ".rise{opacity:0;animation:rise .8s cubic-bezier(.2,.7,.2,1) forwards;animation-delay:var(--o,0s)}"
            "@keyframes rise{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:none}}"
        )
        # reduced motion: no animation, every element shows its finished state
        still = "@media (prefers-reduced-motion:reduce){*{animation:none!important;opacity:1!important}}"
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


def scribble_path(seed: int, cx: float, cy: float, rx: float, ry: float) -> str:
    """A hand-drawn tangle: jittered loops joined by a smooth Catmull-Rom curve,
    ending in a short tail to the right of the box."""
    rng = random.Random(seed)
    pts = [(cx - rx, cy + ry * .2)]
    for i in range(22):
        a = i * 2.35 + rng.uniform(-.5, .5)
        r = rng.uniform(.35, 1)
        drift = (i / 21 - .5) * rx * .5
        pts.append((cx + drift + math.cos(a) * rx * r * .75, cy + math.sin(a) * ry * r * .8 + rng.uniform(-8, 8)))
    pts.append((cx + rx * .85, cy + 6))
    pts.append((cx + rx + 12, cy))
    d = f"M{pts[0][0]:.1f} {pts[0][1]:.1f}"
    for i in range(len(pts) - 1):
        p0, p1, p2 = pts[max(i - 1, 0)], pts[i], pts[i + 1]
        p3 = pts[min(i + 2, len(pts) - 1)]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d += f"C{c1[0]:.1f} {c1[1]:.1f} {c2[0]:.1f} {c2[1]:.1f} {p2[0]:.1f} {p2[1]:.1f}"
    return d


class ArchiMate:
    """A few ArchiMate 3.2 notation shapes, drawn in one ink colour (colour carries no
    meaning in ArchiMate). Square corners = structure, rounded corners = behaviour."""

    H = 60

    def __init__(self, tl: Timeline, t: dict) -> None:
        self.tl, self.ink, self.bg = tl, t["ink"], t["bg"]

    def element(self, kind: str, cx: float, cy: float, label: str, at: float, w: float = 164) -> str:
        ink, bg, h = self.ink, self.bg, self.H
        x, y = cx - w / 2, cy - h / 2
        rx = 2 if kind == "component" else 14
        ix, iy = x + w - 26, y + 9
        if kind == "component":
            icon = (
                f'<rect x="{ix + 4}" y="{iy}" width="14" height="16" fill="none"/>'
                f'<rect x="{ix}" y="{iy + 3}" width="8" height="4" fill="{bg}"/>'
                f'<rect x="{ix}" y="{iy + 9.5}" width="8" height="4" fill="{bg}"/>'
            )
        elif kind == "service":
            icon = f'<rect x="{ix - 2}" y="{iy + 3}" width="20" height="10" rx="5" fill="none"/>'
        else:  # process
            icon = f'<path fill="none" d="M{ix - 3} {iy + 5}h11v-4l8 7l-8 7v-4h-11z"/>'
        lw = text_width(label, 17, 500)
        fits(lw, w - 20, label)
        body = (
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{bg}" stroke="{ink}" stroke-width="1.75"/>'
            f'<g stroke="{ink}" stroke-width="1.5" stroke-linejoin="round">{icon}</g>'
            + text(label, cx - lw / 2, cy + 14, 17, 500, ink)
        )
        return self.tl.appear(at, body)

    def serving(self, x: float, y1: float, y2: float, at: float) -> str:
        """Serving: solid line, open arrowhead."""
        return self.tl.draw(at, at + 3, f"M{x} {y1}V{y2}", self.ink, 1.75) + self.tl.appear(
            at + 3, f'<path fill="none" stroke="{self.ink}" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" d="M{x - 6} {y2 + 10}L{x} {y2}L{x + 6} {y2 + 10}"/>'
        )

    def realization(self, x: float, y1: float, y2: float, at: float) -> str:
        """Realization: dashed line, hollow triangle."""
        line = f'<path d="M{x} {y1}V{y2 + 11}" stroke="{self.ink}" stroke-width="1.75" stroke-dasharray="5 4"/>'
        head = f'<path fill="{self.bg}" stroke="{self.ink}" stroke-width="1.75" stroke-linejoin="round" d="M{x} {y2}L{x - 7} {y2 + 11}H{x + 7}Z"/>'
        return self.tl.appear(at, line + head)

    def flow(self, x1: float, x2: float, y: float, at: float) -> str:
        """Flow: dashed line, filled arrowhead."""
        line = f'<path d="M{x1} {y}H{x2 - 9}" stroke="{self.ink}" stroke-width="1.75" stroke-dasharray="5 4"/>'
        head = f'<path fill="{self.ink}" d="M{x2} {y}l-10 -5.5v11z"/>'
        return self.tl.appear(at, line + head)


def hero(t: dict) -> str:
    W, H = 1200, 520
    muted = t["muted"]
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

    # right: a wobbly scribble (the question) becomes an ArchiMate view (the design)
    b.append(tl.appear(1, text("a question", 636, 170, 18, 500, muted)))
    b.append(tl.draw(3, 34, scribble_path(seed=4, cx=715, cy=262, rx=80, ry=105), muted, 2.5))
    b.append(tl.draw(36, 40, "M812 262H838", muted, 2))
    b.append(tl.appear(40, f'<path fill="{muted}" d="M846 262l-10 -6v12z"/>'))

    am = ArchiMate(tl, t)
    col, crm_x = 945, 1120
    proc_y, svc_y, app_y = 120, 245, 370
    b.append(am.element("component", col, app_y, "Portal", 41, w=140))
    b.append(am.element("component", crm_x, app_y, "CRM", 43, w=140))
    b.append(am.flow(col + 70, crm_x - 70, app_y, 46))
    b.append(am.realization(col, app_y - 30, svc_y + 30, 49))
    b.append(am.element("service", col, svc_y, "Request service", 54))
    b.append(am.serving(col, svc_y - 30, proc_y + 30, 58))
    b.append(am.element("process", col, proc_y, "Handle request", 62))
    for label, y in (("BUSINESS", proc_y), ("APPLICATION", svc_y)):
        b.append(tl.appear(65, text(label, 1190 - text_width(label, 13, 600, 2), y + 5, 13, 600, muted, tracking=2)))

    alt = (
        f"{' '.join(s for s, _ in HEADLINE)} {SUBLINE} "
        "Animation: a wobbly scribble, a question, turns into an ArchiMate view: the Portal and CRM application "
        "components, the Request service they realise, and the Handle request business process it serves."
    )
    return svg(W, H, "".join(b), alt, tl.style())


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
    for f in sorted(OUT.glob("*.svg")):
        print(f"{f.stat().st_size / 1024:6.1f} KB  {f.name}")


if __name__ == "__main__":
    main()
