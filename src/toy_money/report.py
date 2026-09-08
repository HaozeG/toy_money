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

# Categorical slots 1 & 2 from the data-viz reference palette (CVD-validated).
_COLOR = {"CHN": "#2a78d6", "JPN": "#eb6834"}

# Shared "years since anchor" window for every panel — a common analytical
# coordinate only works if the axis is identical across the grid.
_VIEW_T = (-25, 35)


def _panels(alignment: Alignment):
    panels = []
    for s in SERIES:
        if not s.in_report:
            continue
        try:
            raw = datastore.read(s.key)
        except FileNotFoundError:
            continue
        aligned = align_series(raw, alignment)
        if aligned.empty:
            continue
        panels.append((s, aligned, datastore.provenance(s.key)))
    return panels


def make_figure(alignment: Alignment):
    """Build the Plotly figure and the list of caveat strings for `alignment`."""
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
        vertical_spacing=0.075,
        horizontal_spacing=0.08,
    )

    # Where does China's actual data end? Everything to the right of this on each
    # panel is Japan's post-anchor path that China has not yet lived.
    chn_last_t = None
    for _, df, _ in panels:
        chn = df[df["country"] == "CHN"]
        if not chn.empty:
            m = int(chn["t"].max())
            chn_last_t = m if chn_last_t is None else max(chn_last_t, m)

    seed_notes = []
    for i, (s, df, prov) in enumerate(panels):
        row, col = divmod(i, ncols)
        row += 1
        col += 1
        for iso3 in COUNTRIES:
            sub = df[(df["country"] == iso3) & df["t"].between(*_VIEW_T)]
            if sub.empty:
                continue
            fig.add_trace(
                go.Scatter(
                    x=sub["t"],
                    y=sub["value"],
                    mode="lines",
                    name=COUNTRIES[iso3],
                    showlegend=False,  # every panel carries direct end-labels
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
            # Direct label at each line's right-hand end (identity without a
            # legend round-trip).
            last = sub.iloc[-1]
            fig.add_annotation(
                x=last["t"],
                y=last["value"],
                text=f" {COUNTRIES[iso3]}",
                showarrow=False,
                xanchor="left",
                font=dict(color=_COLOR[iso3], size=10),
                row=row,
                col=col,
            )

        if s.log_y:
            fig.update_yaxes(
                type="log",
                tickvals=[2500, 5000, 10000, 20000, 40000],
                ticktext=["2.5k", "5k", "10k", "20k", "40k"],
                row=row,
                col=col,
            )
        fig.add_vline(
            x=0, line_width=1, line_dash="dot", line_color="#888", row=row, col=col
        )
        if chn_last_t is not None and chn_last_t < _VIEW_T[1]:
            fig.add_vrect(
                x0=chn_last_t,
                x1=_VIEW_T[1],
                fillcolor="#888",
                opacity=0.07,
                line_width=0,
                row=row,
                col=col,
            )

        if s.note:
            seed_notes.append(f"<b>{s.label}:</b> {s.note}")
        if prov == "seed":
            extra = f" {s.seed_note}" if s.seed_note else ""
            seed_notes.append(
                f"<b>{s.label}:</b> hand-seeded approximate data — "
                f"live fetch unavailable, not from the official provider.{extra}"
            )

    fig.update_xaxes(range=list(_VIEW_T), title_text="years since anchor", row=nrows, col=1)
    fig.update_xaxes(range=list(_VIEW_T), title_text="years since anchor", row=nrows, col=2)
    for r in range(1, nrows):
        for c in (1, 2):
            fig.update_xaxes(range=list(_VIEW_T), row=r, col=c)

    band = (
        f" &nbsp;·&nbsp; shaded = beyond China's latest data (t={chn_last_t}), Japan only"
        if chn_last_t is not None and chn_last_t < _VIEW_T[1]
        else ""
    )
    fig.update_layout(
        height=300 * nrows + 40,
        template="plotly_white",
        font=dict(size=12),
        title=dict(
            text=(
                "China now vs. Japan 1990s — aligned macro comparison "
                "<span style='font-size:12px;color:#2a78d6'>■ China</span>"
                "<span style='font-size:12px;color:#eb6834'> ■ Japan</span><br>"
                f"<span style='font-size:12px;color:#666'>Anchor: "
                f"{alignment.describe()} &nbsp;·&nbsp; t = years since anchor "
                f"(dotted line){band}</span>"
            ),
        ),
        showlegend=False,
        margin=dict(t=95, l=55, r=62, b=55),
    )
    return fig, panels, seed_notes


def build_report(alignment: Alignment, out_path: Path) -> Path:
    fig, panels, seed_notes = make_figure(alignment)
    any_live = any(prov == "live" for _, _, prov in panels)

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
        source_line = "Sources: World Bank, IMF DataMapper, BIS."

    items = "".join(f"<li>{n}</li>" for n in seed_notes)
    notes_html = (
        "<div style='max-width:1100px;margin:20px auto;font:13px/1.5 system-ui;"
        "color:#444;border-top:1px solid #ddd;padding-top:12px'>"
        + (f"<b>Data caveats</b><ul>{items}</ul>" if seed_notes else "")
        + f"<p style='color:#888'>Generated {_dt.date.today().isoformat()} by toy-money; "
        + "observations after the current year (IMF/BIS forward projections) are excluded. "
        + "The anchor choice drives the verdict — rebuild with "
        + "<code>--anchor workingage_peak</code> or explicit "
        + "<code>--anchor-jpn/--anchor-chn</code> to test alternatives. "
        + source_line
        + "</p></div>"
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    html = fig.to_html(include_plotlyjs="inline", full_html=True)
    html = html.replace("</body>", notes_html + "</body>")
    out_path.write_text(html, encoding="utf-8")
    return out_path
