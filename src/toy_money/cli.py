"""toy-money CLI: `fetch` refreshes the local cache, `build` renders the report."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from . import datastore, sources
from .align import resolve_alignment
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
    out = Path(args.out) if args.out else (ARTIFACTS_DIR / "china_japan.html")
    try:
        path = build_report(alignment, out)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"wrote {path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="toy-money", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    pf = sub.add_parser("fetch", help="refresh the local data cache")
    pf.add_argument(
        "--source",
        default="all",
        choices=["all", "seed", *sources.SOURCE_NAMES],
        help="limit fetch to one source (default: all)",
    )
    pf.add_argument("--force", action="store_true", help="re-download cached series")
    pf.set_defaults(func=_cmd_fetch)

    pb = sub.add_parser("build", help="render the HTML comparison report")
    pb.add_argument("--anchor", help="named anchor preset (default: %(default)s)",
                    default=None)
    pb.add_argument("--anchor-jpn", type=int, help="explicit Japan anchor year")
    pb.add_argument("--anchor-chn", type=int, help="explicit China anchor year")
    pb.add_argument("--out", help="output HTML path")
    pb.set_defaults(func=_cmd_build)

    pp = sub.add_parser(
        "pull-cache",
        help="download the data cache built by the refresh-data GitHub Action "
        "(for when the data providers are blocked locally)",
    )
    pp.add_argument("--run", help="specific workflow run id (default: newest)")
    pp.add_argument("--repo", help="OWNER/REPO (default: the repo's origin remote)")
    pp.set_defaults(func=_cmd_pull_cache)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
