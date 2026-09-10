"""Render the aligned comparison as a single self-contained HTML file."""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import math
from dataclasses import asdict
from pathlib import Path

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .align import Alignment, resolve_alignment
from .analysis import ANALYZERS, Finding, headline, prepared_panels
from .config import ANCHOR_PRESETS, ANALYSIS_WINDOW, COUNTRIES, MAX_YEAR, SERIES
from . import datastore

# Categorical slots 1 & 2 from the data-viz reference palette (CVD-validated).
_COLOR = {"CHN": "#2a78d6", "JPN": "#eb6834"}

# Shared "years since anchor" window for every panel — the same window is used
# for overlap counting in `analysis.precedent`, so the figure and the findings
# make the same claim about comparability.
_VIEW_T = ANALYSIS_WINDOW

# Below this many post-anchor years, an anchor's column is a snapshot of China's
# current position, not a trajectory match — the report says so (decision 2 = D).
SNAPSHOT_MIN_POST = 8


def _panels(alignment: Alignment):
    return [(p.series, p.df, p.provenance) for p in prepared_panels(alignment)]


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
        if s.definition_note:
            seed_notes.append(
                f"<b>{s.label} (definition):</b> {s.definition_note}"
            )
        if prov == "seed":
            extra = f" {s.seed_note}" if s.seed_note else ""
            seed_notes.append(
                f"<b>{s.label}:</b> bundled fallback snapshot — live fetch "
                f"unavailable, not refreshed from the provider.{extra}"
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


_DIR_STYLE = {
    "above": "background:#f6e0da;color:#a4432a",
    "below": "background:#e3ecf6;color:#2a5a8c",
    "crossing": "background:#eef0e6;color:#5a6a2c",
    "n/a": "background:#eee;color:#999",
}


def _num(v: float | None) -> str:
    return "–" if v is None else f"{v:.1f}"


def _conclusions_html(
    alignment: Alignment, method: str, findings: list[Finding]
) -> str:
    analyzer = ANALYZERS[method]
    if not findings:
        return ""

    # Direction under every preset (a flip between presets = the comparison
    # depends on the alignment). Reuse the active findings where a preset matches.
    presets = list(ANCHOR_PRESETS)
    active = next(
        (n for n in presets if resolve_alignment(n).anchors == alignment.anchors),
        None,
    )
    by_preset: dict[str, dict[str, str]] = {}
    post_years: dict[str, int] = {}
    for name in presets:
        al = resolve_alignment(name)
        fs = findings if name == active else analyzer(prepared_panels(al), al)
        post_years[name] = max((f.n_post for f in fs), default=0)
        for f in fs:
            by_preset.setdefault(f.key, {})[name] = f.direction

    ref_t = findings[0].reference_t
    ref_year = alignment.anchors["CHN"] + ref_t

    def row(f: Finding) -> str:
        name = f.label
        if f.level_gap_at_anchor is not None:
            chn0, jpn0 = f.level_gap_at_anchor
            name += (
                f" <span style='color:#888'>(log-change; {chn0:,.0f} vs "
                f"{jpn0:,.0f} at anchor)</span>"
            )
        if f.jpn_forward:
            hi = max(f.jpn_forward)
            fwd = f"{_num(f.jpn_at_ref)} → {f.jpn_forward[hi]:.1f}"
        else:
            fwd = "–"
        pres = "".join(
            f"<td style='{_DIR_STYLE.get(by_preset[f.key].get(n, ''), '')};"
            f"text-align:center;padding:3px 8px'>"
            f"{by_preset[f.key].get(n, '–')}</td>"
            for n in presets
        )
        return (
            f"<tr><td style='padding:3px 8px'>{name}</td>"
            f"<td style='text-align:right;padding:3px 8px'>{_num(f.chn_at_ref)}</td>"
            f"<td style='text-align:right;padding:3px 8px'>{_num(f.jpn_at_ref)}</td>"
            f"<td style='text-align:right;padding:3px 8px'>{fwd}</td>"
            f"{pres}</tr>"
        )

    body = "".join(row(f) for f in findings)

    def th(n: str) -> str:
        yrs = post_years.get(n, 0)
        label = f"{n}<br><span style='font-weight:400;color:#888'>{yrs}y post"
        label += " · snapshot*" if yrs < SNAPSHOT_MIN_POST else ""
        label += "</span>"
        return (
            f"<th style='padding:3px 8px'>"
            f"{'<b>' + label + '</b>' if n == active else label}</th>"
        )

    head = "".join(th(n) for n in presets)
    snapshot = [n for n in presets if post_years.get(n, 0) < SNAPSHOT_MIN_POST]
    snapshot_note = (
        f"<p style='color:#888;margin:6px 0 0'>* {', '.join(snapshot)}: China has "
        f"only ~{post_years[snapshot[0]]} years past this anchor — read the column "
        f"as where China sits now, not as a path match. A distribution of episodes "
        f"(Phase B) is what tests position on short data.</p>"
        if snapshot
        else ""
    )
    indet = [f.label for f in findings if f.verdict == "indeterminate"]
    indet_note = (
        f"<p style='color:#888;margin:6px 0 0'>Indeterminate (too few post-anchor "
        f"years): {', '.join(indet)}.</p>"
        if indet
        else ""
    )

    return (
        "<div style='max-width:1100px;margin:16px auto 0;font:14px/1.5 system-ui;"
        "color:#222'>"
        "<h2 style='margin:0 0 2px'>Conclusion</h2>"
        f"<p style='margin:0 0 4px'>{headline(findings)}.</p>"
        f"<p style='color:#666;margin:0 0 10px'>Method <code>{method}</code>; "
        f"reference = China's latest year (t={ref_t}, {ref_year}). Columns: value at "
        "that t for China and Japan (this build), Japan's value 10y on, and China's "
        "direction vs. Japan under each anchor (<b>bold</b> = this build; the year "
        "count under each is China's post-anchor data). The chart shows the full "
        "paths.</p>"
        "<table style='border-collapse:collapse;font-size:13px;margin-bottom:14px'>"
        "<tr><th style='padding:3px 8px;text-align:left'>indicator</th>"
        "<th style='padding:3px 8px'>China</th><th style='padding:3px 8px'>Japan</th>"
        "<th style='padding:3px 8px'>Japan +10y</th>"
        f"{head}</tr>"
        f"{body}</table>{snapshot_note}{indet_note}"
        "</div><hr style='max-width:1100px;margin:18px auto;border:none;"
        "border-top:1px solid #ddd'>"
    )


def _cache_manifest() -> dict:
    """Anchor-independent snapshot of the data behind the report: per series its
    provenance, source, row count, year range and (for a live parquet) sha256."""
    out = {}
    for s in SERIES:
        entry = {"source": s.source, "provenance": datastore.provenance(s.key)}
        try:
            df = datastore.read(s.key)
            entry.update(
                rows=int(len(df)),
                year_min=int(df["year"].min()),
                year_max=int(df["year"].max()),
                # Per-country span: an episode whose country is absent here is
                # marked unavailable for that indicator, not silently dropped.
                by_country={
                    str(c): [int(g["year"].min()), int(g["year"].max()), int(len(g))]
                    for c, g in df.groupby("country")
                },
            )
        except FileNotFoundError:
            entry.update(rows=0, year_min=None, year_max=None, by_country={})
        pq = datastore.DATA_DIR / f"{s.key}.parquet"
        entry["sha256"] = (
            hashlib.sha256(pq.read_bytes()).hexdigest() if pq.exists() else None
        )
        out[s.key] = entry
    return out


def write_side_outputs(
    alignment: Alignment,
    method: str,
    findings: list[Finding],
    findings_label: str,
    out_dir: Path,
) -> list[Path]:
    """Write the reviewable JSON next to the HTML: the findings for this
    alignment, and the anchor-independent cache manifest."""
    out_dir.mkdir(parents=True, exist_ok=True)
    # No wall-clock timestamp: these are committed review snapshots, and git
    # already dates them. The parquet sha256 in the manifest identifies the data.
    findings_path = out_dir / f"findings.{findings_label}.json"
    findings_path.write_text(
        json.dumps(
            {
                "method": method,
                "max_year": MAX_YEAR,
                "analysis_window": list(ANALYSIS_WINDOW),
                "alignment": {
                    "label": alignment.label,
                    "anchors": alignment.anchors,
                },
                "findings": [asdict(f) for f in findings],
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    manifest_path = out_dir / "cache_manifest.json"
    manifest_path.write_text(
        json.dumps({"series": _cache_manifest()}, indent=2),
        encoding="utf-8",
    )
    return [findings_path, manifest_path]


def build_report(
    alignment: Alignment,
    out_path: Path,
    method: str = "precedent",
    findings_label: str = "custom",
) -> Path:
    fig, panels, seed_notes = make_figure(alignment)
    findings = ANALYZERS[method](prepared_panels(alignment), alignment)
    any_live = any(prov == "live" for _, _, prov in panels)
    n_seed = sum(1 for _, _, prov in panels if prov == "seed")
    n_unknown = sum(1 for _, _, prov in panels if prov == "unknown")

    if not any_live and n_seed == len(panels):
        source_line = (
            "<b>All panels use the bundled fallback snapshot</b> — no live fetch "
            "reached the official providers. Run <code>toy-money fetch</code> with "
            "network access for World Bank / IMF / BIS figures."
        )
    elif n_seed or n_unknown:
        parts = ["Sources: World Bank, IMF DataMapper, BIS."]
        if n_seed:
            parts.append(
                f"{n_seed} panel(s) use the bundled fallback snapshot (flagged above)."
            )
        if n_unknown:
            parts.append(
                f"{n_unknown} panel(s) have unknown provenance (missing .meta.json)."
            )
        source_line = " ".join(parts)
    else:
        source_line = "Sources: World Bank, IMF DataMapper, BIS."

    items = "".join(f"<li>{n}</li>" for n in seed_notes)
    notes_html = (
        "<div style='max-width:1100px;margin:20px auto;font:13px/1.5 system-ui;"
        "color:#444;border-top:1px solid #ddd;padding-top:12px'>"
        + (f"<b>Data caveats</b><ul>{items}</ul>" if seed_notes else "")
        + f"<p style='color:#888'>{_dt.date.today().isoformat()} · toy-money · "
        + f"data through {MAX_YEAR}; overlap window "
        + f"t={ANALYSIS_WINDOW[0]}..{ANALYSIS_WINDOW[1]}. "
        + f"Rebuild <code>--anchor workingage_peak</code> for the other alignment. "
        + source_line
        + "</p></div>"
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    html = fig.to_html(include_plotlyjs="cdn", full_html=True)
    html = html.replace(
        "<body>", "<body>" + _conclusions_html(alignment, method, findings), 1
    )
    html = html.replace("</body>", notes_html + "</body>")
    out_path.write_text(html, encoding="utf-8")
    write_side_outputs(alignment, method, findings, findings_label, out_path.parent)
    return out_path
