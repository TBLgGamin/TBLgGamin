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
from xml.sax.saxutils import escape

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
OUT = ROOT.parent / "assets"

THEMES = {
    "light": {"ink": "#0A0A0A", "muted": "#737373", "line2": "#D4D4D4", "accent": "#6F49B1", "on_accent": "#FFFFFF"},
    "dark": {"ink": "#FAFAFA", "muted": "#A1A1A1", "line2": "#3A3A3A", "accent": "#D6C9F9", "on_accent": "#0A0A0A"},
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
        f"<title>{escape(title)}</title>{STYLE}{body}</svg>\n"
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
        + text("·  IT CONSULTANT & ARCHITECT", x0 + text_width("WESSEL VAN DER VLUGT", 15, 600, 2.4) + 12, 188, 15, 600, accent, tracking=2.4)
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

    return svg(W, H, "".join(b), "Wessel van der Vlugt, IT consultant and solution architecture. Mapping where people meet systems. Now systems act too.")


# ---------------------------------------------------------------- project cards

# GitHub shows README SVGs as <img>, so links inside an SVG never work: every card and
# button is its own image, wrapped in a link in README.md.
PROJECTS = [
    {
        "slug": "mtgf",
        "url": "mtgf.net",
        "desc": "Magic: The Gathering search, deck builder and 3D playtest. Search in plain language; AI agents can use it through MCP.",
        "tags": "NUXT · CLICKHOUSE · ONNX · MCP",
    },
    {
        "slug": "ordo",
        "url": "ordo.wena.one",
        "desc": "Tiling terminal for running many shells and AI agents side by side, with a shared channel so the agents can coordinate.",
        "tags": "TYPESCRIPT · BUN · MCP",
    },
    {
        "slug": "piikey",
        "url": "github.com/TBLgGamin/piikey",
        "desc": "Finds your personal data on your PC and masks it before it reaches AI chats. Runs locally, in the background.",
        "tags": "RUST · WINUI 3 · DIRECTML",
    },
    {
        "slug": "pokeum",
        "url": "github.com/TBLgGamin/pokeum",
        "desc": "Point your phone at a Pokémon card and get the exact printing. Self-hosted, no account, nothing sent to a cloud.",
        "tags": "PYTHON · DINOV2 · VUE PWA",
    },
]


def arrow(x: float, y: float, s: float, stroke: str, w: float = 2) -> str:
    """↗ with (x, y) the bottom-left corner of an s×s box."""
    return (
        f'<path fill="none" stroke="{stroke}" stroke-width="{w}" stroke-linecap="round" stroke-linejoin="round" '
        f'd="M{x} {y}L{x + s} {y - s}M{x + s * 0.3:.1f} {y - s}H{x + s}V{y - s * 0.3:.1f}"/>'
    )


def logo_tile(slug: str, x: float, y: float, size: float, accent: str) -> str:
    out = f'<rect x="{x}" y="{y}" width="{size}" height="{size}" rx="{size * .26:.0f}" fill="{accent}" fill-opacity=".14"/>'
    m = size * .64
    mx, my = x + (size - m) / 2, y + (size - m) / 2
    if slug in ("mtgf", "ordo"):
        return out + png_mark(slug, mx, my, m, accent)
    return out + vector_mark(POKEUM if slug == "pokeum" else PIIKEY, mx, my, m, accent)


def card(p: dict, t: dict) -> str:
    W, H = 600, 300
    ink, muted, line, accent = t["ink"], t["muted"], t["line2"], t["accent"]
    b = [
        "<defs>"
        f'<radialGradient id="g" cx="{W}" cy="0" r="380" gradientUnits="userSpaceOnUse">'
        f'<stop offset="0" stop-color="{accent}" stop-opacity=".14"/><stop offset="1" stop-color="{accent}" stop-opacity="0"/></radialGradient>'
        "</defs>"
        f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="20" fill="url(#g)" stroke="{line}" stroke-width="1.5"/>',
        logo_tile(p["slug"], 36, 36, 76, accent),
        text(p["slug"], 136, 72, 34, 700, ink, tracking=-.8),
        text(p["url"], 136, 104, 18, 500, accent),
        # corner affordance: the whole card is a link
        f'<circle cx="{W - 56}" cy="62" r="22" fill="none" stroke="{line}" stroke-width="1.5"/>',
        arrow(W - 62, 68, 12, ink),
    ]
    for i, s in enumerate(wrap(p["desc"], 21, 400, W - 72)[:3]):
        b.append(text(s, 36, 168 + i * 31, 21, 400, ink))
    b.append(text(p["tags"], 36, 268, 13, 600, muted, tracking=2.2))
    return svg(W, H, "".join(b), f"{p['slug']} ({p['url']}): {p['desc']}")


# ---------------------------------------------------------------- link buttons


def linkedin_icon(x: float, y: float, s: float, bg: str, fg: str) -> str:
    return (
        f'<rect x="{x}" y="{y}" width="{s}" height="{s}" rx="{s * .18:.1f}" fill="{fg}"/>'
        + text("in", x + s / 2, y + s * .8, s * .78, 700, bg, tracking=-.5, anchor="middle")
    )


def button(label: str, icon: str, t: dict) -> str:
    h, pad, ic, gap = 44, 18, 20, 10
    fg, bg = t["on_accent"], t["accent"]
    tw = text_width(label, 17, 600)
    iw = ic * 694 / 436 if icon == "wena" else ic
    w = int(pad + iw + gap + tw + pad)
    icon_svg = wena_mark(pad, (h - ic) / 2, ic, fg) if icon == "wena" else linkedin_icon(pad, (h - ic) / 2, ic, bg, fg)
    b = f'<rect width="{w}" height="{h}" rx="10" fill="{bg}"/>' + icon_svg + text(label, pad + iw + gap, 28.5, 17, 600, fg)
    return svg(w, h, b, label)


# ---------------------------------------------------------------- competences

COMPETENCES = [
    ("BUILD", ["Software development", "System architecture", "AI & ML", "RPA & AI workflows", "DevOps"]),
    ("PEOPLE", ["Stakeholder management", "Change management", "Training & adoption", "Knowledge management"]),
    ("EXPLORING", ["Human–agent interaction", "Reinforcement learning", "Embedded systems", "Sociology"]),
]


def competences(t: dict) -> str:
    W = 1200
    ink, muted, line, accent = t["ink"], t["muted"], t["line2"], t["accent"]
    x0, h, gap, fs, row = 170, 44, 12, 18, 64
    b = []
    for r, (label, chips) in enumerate(COMPETENCES):
        y = r * row
        b.append(text(label, 0, y + 28, 14, 600, accent if label == "EXPLORING" else muted, tracking=2.4))
        x = x0
        for c in chips:
            w = text_width(c, fs, 500) + 36
            dashed = ' stroke-dasharray="5 5"' if label == "EXPLORING" else ""
            stroke = accent if label == "EXPLORING" else line
            b.append(
                f'<rect x="{x + .75:.1f}" y="{y + .75}" width="{w - 1.5:.1f}" height="{h - 1.5}" rx="{h / 2}" fill="none" stroke="{stroke}" stroke-width="1.5"{dashed}/>'
                + text(c, x + 18, y + 28.5, fs, 500, ink)
            )
            x += w + gap
            assert x <= W + gap, f"row {label} overflows: {x:.0f}"
    H = len(COMPETENCES) * row - (row - h)
    alt = "Competences. " + " ".join(f"{l.title()}: {', '.join(c)}." for l, c in COMPETENCES)
    return svg(W, H, "".join(b), alt)


# ---------------------------------------------------------------- build


def main() -> None:
    OUT.mkdir(exist_ok=True)
    for old in OUT.glob("*.svg"):
        old.unlink()
    for name, t in THEMES.items():
        (OUT / f"hero-{name}.svg").write_text(hero(t), encoding="utf-8")
        for p in PROJECTS:
            (OUT / f"card-{p['slug']}-{name}.svg").write_text(card(p, t), encoding="utf-8")
        (OUT / f"competences-{name}.svg").write_text(competences(t), encoding="utf-8")
        (OUT / f"btn-wena-{name}.svg").write_text(button("wena.one", "wena", t), encoding="utf-8")
        (OUT / f"btn-linkedin-{name}.svg").write_text(button("LinkedIn", "linkedin", t), encoding="utf-8")
    for f in sorted(OUT.glob("*.svg")):
        print(f"{f.stat().st_size / 1024:6.1f} KB  {f.name}")


if __name__ == "__main__":
    main()
