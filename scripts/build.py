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

BUILDING_LINE = "Side projects where people and AI share the work."

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


STYLE = """<style>
.pop{transform-box:fill-box;transform-origin:center;animation:pop .8s cubic-bezier(.34,1.56,.64,1) both;animation-delay:var(--o,0s)}
@keyframes pop{from{opacity:0;transform:scale(.3)}to{opacity:1;transform:none}}
.breathe{transform-box:fill-box;transform-origin:center;animation:breathe 4s ease-in-out 1.2s infinite}
@keyframes breathe{50%{transform:scale(1.05) rotate(-2deg)}}
.draw{stroke-dasharray:100;stroke-dashoffset:100;animation:draw 1s cubic-bezier(.2,.7,.2,1) forwards;animation-delay:var(--o,0s)}
@keyframes draw{to{stroke-dashoffset:0}}
.pulse{stroke-dasharray:4 96;stroke-dashoffset:100;opacity:0;animation:pulse 2.6s linear infinite;animation-delay:var(--o,0s)}
@keyframes pulse{0%{stroke-dashoffset:100;opacity:1}90%{opacity:1}100%{stroke-dashoffset:0;opacity:0}}
.spin{animation:spin 24s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
.rise{opacity:0;animation:rise .8s cubic-bezier(.2,.7,.2,1) forwards;animation-delay:var(--o,0s)}
@keyframes rise{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:none}}
@media (prefers-reduced-motion:reduce){.pop,.breathe,.spin,.rise{animation:none;opacity:1}.draw{animation:none;stroke-dashoffset:0}.pulse{display:none}}
</style>"""


def svg(w: float, h: float, body: str, title: str, animated: bool = False) -> str:
    style = STYLE if animated else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:.0f} {h:.0f}" width="{w:.0f}" height="{h:.0f}" role="img">'
        f"<title>{escape(title)}</title>{style}{body}</svg>\n"
    )


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


def hero(t: dict) -> str:
    W, H = 1200, 520
    ink, muted, faint, accent, bg = t["ink"], t["muted"], t["faint"], t["accent"], t["bg"]
    b = []

    # left: words
    x0 = 0
    for i, (s, tone) in enumerate(HEADLINE):
        fits(text_width(s, 64, 700, -2), 560, s)
        b.append(f'<g class="rise" style="--o:{.2 + i * .1:.1f}s">' + text(s, x0 - 3, 184 + i * 72, 64, 700, t[tone], tracking=-2) + "</g>")
    sub = wrap(SUBLINE, 24, 400, 500)
    b.append(
        '<g class="rise" style="--o:.6s">'
        + "".join(text(s, x0, 390 + i * 36, 24, 400, muted) for i, s in enumerate(sub))
        + "</g>"
    )

    # right: the wena mark at the centre, the things it builds around it
    cx, cy = 920, 260
    orbit = 150
    b.append(
        f'<g class="spin" style="transform-origin:{cx}px {cy}px">'
        f'<circle cx="{cx}" cy="{cy}" r="{orbit}" fill="none" stroke="{faint}" stroke-width="1.5" stroke-dasharray="2 10" stroke-linecap="round"/>'
        f'<circle cx="{cx + orbit}" cy="{cy}" r="6" fill="{accent}"/>'
        f'<circle cx="{cx - orbit * .5:.1f}" cy="{cy - orbit * .866:.1f}" r="4" fill="{ink}"/>'
        f'<circle cx="{cx - orbit * .5:.1f}" cy="{cy + orbit * .866:.1f}" r="4" fill="{muted}"/>'
        "</g>"
    )

    M = 64
    spots = [(690, 70), (1150, 70), (690, 450), (1150, 450)]
    for i, ((px, py), p) in enumerate(zip(spots, PROJECTS)):
        sx = cx + (-70 if px < cx else 70)
        ex = px + (M / 2 + 14 if px < cx else -(M / 2 + 14))
        d = f"M{sx} {cy}C{sx + (ex - sx) * .6:.0f} {cy} {ex} {cy + (py - cy) * .4:.0f} {ex} {py}"
        o = .9 + i * .15
        b.append(f'<path class="draw" style="--o:{o:.2f}s" pathLength="100" d="{d}" fill="none" stroke="{faint}" stroke-width="2" stroke-linecap="round"/>')
        b.append(f'<path class="pulse" style="--o:{2 + i * .65:.2f}s" pathLength="100" d="{d}" fill="none" stroke="{accent}" stroke-width="4" stroke-linecap="round"/>')
        b.append(f'<g class="pop" style="--o:{1.3 + i * .15:.2f}s">{mark(p["slug"], px - M / 2, py - M / 2, M, ink)}</g>')

    wh = 120
    ww = wh * 694 / 436
    b.append(
        f'<g class="pop" style="--o:.3s"><g class="breathe">'
        f'<circle cx="{cx}" cy="{cy}" r="{ww / 2 + 12:.0f}" fill="{bg}"/>'
        f"{wena_mark(cx - ww / 2, cy - wh / 2, wh, accent)}</g></g>"
    )

    alt = f"{' '.join(s for s, _ in HEADLINE)} {SUBLINE} Animation: the wena logo connected to mtgf, ordo, piikey and pokeum."
    return svg(W, H, "".join(b), alt, animated=True)


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
    W = 1200
    return svg(W, 72, eyebrow("BUILDING", 0, 18, t) + text(BUILDING_LINE, 0, 64, 26, 400, t["ink"]), f"Building. {BUILDING_LINE}")


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
