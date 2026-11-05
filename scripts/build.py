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
    "light": {
        "ink": "#0A0A0A",
        "muted": "#737373",
        "line": "#E5E5E5",
        "line2": "#D4D4D4",
        "accent": "#6F49B1",
        "mtgf": "black",
    },
    "dark": {
        "ink": "#FAFAFA",
        "muted": "#A1A1A1",
        "line": "#2E2E2E",
        "line2": "#404040",
        "accent": "#D6C9F9",
        "mtgf": "white",
    },
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


def text(
    s: str,
    x: float,
    y: float,
    size: float,
    weight: int = 400,
    fill: str = "currentColor",
    tracking: float = 0,
    anchor: str = "start",
    cls: str = "",
) -> str:
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
    c = f' class="{cls}"' if cls else ""
    return f'<path{c} fill="{fill}" d="{pen.getCommands()}"/>'


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
MTGF_PNG = base64.b64encode((SRC / "mtgf-mark.png").read_bytes()).decode()

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


def mtgf_mark(x: float, y: float, size: float, tone: str) -> str:
    # The mark is black ink; on dark it flips to white (never recoloured to the accent).
    flt = ""
    if tone == "white":
        flt = ' filter="url(#toWhite)"'
    return (
        '<filter id="toWhite"><feColorMatrix type="matrix" values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 1 0"/></filter>'
        f'<image x="{x}" y="{y}" width="{size}" height="{size}"{flt} href="data:image/png;base64,{MTGF_PNG}"/>'
    )


def person(cx: float, cy: float, stroke: str, r: float = 24) -> str:
    return (
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{stroke}" stroke-width="1.5"/>'
        f'<circle cx="{cx}" cy="{cy - r * 0.27:.1f}" r="{r * 0.27:.1f}" fill="{stroke}"/>'
        f'<path fill="{stroke}" d="M{cx - r * 0.5:.1f} {cy + r * 0.5:.1f}a{r * 0.5:.1f} {r * 0.42:.1f} 0 0 1 {r:.1f} 0z"/>'
    )


def agent(cx: float, cy: float, accent: str, r: float = 24, halo: bool = True) -> str:
    out = ""
    if halo:
        out += f'<circle class="halo" cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{accent}" stroke-width="1.5"/>'
    out += (
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{accent}" fill-opacity=".12" stroke="{accent}" stroke-width="1.5"/>'
        f'<circle cx="{cx}" cy="{cy}" r="{r * 0.3:.1f}" fill="{accent}"/>'
    )
    for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
        out += f'<circle cx="{cx + dx * r * 0.62:.1f}" cy="{cy + dy * r * 0.62:.1f}" r="{r * 0.09:.1f}" fill="{accent}"/>'
    return out


def arrow(x: float, y: float, s: float, stroke: str) -> str:
    """↗, (x, y) = bottom-left corner of an s×s box."""
    return (
        f'<path fill="none" stroke="{stroke}" stroke-width="{s * 0.14:.1f}" stroke-linecap="round" stroke-linejoin="round" '
        f'd="M{x} {y}L{x + s} {y - s}M{x + s * 0.3:.1f} {y - s}H{x + s}V{y - s * 0.3:.1f}"/>'
    )


STYLE = """
<style>
.p{stroke-dasharray:5 95;animation:flow var(--d,3s) linear infinite;animation-delay:var(--o,0s)}
@keyframes flow{from{stroke-dashoffset:100}to{stroke-dashoffset:0}}
.halo{transform-box:fill-box;transform-origin:center;animation:halo 2.4s ease-out infinite}
@keyframes halo{from{transform:scale(1);opacity:.7}to{transform:scale(1.9);opacity:0}}
.slide{animation:slide 9s cubic-bezier(.65,0,.35,1) infinite alternate}
@keyframes slide{from{transform:translateX(0)}to{transform:translateX(var(--run))}}
.rise{opacity:0;animation:rise .9s cubic-bezier(.2,.7,.2,1) forwards;animation-delay:var(--o,0s)}
@keyframes rise{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
@media (prefers-reduced-motion:reduce){.p{display:none}.halo,.slide{animation:none}.rise{animation:none;opacity:1}}
</style>"""


def svg(w: int, h: int, body: str, title: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img">'
        f"<title>{title}</title>{STYLE}{body}</svg>\n"
    )


# ---------------------------------------------------------------- hero


def edge(x1, y1, x2, y2, stroke, pulse, dur, opacity=1.0, dashed=False, rng=None) -> str:
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
    W, H = 1200, 520
    ink, muted, line, accent = t["ink"], t["muted"], t["line2"], t["accent"]
    b = []

    # glow + dot field behind the landscape (marketing surface: same-hue only)
    b.append(
        "<defs>"
        f'<radialGradient id="glow" cx="900" cy="270" r="250" gradientUnits="userSpaceOnUse">'
        f'<stop offset="0" stop-color="{accent}" stop-opacity=".16"/><stop offset="1" stop-color="{accent}" stop-opacity="0"/></radialGradient>'
        f'<radialGradient id="fade" cx="900" cy="270" r="260" gradientUnits="userSpaceOnUse">'
        '<stop offset=".55" stop-color="#fff"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>'
        f'<mask id="dotmask"><rect width="{W}" height="{H}" fill="url(#fade)"/></mask>'
        f'<pattern id="dots" width="22" height="22" patternUnits="userSpaceOnUse"><circle cx="11" cy="11" r="1.1" fill="{muted}" fill-opacity=".35"/></pattern>'
        "</defs>"
        f'<rect x="560" width="{W - 560}" height="{H}" fill="url(#glow)"/>'
        f'<rect x="580" y="20" width="{W - 600}" height="{H - 40}" fill="url(#dots)" mask="url(#dotmask)"/>'
    )

    # left: identity
    x0 = 40
    b.append(f'<g class="rise" style="--o:.05s">{wena_mark(x0, 52, 30, accent)}</g>')
    b.append(
        f'<g class="rise" style="--o:.15s">'
        + text("WESSEL VAN DER VLUGT", x0, 132, 15, 600, muted, tracking=2.4)
        + text("·  SOLUTIONS ARCHITECT", x0 + text_width("WESSEL VAN DER VLUGT", 15, 600, 2.4) + 12, 132, 15, 600, accent, tracking=2.4)
        + "</g>"
    )
    head = [("Mapping where people", ink), ("meet systems.", ink), ("Now systems act too.", accent)]
    for i, (s, c) in enumerate(head):
        b.append(f'<g class="rise" style="--o:{.25 + i * .1:.2f}s">' + text(s, x0 - 2, 202 + i * 60, 52, 700, c, tracking=-1.6) + "</g>")
    sub = (
        "I design application landscapes and the interaction points between people and the systems they rely on. "
        "Lately: the growing handoff between humans and autonomous systems."
    )
    sub_lines = wrap(sub, 21, 400, 540)
    b.append(
        '<g class="rise" style="--o:.6s">'
        + "".join(text(s, x0, 380 + i * 31, 21, 400, muted) for i, s in enumerate(sub_lines))
        + "</g>"
    )

    # right: an application landscape, columns people → touchpoints → systems, with an agent lane
    cP, cT, cS = 700, 878, 1084
    for label, cx in (("PEOPLE", cP), ("TOUCHPOINTS", cT), ("SYSTEMS", cS)):
        b.append(text(label, cx, 72, 14, 600, muted, tracking=2.2, anchor="middle"))

    people = {"p1": 175, "p2": 315}
    touch = {"app": 135, "portal": 210, "chat": 285}
    systems = ["CRM", "ERP", "data", "identity", "ops", "billing"]
    sys_y = {s: 120 + i * 62 for i, s in enumerate(systems)}
    ag = (cT, 410)
    tw, sw, nh, pr, ar, fs = 116, 124, 40, 28, 28, 17

    edges = []
    human = 3.4
    for p, tps in (("p1", ["app", "portal"]), ("p2", ["portal", "chat"])):
        for tp in tps:
            edges.append(edge(cP + pr + 1, people[p], cT - tw / 2, touch[tp], line, ink, human, rng=rng))
    for tp, ss in (("app", ["CRM", "data"]), ("portal", ["ERP", "identity"])):
        for s in ss:
            edges.append(edge(cT + tw / 2, touch[tp], cS - sw / 2, sys_y[s], line, ink, human * .8, rng=rng))
    edges.append(edge(cT, touch["chat"] + nh / 2, cT, ag[1] - ar, accent, accent, 1.4, opacity=.45, rng=rng))
    for s in ("CRM", "data", "ops", "billing"):
        edges.append(edge(ag[0] + ar, ag[1], cS - sw / 2, sys_y[s], accent, accent, 1.6, opacity=.45, rng=rng))
    # the agent checks back with a person: human in the loop
    edges.append(edge(ag[0] - ar, ag[1], cP, people["p2"] + pr, accent, accent, 2.2, opacity=.7, dashed=True, rng=rng))
    b.extend(edges)

    for p, y in people.items():
        b.append(person(cP, y, ink, r=pr))
    for name, y in touch.items():
        b.append(
            f'<rect x="{cT - tw / 2}" y="{y - nh / 2}" width="{tw}" height="{nh}" rx="10" fill="none" stroke="{ink}" stroke-opacity=".55" stroke-width="1.5"/>'
            + text(name, cT, y + 6, fs, 500, ink, anchor="middle")
        )
    for s, y in sys_y.items():
        b.append(
            f'<rect x="{cS - sw / 2}" y="{y - nh / 2}" width="{sw}" height="{nh}" rx="10" fill="none" stroke="{ink}" stroke-opacity=".55" stroke-width="1.5"/>'
            + text(s, cS, y + 6, fs, 500, ink, anchor="middle")
        )
    b.append(agent(*ag, accent, r=ar))
    b.append(text("agent", ag[0], ag[1] + ar + 28, 17, 600, accent, tracking=.5, anchor="middle"))
    b.append(text("asks first", 752, 404, 15, 500, accent, tracking=.3, anchor="middle"))

    return svg(W, H, "".join(b), "Wessel van der Vlugt, solutions architect. Mapping where people meet systems. Now systems act too.")


# ---------------------------------------------------------------- autonomy spectrum


def spectrum(t: dict) -> str:
    W, H = 1200, 280
    ink, muted, line, accent = t["ink"], t["muted"], t["line2"], t["accent"]
    x1, x2, y = 200, 1000, 124
    stops = [
        ("manual", "you do it"),
        ("assisted", "it helps you"),
        ("suggested", "it proposes"),
        ("approved", "it acts, you approve"),
        ("autonomous", "it acts, you audit"),
    ]
    step = (x2 - x1) / (len(stops) - 1)
    b = [
        "<defs>"
        f'<linearGradient id="track" x1="{x1}" x2="{x2}" gradientUnits="userSpaceOnUse">'
        f'<stop offset="0" stop-color="{accent}" stop-opacity=".15"/><stop offset="1" stop-color="{accent}"/></linearGradient>'
        "</defs>",
        f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" stroke="url(#track)" stroke-width="4" stroke-linecap="round"/>',
        person(56, y, ink, r=28),
        agent(1140, y, accent, r=28),
    ]
    for i, (lab, sub) in enumerate(stops):
        cx = x1 + i * step
        b.append(f'<circle cx="{cx}" cy="{y}" r="7" fill="{accent}" fill-opacity="{.35 + .65 * i / 4:.2f}"/>')
        b.append(text(lab, cx, y - 34, 27, 600, ink, tracking=-.5, anchor="middle"))
        b.append(text(sub, cx, y + 48, 19, 400, muted, anchor="middle"))
    # moving marker: where a given interaction point currently sits
    run = x2 - x1
    b.append(
        f'<g class="slide" style="--run:{run}px">'
        f'<circle cx="{x1}" cy="{y}" r="15" fill="{accent}" fill-opacity=".18"/>'
        f'<circle cx="{x1}" cy="{y}" r="8" fill="{accent}"/></g>'
    )
    # bracket: where the design work is
    bx1, bx2, by = x1 + step, x1 + 3 * step, 220
    b.append(
        f'<path d="M{bx1} {by - 8}V{by}H{bx2}V{by - 8}" fill="none" stroke="{accent}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>'
        + text("where the architecture decisions live", (bx1 + bx2) / 2, by + 34, 19, 600, accent, tracking=.3, anchor="middle")
    )
    return svg(W, H, "".join(b), "Autonomy spectrum: manual, assisted, suggested, approved, autonomous.")


# ---------------------------------------------------------------- project rows

PROJECTS = [
    {
        "slug": "mtgf",
        "name": "mtgf",
        "url": "mtgf.net",
        "desc": "Magic: The Gathering card search that understands plain language, with an MCP server so AI agents can use it as well as people.",
        "stack": "NUXT 4 · CLICKHOUSE · ONNX · MCP",
        "logo": "mtgf",
    },
    {
        "slug": "pokeum",
        "name": "pokeum",
        "url": "github.com/TBLgGamin/pokeum",
        "desc": "Point a phone at a Pokémon card and it names the exact printing. Recognition runs on your own server, with no account and nothing sent to a cloud.",
        "stack": "PYTHON · DINOV2 · ONNX · VUE PWA",
        "logo": "pokeum",
    },
    {
        "slug": "piikey",
        "name": "piikey",
        "url": "github.com/TBLgGamin/piikey",
        "desc": "Sits between you and AI chats on your PC and swaps your personal data for stand-ins before it leaves the machine.",
        "stack": "RUST · WINUI 3 · DIRECTML · LOCAL PROXY",
        "logo": "piikey",
    },
]


def project(p: dict, t: dict) -> str:
    W, H = 1000, 156
    ink, muted, accent = t["ink"], t["muted"], t["accent"]
    b = []
    L, ly = 92, 22
    if p["logo"] == "mtgf":
        b.append(mtgf_mark(0, ly, L, t["mtgf"]))
    else:
        inner = (POKEUM if p["logo"] == "pokeum" else PIIKEY).format(c=accent)
        b.append(f'<svg x="0" y="{ly}" width="{L}" height="{L}" viewBox="0 0 256 256">{inner}</svg>')
    x = 124
    b.append(text(p["name"], x, 56, 32, 700, ink, tracking=-.8))
    ux = x + text_width(p["name"], 32, 700, -.8) + 16
    b.append(text(p["url"], ux, 56, 17, 500, accent))
    b.append(arrow(ux + text_width(p["url"], 17, 500) + 8, 54, 11, accent))
    for i, s in enumerate(wrap(p["desc"], 19, 400, W - x - 10)):
        b.append(text(s, x, 90 + i * 26, 19, 400, ink))
    b.append(text(p["stack"], x, 146, 12, 600, muted, tracking=2))
    return svg(W, H, "".join(b), f"{p['name']} ({p['url']}): {p['desc']}")


# ---------------------------------------------------------------- link pills

LINKS = [("wena.one", "portfolio"), ("mtgf.net", "project"), ("LinkedIn", "profile")]


def pill(label: str, t: dict) -> str:
    h, pad = 48, 20
    tw = text_width(label, 18, 600)
    w = int(pad + tw + 10 + 12 + pad)
    b = (
        f'<rect x=".75" y=".75" width="{w - 1.5}" height="{h - 1.5}" rx="10" fill="none" stroke="{t["line2"]}" stroke-width="1.5"/>'
        + text(label, pad, 30.5, 18, 600, t["ink"])
        + arrow(pad + tw + 10, 30, 11, t["accent"])
    )
    return svg(w, h, b, label)


# ---------------------------------------------------------------- build


def main() -> None:
    OUT.mkdir(exist_ok=True)
    for name, t in THEMES.items():
        (OUT / f"hero-{name}.svg").write_text(hero(t), encoding="utf-8")
        (OUT / f"spectrum-{name}.svg").write_text(spectrum(t), encoding="utf-8")
        for p in PROJECTS:
            (OUT / f"project-{p['slug']}-{name}.svg").write_text(project(p, t), encoding="utf-8")
        for label, _ in LINKS:
            slug = label.lower().replace(".", "-")
            (OUT / f"link-{slug}-{name}.svg").write_text(pill(label, t), encoding="utf-8")
    for f in sorted(OUT.glob("*.svg")):
        print(f"{f.stat().st_size / 1024:6.1f} KB  {f.name}")


if __name__ == "__main__":
    main()
