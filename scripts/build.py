"""Generate the profile README artwork (light + dark SVGs) into ../assets.

Text is converted to outlines so the SVGs render identically everywhere
(GitHub serves them as <img>, which cannot load web fonts).

    pip install fonttools brotli
    python scripts/build.py
"""

from __future__ import annotations

import base64
import random
import re
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
OUT = ROOT.parent / "assets"

THEMES = {
    "light": {"ink": "#0A0A0A", "muted": "#737373", "line2": "#D4D4D4", "accent": "#6F49B1"},
    "dark": {"ink": "#FAFAFA", "muted": "#A1A1A1", "line2": "#404040", "accent": "#D6C9F9"},
}

# ---------------------------------------------------------------- type

_FONT_PATH = SRC / "space-grotesk-latin-wght-normal.woff2"
_fonts: dict[int, TTFont] = {}


def _font(weight: int) -> TTFont:
    if weight not in _fonts:
        _fonts[weight] = instantiateVariableFont(TTFont(_FONT_PATH), {"wght": weight})
    return _fonts[weight]


def text_width(text: str, size: float, weight: int = 400, tracking: float = 0) -> float:
    f = _font(weight)
    cmap, hmtx, upm = f.getBestCmap(), f["hmtx"], f["head"].unitsPerEm
    w = sum(hmtx[cmap[ord(c)]][0] for c in text) * size / upm
    return w + tracking * max(len(text) - 1, 0)


def text(s: str, x: float, y: float, size: float, weight: int = 400, fill: str = "currentColor",
         tracking: float = 0, anchor: str = "start") -> str:
    """Outlined text as one <path>. y is the baseline."""
    f = _font(weight)
    cmap, hmtx, upm = f.getBestCmap(), f["hmtx"], f["head"].unitsPerEm
    gs = f.getGlyphSet()
    scale = size / upm
    if anchor != "start":
        w = text_width(s, size, weight, tracking)
        x -= w / 2 if anchor == "middle" else w
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
    w = h * 694 / 436
    return f'<svg x="{x}" y="{y}" width="{w:.1f}" height="{h}" viewBox="0 0 694 436"><path fill="{fill}" d="{WENA_D}"/></svg>'


def png_mark(name: str, x: float, y: float, size: float, fill: str) -> str:
    """A one-colour PNG mark (black on transparent) recoloured to `fill`, keeping its alpha."""
    data = base64.b64encode((SRC / f"{name}-mark.png").read_bytes()).decode()
    r, g, b = (int(fill[i:i + 2], 16) / 255 for i in (1, 3, 5))
    fid = f"ink-{name}"
    return (
        f'<filter id="{fid}"><feColorMatrix type="matrix" values="0 0 0 0 {r:.3f}  0 0 0 0 {g:.3f}  0 0 0 0 {b:.3f}  0 0 0 1 0"/></filter>'
        f'<image x="{x}" y="{y}" width="{size}" height="{size}" filter="url(#{fid})" href="data:image/png;base64,{data}"/>'
    )


def vector_mark(inner: str, x: float, y: float, size: float, fill: str) -> str:
    return f'<svg x="{x}" y="{y}" width="{size}" height="{size}" viewBox="0 0 256 256">{inner.format(c=fill)}</svg>'


def person(cx: float, cy: float, stroke: str, r: float = 24) -> str:
    return (
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{stroke}" stroke-width="1.5"/>'
        f'<circle cx="{cx}" cy="{cy - r * 0.27:.1f}" r="{r * 0.27:.1f}" fill="{stroke}"/>'
        f'<path fill="{stroke}" d="M{cx - r * 0.5:.1f} {cy + r * 0.5:.1f}a{r * 0.5:.1f} {r * 0.42:.1f} 0 0 1 {r:.1f} 0z"/>'
    )


def agent(cx: float, cy: float, accent: str, r: float = 24) -> str:
    out = (
        f'<circle class="halo" cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{accent}" stroke-width="1.5"/>'
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{accent}" fill-opacity=".12" stroke="{accent}" stroke-width="1.5"/>'
        f'<circle cx="{cx}" cy="{cy}" r="{r * 0.3:.1f}" fill="{accent}"/>'
    )
    for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
        out += f'<circle cx="{cx + dx * r * 0.62:.1f}" cy="{cy + dy * r * 0.62:.1f}" r="{r * 0.09:.1f}" fill="{accent}"/>'
    return out


STYLE = """
<style>
.p{stroke-dasharray:5 95;animation:flow var(--d,3s) linear infinite;animation-delay:var(--o,0s)}
@keyframes flow{from{stroke-dashoffset:100}to{stroke-dashoffset:0}}
.halo{transform-box:fill-box;transform-origin:center;animation:halo 2.4s ease-out infinite}
@keyframes halo{from{transform:scale(1);opacity:.7}to{transform:scale(1.9);opacity:0}}
.rise{opacity:0;animation:rise .9s cubic-bezier(.2,.7,.2,1) forwards;animation-delay:var(--o,0s)}
@keyframes rise{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
@media (prefers-reduced-motion:reduce){.p{display:none}.halo{animation:none}.rise{animation:none;opacity:1}}
</style>"""


def svg(w: int, h: int, body: str, title: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img">'
        f"<title>{title}</title>{STYLE}{body}</svg>\n"
    )


# ---------------------------------------------------------------- hero


def edge(x1, y1, x2, y2, stroke, pulse, dur, rng, opacity=1.0, dashed=False) -> str:
    if abs(x2 - x1) < 1:
        d = f"M{x1} {y1}V{y2}"
    else:
        mx = (x1 + x2) / 2
        d = f"M{x1} {y1}C{mx} {y1} {mx} {y2} {x2} {y2}"
    dash = ' stroke-dasharray="4 6"' if dashed else ""
    off = -(rng.random() * dur)
    return (
        f'<path d="{d}" fill="none" stroke="{stroke}" stroke-opacity="{opacity}" stroke-width="1.5"{dash}/>'
        f'<path class="p" style="--d:{dur}s;--o:{off:.2f}s" pathLength="100" d="{d}" fill="none" '
        f'stroke="{pulse}" stroke-width="3" stroke-linecap="round"/>'
    )


def hero(t: dict) -> str:
    rng = random.Random(7)
    W, H = 1200, 480
    ink, muted, line, accent = t["ink"], t["muted"], t["line2"], t["accent"]
    b = [
        # same-hue glow + dot field behind the landscape
        "<defs>"
        f'<radialGradient id="glow" cx="900" cy="260" r="250" gradientUnits="userSpaceOnUse">'
        f'<stop offset="0" stop-color="{accent}" stop-opacity=".16"/><stop offset="1" stop-color="{accent}" stop-opacity="0"/></radialGradient>'
        f'<radialGradient id="fade" cx="900" cy="260" r="260" gradientUnits="userSpaceOnUse">'
        '<stop offset=".55" stop-color="#fff"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>'
        f'<mask id="dotmask"><rect width="{W}" height="{H}" fill="url(#fade)"/></mask>'
        f'<pattern id="dots" width="22" height="22" patternUnits="userSpaceOnUse"><circle cx="11" cy="11" r="1.1" fill="{muted}" fill-opacity=".35"/></pattern>'
        "</defs>"
        f'<rect x="560" width="{W - 560}" height="{H}" fill="url(#glow)"/>'
        f'<rect x="580" width="{W - 600}" height="{H}" fill="url(#dots)" mask="url(#dotmask)"/>'
    ]

    # left: identity, vertically centred on the diagram
    x0 = 40
    b.append(f'<g class="rise" style="--o:.05s">{wena_mark(x0, 108, 30, accent)}</g>')
    b.append(
        '<g class="rise" style="--o:.15s">'
        + text("WESSEL VAN DER VLUGT", x0, 188, 15, 600, muted, tracking=2.4)
        + text("·  SOLUTIONS ARCHITECT", x0 + text_width("WESSEL VAN DER VLUGT", 15, 600, 2.4) + 12, 188, 15, 600, accent, tracking=2.4)
        + "</g>"
    )
    head = [("Mapping where people", ink), ("meet systems.", ink), ("Now systems act too.", accent)]
    for i, (s, c) in enumerate(head):
        b.append(f'<g class="rise" style="--o:{.25 + i * .1:.2f}s">' + text(s, x0 - 2, 258 + i * 60, 52, 700, c, tracking=-1.6) + "</g>")

    # right: an application landscape, people → touchpoints → systems, with an agent lane
    cP, cT, cS = 700, 878, 1084
    for label, cx in (("PEOPLE", cP), ("TOUCHPOINTS", cT), ("SYSTEMS", cS)):
        b.append(text(label, cx, 58, 14, 600, muted, tracking=2.2, anchor="middle"))

    people = {"p1": 160, "p2": 300}
    touch = {"app": 120, "portal": 195, "chat": 270}
    sys_y = {s: 105 + i * 62 for i, s in enumerate(["CRM", "ERP", "data", "identity", "ops", "billing"])}
    ag = (cT, 395)
    tw, sw, nh, pr, ar, fs = 116, 124, 40, 28, 28, 17

    human = 3.4
    for p, tps in (("p1", ["app", "portal"]), ("p2", ["portal", "chat"])):
        for tp in tps:
            b.append(edge(cP + pr + 1, people[p], cT - tw / 2, touch[tp], line, ink, human, rng))
    for tp, ss in (("app", ["CRM", "data"]), ("portal", ["ERP", "identity"])):
        for s in ss:
            b.append(edge(cT + tw / 2, touch[tp], cS - sw / 2, sys_y[s], line, ink, human * .8, rng))
    b.append(edge(cT, touch["chat"] + nh / 2, cT, ag[1] - ar, accent, accent, 1.4, rng, opacity=.45))
    for s in ("CRM", "data", "ops", "billing"):
        b.append(edge(ag[0] + ar, ag[1], cS - sw / 2, sys_y[s], accent, accent, 1.6, rng, opacity=.45))
    # the agent checks back with a person: human in the loop
    b.append(edge(ag[0] - ar, ag[1], cP, people["p2"] + pr, accent, accent, 2.2, rng, opacity=.7, dashed=True))

    for y in people.values():
        b.append(person(cP, y, ink, r=pr))
    for nodes, cx, w in ((touch, cT, tw), (sys_y, cS, sw)):
        for name, y in nodes.items():
            b.append(
                f'<rect x="{cx - w / 2}" y="{y - nh / 2}" width="{w}" height="{nh}" rx="10" fill="none" stroke="{ink}" stroke-opacity=".55" stroke-width="1.5"/>'
                + text(name, cx, y + 6, fs, 500, ink, anchor="middle")
            )
    b.append(agent(*ag, accent, r=ar))
    b.append(text("agent", ag[0], ag[1] + ar + 28, 17, 600, accent, tracking=.5, anchor="middle"))
    b.append(text("asks first", 752, 389, 15, 500, accent, tracking=.3, anchor="middle"))

    return svg(W, H, "".join(b), "Wessel van der Vlugt, solutions architect. Mapping where people meet systems. Now systems act too.")


# ---------------------------------------------------------------- side projects on the autonomy axis

# Left to right: how much of the work the system does on its own.
PROJECTS = [
    ("pokeum", "pokeum", "it recognises the card, you decide"),
    ("mtgf", "mtgf", "people and agents share one search"),
    ("piikey", "piikey", "keeps your data out of AI chats"),
    ("ordo", "ordo", "agents coordinate, you steer"),
]


def work(t: dict) -> str:
    W, H = 1200, 300
    ink, muted, accent = t["ink"], t["muted"], t["accent"]
    ax1, ax2, y = 110, 1090, 150
    xs = [290, 520, 750, 960]
    L = 64
    b = [
        "<defs>"
        f'<linearGradient id="axis" x1="{ax1}" x2="{ax2}" gradientUnits="userSpaceOnUse">'
        f'<stop offset="0" stop-color="{accent}" stop-opacity=".15"/><stop offset="1" stop-color="{accent}"/></linearGradient>'
        "</defs>",
        f'<line x1="{ax1}" y1="{y}" x2="{ax2}" y2="{y}" stroke="url(#axis)" stroke-width="3" stroke-linecap="round"/>',
        person(56, y, ink, r=28),
        agent(1144, y, accent, r=28),
        text("people do the work", 28, 100, 15, 600, muted, tracking=.3),
        text("systems do the work", 1172, 100, 15, 600, accent, tracking=.3, anchor="end"),
    ]
    for (slug, name, phrase), cx in zip(PROJECTS, xs):
        ly = 34
        if slug in ("mtgf", "ordo"):
            b.append(png_mark(slug, cx - L / 2, ly, L, ink))
        else:
            b.append(vector_mark(POKEUM if slug == "pokeum" else PIIKEY, cx - L / 2, ly, L, ink))
        b.append(f'<line x1="{cx}" y1="{ly + L + 8}" x2="{cx}" y2="{y - 10}" stroke="{ink}" stroke-opacity=".25" stroke-width="1.5"/>')
        b.append(f'<circle cx="{cx}" cy="{y}" r="6" fill="{accent}"/>')
        b.append(text(name, cx, y + 52, 27, 700, ink, tracking=-.4, anchor="middle"))
        for i, s in enumerate(wrap(phrase, 20, 400, 215)):
            b.append(text(s, cx, y + 84 + i * 27, 20, 400, muted, anchor="middle"))
    alt = "Side projects on an axis from people doing the work to systems doing the work: " + "; ".join(
        f"{n}: {p}" for _, n, p in PROJECTS
    )
    return svg(W, H, "".join(b), alt)


# ---------------------------------------------------------------- build


def main() -> None:
    OUT.mkdir(exist_ok=True)
    for old in OUT.glob("*.svg"):
        old.unlink()
    for name, t in THEMES.items():
        (OUT / f"hero-{name}.svg").write_text(hero(t), encoding="utf-8")
        (OUT / f"work-{name}.svg").write_text(work(t), encoding="utf-8")
    for f in sorted(OUT.glob("*.svg")):
        print(f"{f.stat().st_size / 1024:6.1f} KB  {f.name}")


if __name__ == "__main__":
    main()
