"""Render the aligned comparison as a single self-contained HTML file."""

from __future__ import annotations

import datetime as _dt
import math
from pathlib import Path

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from . import datastore
from .align import Alignment, align_series
from .config import COUNTRIES, SERIES

_COLOR = {"JPN": "#c0392b", "CHN": "#2c3e50"}


def _panels(alignment: Alignment):
    panels = []
    for s in SERIES:
        try:
            raw = datastore.read(s.key)
        except FileNotFoundError:
            continue
        aligned = align_series(raw, alignment)
        if aligned.empty:
            continue
        panels.append((s, aligned, datastore.provenance(s.key)))
    return panels


def build_report(alignment: Alignment, out_path: Path) -> Path:
    panels = _panels(alignment)
    if not panels:
        raise RuntimeError(
            "No data available for any series. Run `toy-money fetch` first."
        )

    ncols = 2
    nrows = math.ceil(len(panels) / ncols)
    fig = make_subplots(
        rows=nrows,
        cols=ncols,
        subplot_titles=[f"{s.label} ({s.unit})" for s, _, _ in panels],
        vertical_spacing=0.09,
        horizontal_spacing=0.08,
    )

    seed_notes = []
    any_live = any(prov == "live" for _, _, prov in panels)
    for i, (s, df, prov) in enumerate(panels):
        row, col = divmod(i, ncols)
        row += 1
        col += 1
        for iso3 in COUNTRIES:
            sub = df[df["country"] == iso3]
            if sub.empty:
                continue
            fig.add_trace(
                go.Scatter(
                    x=sub["t"],
                    y=sub["value"],
                    mode="lines",
                    name=COUNTRIES[iso3],
                    legendgroup=iso3,
                    showlegend=(i == 0),
                    line=dict(color=_COLOR[iso3], width=2),
                    hovertemplate=(
                        f"{COUNTRIES[iso3]}<br>t=%{{x}} (year %{{customdata}})"
                        f"<br>%{{y:.2f}}<extra></extra>"
                    ),
                    customdata=sub["year"],
                ),
                row=row,
                col=col,
            )
        fig.add_vline(x=0, line_width=1, line_dash="dot", line_color="#888", row=row, col=col)
        if s.note:
            seed_notes.append(f"<b>{s.label}:</b> {s.note}")
        if prov == "seed":
            seed_notes.append(
                f"<b>{s.label}:</b> hand-seeded approximate data — "
                f"live fetch unavailable, not from the official provider."
            )

    fig.update_xaxes(title_text="years since anchor", row=nrows, col=1)
    fig.update_xaxes(title_text="years since anchor", row=nrows, col=2)
    fig.update_layout(
        height=320 * nrows,
        template="plotly_white",
        title=dict(
            text=(
                "China now vs. Japan 1990s — aligned macro comparison<br>"
                f"<span style='font-size:13px;color:#666'>Anchor: {alignment.describe()}. "
                "The anchor choice drives the verdict — try --anchor workingage_peak "
                "for a different alignment.</span>"
            ),
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(t=110, l=60, r=30, b=60),
    )

    n_seed = sum(1 for _, _, prov in panels if prov == "seed")
    if not any_live:
        source_line = (
            "<b>All panels use hand-seeded approximate data</b> — no live fetch "
            "reached the official providers. Run <code>toy-money fetch</code> with "
            "network access for World Bank / IMF / BIS figures."
        )
    elif n_seed:
        source_line = (
            f"Sources: World Bank, IMF DataMapper, BIS. {n_seed} panel(s) fell back "
            "to hand-seeded data (flagged above)."
        )
    else:
        source_line = "Sources: World Bank, IMF DataMapper, BIS, plus hand-seeded labour data."

    items = "".join(f"<li>{n}</li>" for n in seed_notes)
    notes_html = (
        "<div style='max-width:1100px;margin:20px auto;font:13px/1.5 system-ui;"
        "color:#444;border-top:1px solid #ddd;padding-top:12px'>"
        + (f"<b>Data caveats</b><ul>{items}</ul>" if seed_notes else "")
        + f"<p style='color:#888'>Generated {_dt.date.today().isoformat()} by toy-money. "
        + source_line
        + "</p></div>"
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    html = fig.to_html(include_plotlyjs="inline", full_html=True)
    html = html.replace("</body>", notes_html + "</body>")
    out_path.write_text(html, encoding="utf-8")
    return out_path
