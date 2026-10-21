"""Shared figure style for the J713 bring-up record. Standard library only.

Every figure in this repository is drawn through this module, so all of them share:
  - one width (960 user units, about GitHub's README width) and one type scale,
  - GitHub's own system font stacks (no web fonts, nothing to install),
  - one colour logic: a series colour means one thing everywhere; context data is drawn lighter,
  - GitHub's own Primer red and blue, checked for colour-vision deficiency and contrast in both themes,
  - a plain descriptive title; the finding, definitions and source paths go in the README caption,
  - a light and a dark variant of the same layout, for GitHub's two themes.

A figure is a function draw(fig) that only places marks; numbers come from data/ files written by
analysis/ scripts, never from the figure script itself.
"""
from pathlib import Path

WIDTH = 960
SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif"
MONO = "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace"

# type scale (user units; at README width 1 unit is about 0.86 px)
SIZE = {"title": 18, "subtitle": 13, "panel": 12.5, "label": 12, "small": 11, "overline": 11}
CONTEXT_OPACITY = 0.55   # boots/points outside the comparison a figure is making: behind, still readable

THEMES = {
    "light": {"bg": "#ffffff", "ink": "#1f2328", "soft": "#424a53", "muted": "#6e7781", "rule": "#d8dee4",
              "band": "#f6f8fa", "red": "#d1242f", "blue": "#0969da", "grey": "#8c959f"},
    "dark": {"bg": "#0d1117", "ink": "#e6edf3", "soft": "#c9d1d9", "muted": "#8b949e", "rule": "#30363d",
             "band": "#161b22", "red": "#f85149", "blue": "#4493f8", "grey": "#6e7681"},
}
# What each series colour means across all figures. A new figure reuses these before adding any.
MEANING = {"red": "the failing / original configuration", "blue": "the fixed / changed configuration",
           "grey": "counts and neutral quantities"}


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def text_width(s, size, mono=False):
    """Rough advance width, used only to catch labels that would overflow."""
    return len(str(s)) * size * (0.61 if mono else 0.56)


class Figure:
    def __init__(self, theme, height, title, desc):
        self.t, self.h, self.marks = THEMES[theme], height, []
        self.title, self.desc = title, desc

    def c(self, role):
        return self.t.get(role, role)

    def text(self, x, y, s, size="label", role="ink", anchor="start", mono=False, weight=400, italic=False,
             spacing=0, opacity=1, halo=False):
        px = SIZE.get(size, size)
        w = text_width(s, px, mono) + spacing * len(str(s))
        left = x - (w if anchor == "end" else w / 2 if anchor == "middle" else 0)
        assert left >= 0 and left + w <= WIDTH + 2, f"label overflows the figure: {s!r}"
        attrs = [f'x="{x:.1f}"', f'y="{y:.1f}"', f'font-family="{MONO if mono else SANS}"', f'font-size="{px}"',
                 f'fill="{self.c(role)}"']
        if anchor != "start":
            attrs.append(f'text-anchor="{anchor}"')
        if weight != 400:
            attrs.append(f'font-weight="{weight}"')
        if italic:
            attrs.append('font-style="italic"')
        if spacing:
            attrs.append(f'letter-spacing="{spacing}"')
        if opacity != 1:
            attrs.append(f'opacity="{opacity}"')
        if halo:   # background-coloured outline so a label stays legible over grid lines
            attrs.append(f'stroke="{self.c("bg")}" stroke-width="4" stroke-linejoin="round" paint-order="stroke"')
        self.marks.append(f'<text {" ".join(attrs)}>{esc(s)}</text>')

    def line(self, x1, y1, x2, y2, role="rule", width=1, opacity=1):
        self.marks.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{self.c(role)}" '
                          f'stroke-width="{width}"' + (f' opacity="{opacity}"' if opacity != 1 else "") + "/>")

    def rect(self, x, y, w, h, role, opacity=1):
        self.marks.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{self.c(role)}"'
                          + (f' opacity="{opacity}"' if opacity != 1 else "") + "/>")

    def dot(self, x, y, role, r=6, opacity=1):
        self.marks.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{self.c(role)}" stroke="{self.c("bg")}" '
                          f'stroke-width="2"' + (f' opacity="{opacity}"' if opacity != 1 else "") + "/>")

    def path(self, d, role="soft", width=1.2, fill="none"):
        self.marks.append(f'<path d="{d}" fill="{fill}" stroke="{self.c(role)}" stroke-width="{width}" '
                          'stroke-linejoin="round" stroke-linecap="round"/>')

    def polyline(self, pts, role="rule", width=1.2):
        p = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        self.marks.append(f'<polyline points="{p}" fill="none" stroke="{self.c(role)}" stroke-width="{width}" '
                          'stroke-linejoin="round"/>')

    def svg(self):
        head = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {self.h}" width="{WIDTH}" '
                f'height="{self.h}" role="img" aria-labelledby="t d">'
                f'<title id="t">{esc(self.title)}</title><desc id="d">{esc(self.desc)}</desc>'
                f'<rect width="{WIDTH}" height="{self.h}" fill="{self.c("bg")}"/>')
        return head + "\n" + "\n".join(self.marks) + "\n</svg>\n"


def render(draw, name, height, title, desc, out_dir):
    """Draw the same figure in both themes: <name>-light.svg and <name>-dark.svg."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for theme in THEMES:
        fig = Figure(theme, height, title, desc)
        draw(fig)
        (out_dir / f"{name}-{theme}.svg").write_text(fig.svg())
