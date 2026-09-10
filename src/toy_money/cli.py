"""toy-money CLI: `fetch` refreshes the local cache, `build` renders the report."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from . import datastore, sources
from .align import anchor_year, resolve_alignment
from .analysis import ANALYZERS
from .config import (
    DATA_DIR,
    ARTIFACTS_DIR,
    DEFAULT_ANCHOR,
    EPISODES,
    FETCH_COUNTRIES,
    SERIES,
)
from .report import build_report


def _write_seed(key: str) -> bool:
    seed = datastore.seed_frame(key)
    if seed is None:
        return False
    datastore.write(key, seed, provenance="seed")
    return True


def _cmd_fetch(args: argparse.Namespace) -> int:
    src = args.source
    selected = [
        s for s in SERIES
        if src in ("all", "seed") or s.source == src
    ]
    if not selected:
        print(f"no series use source '{src}'", file=sys.stderr)
        return 2

    live_ok = seed_ok = fell_back = failed = 0
    for s in selected:
        if datastore.has(s.key) and not args.force and src != "seed":
            print(f"  skip  {s.key} (cached; use --force)")
            continue
        if src == "seed" or s.source == "seed":
            if _write_seed(s.key):
                print(f"  seed  {s.key}")
                seed_ok += 1
            else:
                print(f"  FAIL  {s.key}: no seed CSV bundled")
                failed += 1
            continue
        try:
            df = sources.fetch(s)
            datastore.write(s.key, df)
            print(f"  ok    {s.key}: {len(df)} rows via {s.source}")
            live_ok += 1
        except Exception as exc:  # noqa: BLE001 - one bad source must not abort the rest
            if _write_seed(s.key):
                print(f"  WARN  {s.key}: {s.source} failed ({exc}); wrote seed fallback")
                fell_back += 1
            else:
                print(f"  FAIL  {s.key}: {s.source} failed ({exc}); no seed available")
                failed += 1
    print(
        f"\nfetch complete: {live_ok} live, {seed_ok} seed, "
        f"{fell_back} fell back to seed after failure, {failed} failed"
    )
    # A live fetch that silently degraded to seed is not a success.
    return 0 if (failed == 0 and fell_back == 0) else 1


def _cmd_pull_cache(args: argparse.Namespace) -> int:
    """Download the parquet cache built by the `refresh-data` GitHub Action.

    Used when api.worldbank.org / stats.bis.org etc. are blocked locally but
    github.com is reachable. The Action fetches on GitHub's runners and uploads
    a `data-cache` artifact; this pulls the newest one into data/.
    """
    if not shutil.which("gh"):
        print(
            "the GitHub CLI (`gh`) is required. Install: https://cli.github.com "
            "then `gh auth login`.",
            file=sys.stderr,
        )
        return 2
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    cmd = ["gh", "run", "download", "--name", "data-cache", "--dir", str(DATA_DIR)]
    if args.run:
        cmd += [args.run]
    if args.repo:
        cmd += ["--repo", args.repo]
    print("$ " + " ".join(cmd))
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(
            "\ndownload failed. Has the `refresh-data` workflow run yet? "
            "Trigger it with `gh workflow run refresh-data.yml`.",
            file=sys.stderr,
        )
        return 1
    live = sum(1 for s in SERIES if datastore.provenance(s.key) == "live")
    print(f"\npulled cache into {DATA_DIR} — {live}/{len(SERIES)} series live")
    return 0


def _cmd_build(args: argparse.Namespace) -> int:
    overrides = {}
    if args.anchor_jpn:
        overrides["JPN"] = args.anchor_jpn
    if args.anchor_chn:
        overrides["CHN"] = args.anchor_chn
    if args.method == "episodes":
        print(
            "the 'episodes' analyzer is not a bilateral report; run "
            "`toy-money episodes` instead",
            file=sys.stderr,
        )
        return 2
    preset = None if overrides and not args.anchor else (args.anchor or DEFAULT_ANCHOR)
    try:
        alignment = resolve_alignment(preset, overrides or None)
    except (KeyError, ValueError) as exc:
        print(f"anchor error: {exc}", file=sys.stderr)
        return 2
    label = preset if preset and not overrides else "custom"
    out = Path(args.out) if args.out else (ARTIFACTS_DIR / "china_japan.html")
    try:
        path = build_report(alignment, out, method=args.method, findings_label=label)
    except (RuntimeError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"wrote {path}")
    print(f"wrote {path.parent / f'findings.{label}.json'}")
    print(f"wrote {path.parent / 'cache_manifest.json'}")
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    """Print, for each BIS series, the exact request URL(s) and three sample rows
    from the cache, so a human can check them against the stats.bis.org UI.

    The dev machine cannot reach BIS — this is a print-and-hand-off command. An
    Action fetch exiting 0 means HTTP succeeded and rows parsed; it does not prove
    the SDMX key selected the intended series.
    """
    from .sources import bis

    any_bis = False
    for s in SERIES:
        if s.source != "bis":
            continue
        any_bis = True
        print(f"\n=== {s.key} — {s.label} ({s.unit}) ===")
        for country, url in bis.request_urls(s):
            print(f"  {country}: {url}")
        try:
            df = datastore.read(s.key)
        except FileNotFoundError:
            print("  (no cache — run `toy-money pull-cache` first)")
            continue
        for country in sorted(df["country"].unique()):
            g = df[df["country"] == country].sort_values("year")
            picks = g.iloc[[0, len(g) // 2, -1]] if len(g) >= 3 else g
            rows = ", ".join(
                f"({r.country}, {int(r.year)}, {r.value:.3f})"
                for r in picks.itertuples()
            )
            print(f"  sample {country}: {rows}")
    if not any_bis:
        print("no BIS series in SERIES")
    return 0


def _cmd_coverage(args: argparse.Namespace) -> int:
    """Per series x country: provenance and year span in the cache. The B2
    deliverable — shows whether each episode has the data its anchor rule and
    comparison window need, and which BIS series are absent per country.
    """
    countries = list(FETCH_COUNTRIES)
    print(f"{'series':24} {'prov':6} " + " ".join(f"{c:>11}" for c in countries))
    for s in SERIES:
        prov = datastore.provenance(s.key)
        try:
            df = datastore.read(s.key)
        except FileNotFoundError:
            df = None
        cells = []
        for c in countries:
            if df is None:
                cells.append(f"{'-':>11}")
                continue
            g = df[df["country"] == c]
            if g.empty:
                cells.append(f"{'MISSING':>11}")
            else:
                cells.append(f"{int(g.year.min())}-{int(g.year.max()):>4}")
        print(f"{s.key:24} {prov:6} " + " ".join(cells))
    print()
    print("Episode      rule             window       -> anchor year (or why not)")
    for e in EPISODES:
        lo, hi = e.search_window
        res = anchor_year(e.iso3, e.anchor_rule, e.search_window)
        got = str(res.year) if res.year is not None else f"— {res.reason}"
        print(
            f"  {e.set_name:15} {e.iso3}  {e.anchor_rule:16} {lo}-{hi}  ->  {got}"
        )
    return 0


def _cmd_episodes(args: argparse.Namespace) -> int:
    """Run the `episodes` analyzer: China's Δ-from-anchor at each post-anchor year
    against the distribution of comparable episodes. Prints a compact table and
    writes artifacts/episodes.json.
    """
    import dataclasses
    import json

    from .analysis import episodes

    findings = episodes([], None)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    out = ARTIFACTS_DIR / "episodes.json"
    out.write_text(
        json.dumps(
            {"findings": [dataclasses.asdict(f) for f in findings]},
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    last_hyp = None
    for f in findings:
        if f.hypothesis != last_hyp:
            print(f"\n=== {f.hypothesis} (horizon t={f.horizon}) ===")
            last_hyp = f.hypothesis
        gap = ", ".join(f"{k}: {v}" for k, v in f.unavailable.items())
        print(f"\n  {f.key} — {f.label} [{f.compare_as}]")
        if gap:
            print(f"    unavailable: {gap}")
        shown = sorted(set(f.chn) | {f.horizon})
        for t in shown:
            d = f.distribution.get(t)
            if not d:
                continue
            chn = f.chn.get(t)
            rank = f.chn_rank.get(t)
            chn_s = (
                f"CHN {chn:+.1f} (>{rank[0]}/{rank[1]})"
                if chn is not None and rank
                else "CHN —"
            )
            jpn = f.jpn.get(t)
            jpn_s = f"JPN {jpn:+.1f}" if jpn is not None else "JPN —"
            print(
                f"    t={t:2}  n={d['n']}  "
                f"[{d['min']:+.1f} .. {d['median']:+.1f} .. {d['max']:+.1f}]  "
                f"{chn_s}  {jpn_s}"
            )
    print(f"\nwrote {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="toy-money", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    pf = sub.add_parser("fetch", help="refresh the local data cache")
    pf.add_argument(
        "--source",
        default="all",
        choices=["all", "seed", *sources.SOURCE_NAMES],
        help="limit fetch to one source (default: all; 'seed' writes the bundled snapshot)",
    )
    pf.add_argument("--force", action="store_true", help="re-download cached series")
    pf.set_defaults(func=_cmd_fetch)

    pb = sub.add_parser("build", help="render the HTML comparison report")
    pb.add_argument("--anchor", help="named anchor preset (default: %(default)s)",
                    default=None)
    pb.add_argument("--anchor-jpn", type=int, help="explicit Japan anchor year")
    pb.add_argument("--anchor-chn", type=int, help="explicit China anchor year")
    pb.add_argument("--out", help="output HTML path")
    pb.add_argument(
        "--method",
        default="precedent",
        choices=sorted(ANALYZERS),
        help="analysis method for the stated conclusion (default: %(default)s)",
    )
    pb.set_defaults(func=_cmd_build)

    pp = sub.add_parser(
        "pull-cache",
        help="download the data cache built by the refresh-data GitHub Action "
        "(for when the data providers are blocked locally)",
    )
    pp.add_argument("--run", help="specific workflow run id (default: newest)")
    pp.add_argument("--repo", help="OWNER/REPO (default: the repo's origin remote)")
    pp.set_defaults(func=_cmd_pull_cache)

    pv = sub.add_parser(
        "verify",
        help="print BIS request URLs + sample cache rows for a human to check "
        "against stats.bis.org (the dev machine cannot reach BIS)",
    )
    pv.set_defaults(func=_cmd_verify)

    pc = sub.add_parser(
        "coverage",
        help="per series x country: provenance and year span in the cache "
        "(shows which episodes have the data their anchor rule needs)",
    )
    pc.set_defaults(func=_cmd_coverage)

    pe = sub.add_parser(
        "episodes",
        help="China's Δ-from-anchor vs the distribution of comparable episodes "
        "(writes artifacts/episodes.json)",
    )
    pe.set_defaults(func=_cmd_episodes)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
