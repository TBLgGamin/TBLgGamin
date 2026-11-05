"""Generate the profile README artwork (light + dark SVGs) into ../assets.

Flat and free-form: type, space and one accent. No cards, borders, gradients or shadows.
Text is converted to outlines because GitHub shows SVGs as <img>, which cannot load fonts.
Links inside an SVG never work there, so every clickable thing is its own image.

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
    "light": {"ink": "#0A0A0A", "muted": "#737373", "accent": "#6F49B1"},
    "dark": {"ink": "#FAFAFA", "muted": "#A1A1A1", "accent": "#D6C9F9"},
}

# ---------------------------------------------------------------- content

ROLE = "IT consultant & developer"
LINES = [
    "Where technology, organisations and people meet.",
    "Growing towards solution architecture.",
]

# (period, title, place, state) — state: "done", "now" or "next"
PATH = [
    ("2022 – 2026", "Business IT & Management", "Avans · bachelor", "done"),
    ("2023", "Process improvement", "Weener Plastics", "done"),
    ("2024", "Development intern", "Growrs", "done"),
    ("2025 – now", "Student consultant", "VVA Informatisering", "now"),
    ("2026 – 2028", "Digital Business Transformation", "Open Universiteit · MSc", "now"),
    ("Next", "Solution architect", "", "next"),
]

COMPETENCES = [
    ("BUILD", ["Software development", "System architecture", "AI & machine learning", "RPA & AI workflows", "DevOps & releases"]),
    ("ORGANISE", ["Process analysis & BPMN", "Requirements analysis", "Stakeholder management", "Change management", "Training & adoption"]),
    ("EXPLORING", ["Human–agent interaction", "Reinforcement learning", "Embedded systems", "Sociology"]),
]

PROJECTS = [
    {"slug": "mtgf", "url": "mtgf.net"},
    {"slug": "ordo", "url": "ordo.wena.one"},
    {"slug": "piikey", "url": "GitHub"},
    {"slug": "pokeum", "url": "GitHub"},
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


def svg(w: float, h: float, body: str, title: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:.0f} {h:.0f}" width="{w:.0f}" height="{h:.0f}" role="img">'
        f"<title>{escape(title)}</title>{body}</svg>\n"
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
    return f'<svg x="{x}" y="{y}" width="{h * 694 / 436:.1f}" height="{h}" viewBox="0 0 694 436"><path fill="{fill}" d="{WENA_D}"/></svg>'


def mark(slug: str, x: float, y: float, size: float, fill: str) -> str:
    if slug in ("pokeum", "piikey"):
        inner = (POKEUM if slug == "pokeum" else PIIKEY).format(c=fill)
        return f'<svg x="{x}" y="{y}" width="{size}" height="{size}" viewBox="0 0 256 256">{inner}</svg>'
    # one-colour PNG marks (black on transparent), recoloured to `fill` with alpha kept
    data = base64.b64encode((SRC / f"{slug}-mark.png").read_bytes()).decode()
    r, g, b = (int(fill[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return (
        f'<filter id="ink"><feColorMatrix type="matrix" values="0 0 0 0 {r:.3f}  0 0 0 0 {g:.3f}  0 0 0 0 {b:.3f}  0 0 0 1 0"/></filter>'
        f'<image x="{x}" y="{y}" width="{size}" height="{size}" filter="url(#ink)" href="data:image/png;base64,{data}"/>'
    )


def arrow(x: float, y: float, s: float, stroke: str) -> str:
    """↗ with (x, y) the bottom-left corner of an s×s box."""
    return (
        f'<path fill="none" stroke="{stroke}" stroke-width="{s * .16:.1f}" stroke-linecap="round" stroke-linejoin="round" '
        f'd="M{x} {y}L{x + s} {y - s}M{x + s * .3:.1f} {y - s}H{x + s}V{y - s * .3:.1f}"/>'
    )


# ---------------------------------------------------------------- pieces


def header(t: dict) -> str:
    W, H = 1200, 344
    ink, muted, accent = t["ink"], t["muted"], t["accent"]
    b = [
        wena_mark(0, 24, 40, accent),
        text("Wessel van der Vlugt", -3, 160, 80, 700, ink, tracking=-2.8),
        text(ROLE, 0, 216, 32, 500, accent, tracking=-.4),
    ]
    fits(text_width("Wessel van der Vlugt", 80, 700, -2.8), W, "name")
    for i, s in enumerate(LINES):
        fits(text_width(s, 26, 400), W, "header line")
        b.append(text(s, 0, 288 + i * 40, 26, 400, muted))
    return svg(W, H, "".join(b), f"Wessel van der Vlugt, {ROLE}. " + " ".join(LINES))


def competences(t: dict) -> str:
    W, col, size, lead = 1200, 400, 24, 40
    ink, muted = t["ink"], t["muted"]
    b = []
    for c, (label, items) in enumerate(COMPETENCES):
        x = c * col
        b.append(text(label, x, 16, 15, 600, muted, tracking=2.4))
        for i, s in enumerate(items):
            fits(text_width(s, size, 400), col - 32, s)
            b.append(text(s, x, 64 + i * lead, size, 400, ink))
    H = 64 + (max(len(i) for _, i in COMPETENCES) - 1) * lead + 16
    alt = " ".join(f"{l.title()}: {', '.join(i)}." for l, i in COMPETENCES)
    return svg(W, H, "".join(b), alt)


def path(t: dict) -> str:
    W, col, y = 1200, 200, 56
    ink, muted, accent, bg = t["ink"], t["muted"], t["accent"], t["bg"]
    xs = [8 + i * col for i in range(len(PATH))]
    last_now = max(i for i, p in enumerate(PATH) if p[3] == "now")
    b = [
        f'<line x1="{xs[0]}" y1="{y}" x2="{xs[last_now]}" y2="{y}" stroke="{muted}" stroke-width="2"/>',
        f'<line x1="{xs[last_now]}" y1="{y}" x2="{xs[-1]}" y2="{y}" stroke="{accent}" stroke-width="2" stroke-dasharray="2 8" stroke-linecap="round"/>',
    ]
    bottom = 0.0
    for x, (period, title, place, state) in zip(xs, PATH):
        lx = x - 8
        if state == "done":
            b.append(f'<circle cx="{x}" cy="{y}" r="6" fill="{ink}"/>')
        elif state == "now":
            b.append(f'<circle cx="{x}" cy="{y}" r="8" fill="{accent}"/>')
        else:
            b.append(f'<circle cx="{x}" cy="{y}" r="8" fill="{bg}" stroke="{accent}" stroke-width="2.5"/>')
        b.append(text(period.upper(), lx, 20, 14, 600, accent if state != "done" else muted, tracking=1.6))
        ty = 108
        for s in wrap(title, 22, 600, col - 24):
            b.append(text(s, lx, ty, 22, 600, accent if state == "next" else ink, tracking=-.3))
            ty += 30
        for s in wrap(place, 18, 400, col - 24) if place else []:
            b.append(text(s, lx, ty + 2, 18, 400, muted))
            ty += 26
        bottom = max(bottom, ty)
    alt = "Path: " + "; ".join(f"{p}: {ti}{', ' + pl if pl else ''}" for p, ti, pl, _ in PATH) + "."
    return svg(W, bottom - 6, "".join(b), alt)


def project(p: dict, t: dict) -> str:
    W, H, M = 280, 196, 80
    ink, accent = t["ink"], t["accent"]
    cx = W / 2
    nw = text_width(p["slug"], 30, 700, -.6)
    uw = text_width(p["url"], 20, 500) + 8 + 12
    b = [
        mark(p["slug"], cx - M / 2, 0, M, ink),
        text(p["slug"], cx - nw / 2, 136, 30, 700, ink, tracking=-.6),
        text(p["url"], cx - uw / 2, 174, 20, 500, accent),
        arrow(cx - uw / 2 + uw - 12, 172, 12, accent),
    ]
    return svg(W, H, "".join(b), f"{p['slug']} ({p['url']})")


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
        t = {**t, "bg": "#FFFFFF" if name == "light" else "#0D1117"}
        (OUT / f"header-{name}.svg").write_text(header(t), encoding="utf-8")
        (OUT / f"path-{name}.svg").write_text(path(t), encoding="utf-8")
        (OUT / f"competences-{name}.svg").write_text(competences(t), encoding="utf-8")
        for p in PROJECTS:
            (OUT / f"project-{p['slug']}-{name}.svg").write_text(project(p, t), encoding="utf-8")
        for icon, label in LINKS:
            (OUT / f"link-{icon}-{name}.svg").write_text(link(icon, label, t), encoding="utf-8")
    for f in sorted(OUT.glob("*.svg")):
        print(f"{f.stat().st_size / 1024:6.1f} KB  {f.name}")


if __name__ == "__main__":
    main()
