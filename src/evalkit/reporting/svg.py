"""Server-rendered SVG charts (ADR-0007): zero runtime dependency, works from file://,
every drawn value is traceable to a stored record. Axes start at zero for rates and counts;
intervals are drawn as error bars; nothing is smoothed or extrapolated.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from html import escape

PALETTE = {
    "ink": "#1f2933",
    "muted": "#7b8794",
    "grid": "#e4e7eb",
    "ok": "#2f855a",
    "warn": "#b7791f",
    "fail": "#c53030",
    "neutral": "#3b6ea5",
    "neutral2": "#8aa9c8",
    "neutral3": "#c9d6e3",
}

STATUS_COLOR = {
    "PASS": PALETTE["ok"],
    "WARNING": PALETTE["warn"],
    "FAIL": PALETTE["fail"],
    "INCONCLUSIVE": PALETTE["muted"],
    "NOT_EVALUATED": PALETTE["neutral3"],
}


@dataclass
class Bar:
    label: str
    value: float | None
    low: float | None = None
    high: float | None = None
    color: str | None = None
    note: str = ""


def _fmt(v: float, pct: bool) -> str:
    return f"{v:.0%}" if pct else (f"{v:.3g}" if abs(v) < 1000 else f"{v:,.0f}")


def bar_chart(
    bars: Sequence[Bar],
    *,
    title: str,
    width: int = 640,
    height: int | None = None,
    max_value: float | None = None,
    percent: bool = False,
    unit: str = "",
) -> str:
    """Horizontal bars with optional error bars. Missing values are drawn as 'n/a'."""
    row_h = 28
    left = 180
    top = 36
    h = height or (top + row_h * max(1, len(bars)) + 24)
    plot_w = width - left - 110
    vals = [b.high if b.high is not None else b.value for b in bars if b.value is not None]
    vmax = max_value if max_value is not None else (max(vals) if vals else 1.0)
    vmax = vmax or 1.0
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {h}" style="max-width:100%;height:auto" '
        f'width="{width}" height="{h}" role="img" aria-label="{escape(title)}" font-family="system-ui, sans-serif" '
        f'font-size="12">',
        f"<title>{escape(title)}</title>",
        f'<text x="0" y="16" font-size="14" font-weight="600" fill="{PALETTE["ink"]}">{escape(title)}</text>',
    ]
    for frac in (0, 0.25, 0.5, 0.75, 1.0):
        x = left + plot_w * frac
        out.append(
            f'<line x1="{x:.1f}" y1="{top - 6}" x2="{x:.1f}" y2="{h - 20}" stroke="{PALETTE["grid"]}"/>'
        )
        out.append(
            f'<text x="{x:.1f}" y="{h - 6}" text-anchor="middle" fill="{PALETTE["muted"]}">'
            f"{escape(_fmt(vmax * frac, percent))}{escape(unit)}</text>"
        )
    for i, b in enumerate(bars):
        y = top + i * row_h
        out.append(
            f'<text x="{left - 8}" y="{y + 17}" text-anchor="end" fill="{PALETTE["ink"]}">'
            f"{escape(b.label[:28])}</text>"
        )
        if b.value is None:
            out.append(f'<text x="{left + 4}" y="{y + 17}" fill="{PALETTE["muted"]}">n/a</text>')
            continue
        w = plot_w * min(b.value, vmax) / vmax
        color = b.color or PALETTE["neutral"]
        out.append(
            f'<rect x="{left}" y="{y + 5}" width="{w:.1f}" height="18" fill="{color}" rx="2">'
            f"<title>{escape(b.label)}: {escape(_fmt(b.value, percent))}{escape(unit)} {escape(b.note)}</title></rect>"
        )
        if b.low is not None and b.high is not None:
            x1 = left + plot_w * min(b.low, vmax) / vmax
            x2 = left + plot_w * min(b.high, vmax) / vmax
            cy = y + 14
            out.append(
                f'<line x1="{x1:.1f}" y1="{cy}" x2="{x2:.1f}" y2="{cy}" stroke="{PALETTE["ink"]}" stroke-width="1.5"/>'
                f'<line x1="{x1:.1f}" y1="{cy - 5}" x2="{x1:.1f}" y2="{cy + 5}" stroke="{PALETTE["ink"]}" stroke-width="1.5"/>'
                f'<line x1="{x2:.1f}" y1="{cy - 5}" x2="{x2:.1f}" y2="{cy + 5}" stroke="{PALETTE["ink"]}" stroke-width="1.5"/>'
            )
        out.append(
            f'<text x="{left + w + 6:.1f}" y="{y + 17}" fill="{PALETTE["ink"]}">'
            f"{escape(_fmt(b.value, percent))}{escape(unit)}</text>"
        )
    out.append("</svg>")
    return "".join(out)


def line_chart(
    series: Sequence[tuple[str, Sequence[float | None]]],
    labels: Sequence[str],
    *,
    title: str,
    width: int = 640,
    height: int = 240,
    percent: bool = False,
    ymin: float = 0.0,
    ymax: float | None = None,
) -> str:
    """Time/version series. y starts at ``ymin`` (0 by default: no truncated axis)."""
    left, top, right, bottom = 56, 44, 16, 40
    plot_w, plot_h = width - left - right, height - top - bottom
    allv = [v for _, ys in series for v in ys if v is not None]
    y_max = ymax if ymax is not None else (max(allv) if allv else 1.0)
    y_max = y_max if y_max > ymin else ymin + 1.0
    n = max(1, len(labels))
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" '
        f'height="{height}" role="img" aria-label="{escape(title)}" font-family="system-ui, sans-serif" font-size="12">',
        f"<title>{escape(title)}</title>",
        f'<text x="0" y="16" font-size="14" font-weight="600" fill="{PALETTE["ink"]}">{escape(title)}</text>',
    ]
    for frac in (0, 0.5, 1.0):
        yv = ymin + (y_max - ymin) * frac
        y = top + plot_h - plot_h * frac
        out.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_w}" y2="{y:.1f}" stroke="{PALETTE["grid"]}"/>'
        )
        out.append(
            f'<text x="{left - 6}" y="{y + 4:.1f}" text-anchor="end" fill="{PALETTE["muted"]}">{escape(_fmt(yv, percent))}</text>'
        )
    colors = [
        PALETTE["neutral"],
        PALETTE["ok"],
        PALETTE["warn"],
        PALETTE["fail"],
        PALETTE["neutral2"],
    ]
    for si, (name, ys) in enumerate(series):
        color = colors[si % len(colors)]
        pts = []
        for i, v in enumerate(ys):
            if v is None:
                continue
            x = left + (plot_w * i / (n - 1) if n > 1 else plot_w / 2)
            y = top + plot_h - plot_h * (v - ymin) / (y_max - ymin)
            pts.append((x, y, v))
        if len(pts) > 1:
            path = " ".join(f"{x:.1f},{y:.1f}" for x, y, _ in pts)
            out.append(f'<polyline points="{path}" fill="none" stroke="{color}" stroke-width="2"/>')
        for x, y, v in pts:
            out.append(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="{color}"><title>{escape(name)}: {escape(_fmt(v, percent))}</title></circle>'
            )
        out.append(
            f'<text x="{left + plot_w - 4}" y="{top - 8 - si * 14}" text-anchor="end" fill="{color}">{escape(name)}</text>'
        )
    for i, lab in enumerate(labels):
        x = left + (plot_w * i / (n - 1) if n > 1 else plot_w / 2)
        out.append(
            f'<text x="{x:.1f}" y="{height - 8}" text-anchor="middle" fill="{PALETTE["muted"]}">{escape(str(lab)[:12])}</text>'
        )
    out.append("</svg>")
    return "".join(out)


def stacked_bars(
    rows: Sequence[tuple[str, dict[str, float]]],
    categories: Sequence[str],
    *,
    title: str,
    width: int = 640,
    unit: str = "",
) -> str:
    """Horizontal stacked bars (e.g. token categories per campaign)."""
    row_h, left, top = 28, 180, 36
    h = top + row_h * max(1, len(rows)) + 44
    plot_w = width - left - 110
    totals = [sum(d.get(c, 0.0) for c in categories) for _, d in rows]
    vmax = max(totals) if totals and max(totals) > 0 else 1.0
    colors = [
        PALETTE["neutral"],
        PALETTE["neutral2"],
        PALETTE["neutral3"],
        PALETTE["ok"],
        PALETTE["warn"],
    ]
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {h}" width="{width}" height="{h}" '
        f'role="img" aria-label="{escape(title)}" font-family="system-ui, sans-serif" font-size="12">',
        f"<title>{escape(title)}</title>",
        f'<text x="0" y="16" font-size="14" font-weight="600" fill="{PALETTE["ink"]}">{escape(title)}</text>',
    ]
    for i, (label, d) in enumerate(rows):
        y = top + i * row_h
        out.append(
            f'<text x="{left - 8}" y="{y + 17}" text-anchor="end" fill="{PALETTE["ink"]}">{escape(label[:28])}</text>'
        )
        x = float(left)
        for ci, c in enumerate(categories):
            v = d.get(c, 0.0)
            if v <= 0:
                continue
            w = plot_w * v / vmax
            out.append(
                f'<rect x="{x:.1f}" y="{y + 5}" width="{w:.1f}" height="18" fill="{colors[ci % len(colors)]}">'
                f"<title>{escape(label)} / {escape(c)}: {escape(_fmt(v, False))}{escape(unit)}</title></rect>"
            )
            x += w
        out.append(
            f'<text x="{x + 6:.1f}" y="{y + 17}" fill="{PALETTE["ink"]}">{escape(_fmt(totals[i], False))}{escape(unit)}</text>'
        )
    lx = left
    present = {c for _, d in rows for c in categories if d.get(c, 0.0) > 0}
    for ci, c in enumerate(categories):
        if c not in present:
            continue
        ly = h - 14
        out.append(
            f'<rect x="{lx}" y="{ly - 10}" width="12" height="12" fill="{colors[ci % len(colors)]}"/>'
        )
        out.append(f'<text x="{lx + 16}" y="{ly}" fill="{PALETTE["muted"]}">{escape(c)}</text>')
        lx += 16 + 7 * len(c) + 18
    out.append("</svg>")
    return "".join(out)


def histogram(
    values: Sequence[float],
    *,
    title: str,
    bins: int = 12,
    width: int = 640,
    height: int = 220,
    unit: str = "",
) -> str:
    """Simple histogram (counts start at zero)."""
    left, top, right, bottom = 48, 36, 16, 40
    plot_w, plot_h = width - left - right, height - top - bottom
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
        f'role="img" aria-label="{escape(title)}" font-family="system-ui, sans-serif" font-size="12">',
        f"<title>{escape(title)}</title>",
        f'<text x="0" y="16" font-size="14" font-weight="600" fill="{PALETTE["ink"]}">{escape(title)}</text>',
    ]
    if not values:
        out.append(
            f'<text x="{left}" y="{top + 20}" fill="{PALETTE["muted"]}">no data</text></svg>'
        )
        return "".join(out)
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1.0
    counts = [0] * bins
    for v in values:
        idx = min(bins - 1, int((v - lo) / span * bins))
        counts[idx] += 1
    cmax = max(counts) or 1
    bw = plot_w / bins
    for i, c in enumerate(counts):
        bh = plot_h * c / cmax
        x = left + i * bw
        y = top + plot_h - bh
        out.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw - 2:.1f}" height="{bh:.1f}" fill="{PALETTE["neutral"]}">'
            f"<title>[{lo + span * i / bins:.3g}, {lo + span * (i + 1) / bins:.3g}){escape(unit)}: {c}</title></rect>"
        )
    out.append(
        f'<text x="{left}" y="{height - 8}" fill="{PALETTE["muted"]}">{lo:.3g}{escape(unit)}</text>'
    )
    out.append(
        f'<text x="{left + plot_w}" y="{height - 8}" text-anchor="end" fill="{PALETTE["muted"]}">{hi:.3g}{escape(unit)}</text>'
    )
    out.append(
        f'<text x="{left - 6}" y="{top + 4}" text-anchor="end" fill="{PALETTE["muted"]}">{cmax}</text>'
    )
    out.append("</svg>")
    return "".join(out)
