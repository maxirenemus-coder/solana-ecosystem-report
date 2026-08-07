"""Inline SVG charts, generated from scratch.

No Chart.js, no D3, no CDN. Charting libraries are the usual reason a
"zero-dependency" dashboard quietly stops being one, so the handful of shapes
this report needs are drawn directly as SVG paths.

Everything returned here is a self-contained <svg> string that renders from a
file:// URL with no network access.
"""
from __future__ import annotations

from datetime import datetime, timezone


def _scale(values: list[float], width: float, height: float, pad: float = 4.0):
    """Map values onto pixel coordinates, guarding the flat-series case."""
    lo, hi = min(values), max(values)
    span = hi - lo
    if span == 0:
        span = abs(hi) or 1.0
        lo = hi - span / 2
    step = width / max(len(values) - 1, 1)
    pts = []
    for i, v in enumerate(values):
        x = i * step
        y = height - pad - ((v - lo) / span) * (height - 2 * pad)
        pts.append((x, y))
    return pts, lo, hi


def sparkline(values: list[float], width: int = 260, height: int = 60,
              color: str = "#14F195", fill: bool = True) -> str:
    """A compact trend line with an optional gradient fill underneath."""
    if len(values) < 2:
        return f'<svg width="{width}" height="{height}" role="img" aria-label="no data"></svg>'

    pts, lo, hi = _scale(values, width, height)
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    uid = abs(hash((tuple(values[:5]), color))) % 100000

    area = ""
    if fill:
        area = (f'<defs><linearGradient id="g{uid}" x1="0" y1="0" x2="0" y2="1">'
                f'<stop offset="0%" stop-color="{color}" stop-opacity="0.35"/>'
                f'<stop offset="100%" stop-color="{color}" stop-opacity="0"/>'
                f'</linearGradient></defs>'
                f'<polygon points="0,{height} {line} {width},{height}" fill="url(#g{uid})"/>')

    last_x, last_y = pts[-1]
    return (
        f'<svg width="100%" height="{height}" viewBox="0 0 {width} {height}" '
        f'preserveAspectRatio="none" role="img">'
        f'{area}'
        f'<polyline points="{line}" fill="none" stroke="{color}" stroke-width="1.8" '
        f'stroke-linejoin="round" stroke-linecap="round"/>'
        f'<circle cx="{last_x:.1f}" cy="{last_y:.1f}" r="2.6" fill="{color}"/>'
        f'</svg>'
    )


def line_chart(timestamps: list[int], values: list[float], title: str,
               unit_prefix: str = "", width: int = 640, height: int = 220,
               color: str = "#14F195") -> str:
    """A labelled time-series chart with axis ticks and hover tooltips."""
    if len(values) < 2:
        return f'<div class="chart-empty">{title}: not enough data</div>'

    pad_l, pad_b, pad_t = 62, 26, 10
    plot_w = width - pad_l - 12
    plot_h = height - pad_b - pad_t

    pts, lo, hi = _scale(values, plot_w, plot_h)
    line = " ".join(f"{x + pad_l:.1f},{y + pad_t:.1f}" for x, y in pts)

    # Horizontal gridlines with value labels.
    grid = []
    for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
        v = lo + (hi - lo) * frac
        y = pad_t + plot_h - 4 - frac * (plot_h - 8)
        grid.append(
            f'<line x1="{pad_l}" y1="{y:.1f}" x2="{pad_l + plot_w}" y2="{y:.1f}" '
            f'stroke="#232838" stroke-width="1"/>'
            f'<text x="{pad_l - 8}" y="{y + 3.5:.1f}" fill="#8b93a7" font-size="10" '
            f'text-anchor="end">{unit_prefix}{_short(v)}</text>'
        )

    # Date labels at both ends.
    def fmt(ts):
        return datetime.fromtimestamp(ts, timezone.utc).strftime("%b %d")
    x_labels = (
        f'<text x="{pad_l}" y="{height - 8}" fill="#8b93a7" font-size="10">{fmt(timestamps[0])}</text>'
        f'<text x="{pad_l + plot_w}" y="{height - 8}" fill="#8b93a7" font-size="10" '
        f'text-anchor="end">{fmt(timestamps[-1])}</text>'
    )

    # Invisible hover targets: native <title> tooltips, no JS required.
    step = plot_w / max(len(values) - 1, 1)
    hovers = []
    for i, (x, y) in enumerate(pts):
        hovers.append(
            f'<rect x="{pad_l + x - step / 2:.1f}" y="{pad_t}" width="{step:.1f}" height="{plot_h}" '
            f'fill="transparent"><title>{fmt(timestamps[i])}: {unit_prefix}{values[i]:,.2f}</title></rect>'
        )

    uid = abs(hash(title)) % 100000
    return (
        f'<svg width="100%" height="{height}" viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="{title}">'
        f'<defs><linearGradient id="lg{uid}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="{color}" stop-opacity="0.28"/>'
        f'<stop offset="100%" stop-color="{color}" stop-opacity="0"/></linearGradient></defs>'
        f'{"".join(grid)}'
        f'<polygon points="{pad_l},{pad_t + plot_h} {line} {pad_l + plot_w},{pad_t + plot_h}" fill="url(#lg{uid})"/>'
        f'<polyline points="{line}" fill="none" stroke="{color}" stroke-width="2" '
        f'stroke-linejoin="round"/>'
        f'{x_labels}{"".join(hovers)}'
        f'</svg>'
    )


def bar_chart(labels: list[str], values: list[float], width: int = 640,
              height: int = 200, color: str = "#9945FF") -> str:
    """Horizontal bars -- used for stake distribution across top validators."""
    if not values:
        return '<div class="chart-empty">no data</div>'

    row_h = height / len(values)
    hi = max(values) or 1
    rows = []
    for i, (lab, v) in enumerate(zip(labels, values)):
        y = i * row_h
        bar_w = (v / hi) * (width - 200)
        rows.append(
            f'<text x="0" y="{y + row_h / 2 + 3.5:.1f}" fill="#8b93a7" font-size="10" '
            f'font-family="monospace">{lab}</text>'
            f'<rect x="150" y="{y + 3:.1f}" width="{bar_w:.1f}" height="{row_h - 6:.1f}" '
            f'rx="2" fill="{color}" fill-opacity="0.75">'
            f'<title>{v:,.0f} SOL</title></rect>'
            f'<text x="{150 + bar_w + 6:.1f}" y="{y + row_h / 2 + 3.5:.1f}" fill="#e6e9ef" '
            f'font-size="10">{_short(v)}</text>'
        )
    return (f'<svg width="100%" height="{height}" viewBox="0 0 {width} {height}" role="img">'
            f'{"".join(rows)}</svg>')


def progress_ring(pct: float, size: int = 96, color: str = "#9945FF") -> str:
    """Circular progress indicator -- used for epoch completion."""
    r = size / 2 - 8
    circ = 2 * 3.14159265 * r
    filled = circ * min(max(pct, 0), 100) / 100
    c = size / 2
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" role="img">'
        f'<circle cx="{c}" cy="{c}" r="{r:.1f}" fill="none" stroke="#232838" stroke-width="7"/>'
        f'<circle cx="{c}" cy="{c}" r="{r:.1f}" fill="none" stroke="{color}" stroke-width="7" '
        f'stroke-dasharray="{filled:.1f} {circ - filled:.1f}" stroke-linecap="round" '
        f'transform="rotate(-90 {c} {c})"/>'
        f'<text x="{c}" y="{c + 5}" fill="#e6e9ef" font-size="16" font-weight="600" '
        f'text-anchor="middle">{pct:.0f}%</text>'
        f'</svg>'
    )


def _short(v: float) -> str:
    """Compact number formatting for axis labels: 4.7B, 15.5M, 73.48."""
    a = abs(v)
    if a >= 1e9:
        return f"{v / 1e9:.2f}B"
    if a >= 1e6:
        return f"{v / 1e6:.1f}M"
    if a >= 1e3:
        return f"{v / 1e3:.1f}K"
    return f"{v:,.2f}"
