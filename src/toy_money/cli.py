"""toy-money CLI: `fetch` refreshes the local cache, `build` renders the report."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from . import datastore, sources
from .align import resolve_alignment
from .analysis import ANALYZERS
from .config import DATA_DIR, ARTIFACTS_DIR, DEFAULT_ANCHOR, SERIES
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

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
