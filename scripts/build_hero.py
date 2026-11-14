#!/usr/bin/env python3
"""Build the profile hero: a wireframe icosahedron turning in real 3D.

The solid is defined in 3D, spun one full turn about a tilted axis, projected
with perspective, and written out as SMIL keyframes. One full turn means the
last frame equals the first, so the loop has no seam. A smaller dual
(dodecahedron) turns the other way inside it in the accent colour.

Writes assets/hero-dark.svg and assets/hero-light.svg. Standard library only.

    python3 scripts/build_hero.py
"""

from __future__ import annotations

import math
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"

W, H = 600, 332          # viewBox; narrow so the text stays readable on phones
CX, CY = W / 2, 124.0    # centre of the solid
RADIUS = 92.0            # on-screen radius of the outer solid at depth 0
CAMERA = 4.6             # camera distance in solid radii (perspective strength)
FRAMES = 48              # keyframes per turn; linear interpolation in between
TURN_SECONDS = 20        # one full turn
INNER_SCALE = 0.42       # size of the inner dual relative to the outer solid

NAME = "byte4day"
TAGLINE = "Numan Hayder · developer tools, AI agents and Linux desktop software"

THEMES = {
    "dark": {"fg": "#e6edf3", "muted": "#8b949e", "accent": "#e3b341"},
    "light": {"fg": "#1f2328", "muted": "#59636e", "accent": "#9a6700"},
}

Vec = tuple[float, float, float]


# --- geometry ---------------------------------------------------------------

def normalise(v: Vec) -> Vec:
    n = math.sqrt(sum(c * c for c in v))
    return (v[0] / n, v[1] / n, v[2] / n)


def dist(a: Vec, b: Vec) -> float:
    return math.sqrt(sum((p - q) ** 2 for p, q in zip(a, b)))


def nearest_pairs(points: list[Vec]) -> list[tuple[int, int]]:
    """Edges of a regular solid: every pair at the shortest distance."""
    pairs = list(combinations(range(len(points)), 2))
    shortest = min(dist(points[i], points[j]) for i, j in pairs)
    return [(i, j) for i, j in pairs if dist(points[i], points[j]) < shortest * 1.01]


def icosahedron() -> tuple[list[Vec], list[tuple[int, int]]]:
    phi = (1 + math.sqrt(5)) / 2
    points: list[Vec] = []
    for a in (-1.0, 1.0):
        for b in (-phi, phi):
            points += [(0.0, a, b), (a, b, 0.0), (b, 0.0, a)]
    points = [normalise(p) for p in points]
    return points, nearest_pairs(points)


def dual(points: list[Vec], edges: list[tuple[int, int]]) -> tuple[list[Vec], list[tuple[int, int]]]:
    """Face centres of a triangulated solid, pushed out to the unit sphere."""
    linked = set(edges)
    faces = [
        (i, j, k)
        for i, j, k in combinations(range(len(points)), 3)
        if (i, j) in linked and (j, k) in linked and (i, k) in linked
    ]
    centres = [
        normalise(tuple(sum(points[v][axis] for v in face) / 3 for axis in range(3)))  # type: ignore[arg-type]
        for face in faces
    ]
    return centres, nearest_pairs(centres)


def rot_x(v: Vec, a: float) -> Vec:
    c, s = math.cos(a), math.sin(a)
    return (v[0], v[1] * c - v[2] * s, v[1] * s + v[2] * c)


def rot_y(v: Vec, a: float) -> Vec:
    c, s = math.cos(a), math.sin(a)
    return (v[0] * c + v[2] * s, v[1], -v[0] * s + v[2] * c)


def rot_z(v: Vec, a: float) -> Vec:
    c, s = math.cos(a), math.sin(a)
    return (v[0] * c - v[1] * s, v[0] * s + v[1] * c, v[2])


def pose(v: Vec, spin: float, scale: float) -> Vec:
    """Rest pose -> spin about the solid's axis -> tilt that axis toward the viewer."""
    v = rot_z(rot_x(v, 0.55), 0.35)          # rest pose: no vertex sits on the axis
    v = rot_y(v, spin)                       # the turn
    v = rot_x(rot_z(v, math.radians(21)), math.radians(-16))  # tilted axis
    return (v[0] * scale, v[1] * scale, v[2] * scale)


def project(v: Vec) -> tuple[float, float]:
    k = CAMERA / (CAMERA - v[2])             # perspective: nearer is larger
    return (CX + v[0] * RADIUS * k, CY - v[1] * RADIUS * k)


# --- svg --------------------------------------------------------------------

def num(x: float) -> str:
    text = f"{x:.1f}"
    return text[:-2] if text.endswith(".0") else text


def animate(attr: str, values: list[str]) -> str:
    return (
        f'<animate attributeName="{attr}" dur="{TURN_SECONDS}s" '
        f'repeatCount="indefinite" values="{";".join(values)}"/>'
    )


def solid(points: list[Vec], edges: list[tuple[int, int]], *, direction: int, scale: float,
          colour: str, width: float, near: float, far: float, dots: float) -> tuple[str, str]:
    """Return (animated markup, still markup) for one wireframe solid."""
    frames = []
    for f in range(FRAMES + 1):              # +1 closes the loop on the first frame
        spin = direction * 2 * math.pi * f / FRAMES
        frames.append([pose(p, spin, scale) for p in points])

    def shade(z: float) -> float:            # depth cue: far edges fade
        t = (z / scale + 1) / 2
        return far + (near - far) * max(0.0, min(1.0, t))

    moving, still = [], []
    for i, j in edges:
        paths, alphas = [], []
        for frame in frames:
            (x1, y1), (x2, y2) = project(frame[i]), project(frame[j])
            paths.append(f"M{num(x1)} {num(y1)}L{num(x2)} {num(y2)}")
            alphas.append(f"{shade((frame[i][2] + frame[j][2]) / 2):.2f}")
        moving.append(
            f'<path d="{paths[0]}" stroke-opacity="{alphas[0]}">'
            f'{animate("d", paths)}{animate("stroke-opacity", alphas)}</path>'
        )
        still.append(f'<path d="{paths[0]}" stroke-opacity="{alphas[0]}"/>')

    if dots:
        for i in range(len(points)):
            xs, ys, rs, alphas = [], [], [], []
            for frame in frames:
                x, y = project(frame[i])
                k = CAMERA / (CAMERA - frame[i][2])
                xs.append(num(x))
                ys.append(num(y))
                rs.append(f"{dots * k:.2f}")
                alphas.append(f"{shade(frame[i][2]):.2f}")
            moving.append(
                f'<circle cx="{xs[0]}" cy="{ys[0]}" r="{rs[0]}" fill-opacity="{alphas[0]}" '
                f'fill="{colour}" stroke="none">'
                f'{animate("cx", xs)}{animate("cy", ys)}{animate("r", rs)}'
                f'{animate("fill-opacity", alphas)}</circle>'
            )
            still.append(
                f'<circle cx="{xs[0]}" cy="{ys[0]}" r="{rs[0]}" fill-opacity="{alphas[0]}" '
                f'fill="{colour}" stroke="none"/>'
            )

    attrs = f'fill="none" stroke="{colour}" stroke-width="{width}" stroke-linecap="round"'
    return (f"<g {attrs}>{''.join(moving)}</g>", f"<g {attrs}>{''.join(still)}</g>")


def build(theme: dict[str, str]) -> str:
    outer_pts, outer_edges = icosahedron()
    inner_pts, inner_edges = dual(outer_pts, outer_edges)

    inner_moving, inner_still = solid(
        inner_pts, inner_edges, direction=-1, scale=INNER_SCALE,
        colour=theme["accent"], width=1.1, near=0.95, far=0.3, dots=0,
    )
    outer_moving, outer_still = solid(
        outer_pts, outer_edges, direction=1, scale=1.0,
        colour=theme["fg"], width=1.3, near=0.95, far=0.16, dots=2.1,
    )

    mono = "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace"
    sans = "system-ui, -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
    head, _, tail = NAME.partition("4")

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="t d">
<title id="t">{NAME}</title>
<desc id="d">{TAGLINE}. A wireframe icosahedron turns slowly in 3D.</desc>
<style>.still{{display:none}}@media (prefers-reduced-motion:reduce){{.moving{{display:none}}.still{{display:inline}}}}</style>
<g class="moving">{inner_moving}{outer_moving}</g>
<g class="still">{inner_still}{outer_still}</g>
<text x="{W // 2}" y="274" text-anchor="middle" font-family="{mono}" font-size="38" font-weight="600" letter-spacing="-0.5" fill="{theme['fg']}">{head}<tspan fill="{theme['accent']}">4</tspan>{tail}</text>
<text x="{W // 2}" y="307" text-anchor="middle" font-family="{sans}" font-size="16" fill="{theme['muted']}">{TAGLINE}</text>
</svg>
"""


def main() -> None:
    ASSETS.mkdir(exist_ok=True)
    for name, theme in THEMES.items():
        out = ASSETS / f"hero-{name}.svg"
        out.write_text(build(theme), encoding="utf-8")
        print(f"{out.relative_to(ROOT)}  {out.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
