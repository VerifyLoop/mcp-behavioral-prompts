"""SVG plot renderer.

Pure-Python (no matplotlib dependency) so the package stays light. Given a
function expression and an x range, sample N points and emit a minimal SVG
polyline. Good enough for tutor diagrams the student can read on a phone.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import sympy as sp


@dataclass
class PlotResult:
    ok: bool
    svg: str
    notes: str = ""


def render_plot_svg(
    expr: str,
    x_min: float = -5.0,
    x_max: float = 5.0,
    samples: int = 200,
    width: int = 400,
    height: int = 240,
    variable: str = "x",
) -> PlotResult:
    """Render `expr` as a 1D plot in plain SVG.

    Returns ok=False if the expression doesn't parse or the function diverges
    over the requested range (no finite samples).
    """
    if x_max <= x_min or samples < 2:
        return PlotResult(ok=False, svg="", notes="invalid range or samples")
    try:
        e = sp.sympify(expr)
    except Exception as exc:
        return PlotResult(ok=False, svg="", notes=f"parse error: {exc}")

    var = sp.symbols(variable)
    pts: list[tuple[float, float]] = []
    for i in range(samples):
        x = x_min + (x_max - x_min) * i / (samples - 1)
        try:
            y = float(e.evalf(subs={var: x}))
        except Exception:
            continue
        if math.isfinite(y):
            pts.append((x, y))

    if not pts:
        return PlotResult(ok=False, svg="", notes="no finite samples")

    ys = [p[1] for p in pts]
    y_min, y_max = min(ys), max(ys)
    if math.isclose(y_min, y_max):
        y_min -= 1.0
        y_max += 1.0
    pad = 16

    def to_svg_x(x: float) -> float:
        return pad + (x - x_min) / (x_max - x_min) * (width - 2 * pad)

    def to_svg_y(y: float) -> float:
        return height - pad - (y - y_min) / (y_max - y_min) * (height - 2 * pad)

    polyline = " ".join(f"{to_svg_x(x):.1f},{to_svg_y(y):.1f}" for x, y in pts)
    axis_y = to_svg_y(0.0) if y_min <= 0.0 <= y_max else None
    axis_x = to_svg_x(0.0) if x_min <= 0.0 <= x_max else None
    axes = ""
    if axis_y is not None:
        axes += (
            f'<line x1="{pad}" x2="{width - pad}" '
            f'y1="{axis_y:.1f}" y2="{axis_y:.1f}" '
            f'stroke="#888" stroke-width="1"/>'
        )
    if axis_x is not None:
        axes += (
            f'<line y1="{pad}" y2="{height - pad}" '
            f'x1="{axis_x:.1f}" x2="{axis_x:.1f}" '
            f'stroke="#888" stroke-width="1"/>'
        )
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {width} {height}" width="{width}" height="{height}">'
        f'<rect width="100%" height="100%" fill="white"/>'
        f"{axes}"
        f'<polyline fill="none" stroke="#2563eb" stroke-width="2" '
        f'points="{polyline}"/>'
        f"</svg>"
    )
    return PlotResult(ok=True, svg=svg, notes=f"{len(pts)} points")
