# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`toy_money` tests the question *"is this time really different, or does historical
precedent still apply?"* against macro data. It is **hypothesis-testing against
historical analogues, not backtesting** — there is no trading strategy. Phase 1 is a
single vertical slice: **China now vs. Japan 1990s**, testing the claim that China is
retracing Japan's post-bubble path.

## Commands

```bash
uv sync --extra dev                      # set up the environment
uv run toy-money fetch                   # refresh data cache (data/*.parquet)
uv run toy-money fetch --source worldbank --force   # one source, ignore cache
uv run toy-money fetch --source seed     # materialise offline seed data only
uv run toy-money pull-cache              # download cache from the refresh-data Action (firewall workaround)
uv run toy-money build                   # render artifacts/china_japan.html
uv run toy-money build --anchor workingage_peak     # alternate alignment
uv run toy-money build --anchor-jpn 1991 --anchor-chn 2021   # explicit anchors
uv run pytest -q                         # all tests
uv run pytest tests/test_align.py::test_align_shifts_to_years_since_anchor
```

## Network / firewall

The dev machine sits behind a content-filtering gateway (`1.1.1.3` block page,
category 非营利组织) that resets TLS to `api.worldbank.org`, `www.imf.org`,
`stats.bis.org`, `fred.stlouisfed.org`, `ourworldindata.org`. `github.com`,
`api.github.com`, `objects.githubusercontent.com`, `pypi.org`, `huggingface.co`
are reachable. It is a network-policy block, not a technical fault.

Two ways to get live data:

1. **`toy-money pull-cache`** (default path). `.github/workflows/refresh-data.yml`
   runs `toy-money fetch` on GitHub's runners (outside the gateway) monthly / on
   `workflow_dispatch` and uploads a `data-cache` artifact (parquet **+**
   `.meta.json` — the sidecars carry provenance; without them seed data would
   claim official sources). `pull-cache` wraps `gh run download` to fetch it.
   Trigger a fresh run with `gh workflow run refresh-data.yml`.
2. **HTTP(S) proxy**, if a tunnel is available: `_http.py` uses `requests`, which
   honours `HTTPS_PROXY` / `ALL_PROXY` automatically — `HTTPS_PROXY=… uv run
   toy-money fetch` needs no code change (add `pysocks` for `socks5://`).

The `refresh-data` Action log is also the **first real integration test** of
`sources/*.py` — those adapters were written against documented API shapes and
have never seen a live response. BIS is most likely to need fixes.

## Architecture

Pipeline: `sources/*` fetch → `datastore` caches as parquet → `align` transforms →
`report` renders one self-contained HTML file.

- **`config.py` is the single source of truth.** `SERIES` (the indicator table) and
  `ANCHOR_PRESETS` live here. Add an indicator by appending a `Series(...)` row, not by
  touching the pipeline.
- **`sources/`**: one adapter per provider, each exposing
  `fetch(series) -> DataFrame[country, year, value]`. World Bank and IMF DataMapper are
  keyless. BIS uses the SDMX CSV API — its dimension keys in `sources/bis.py` are
  best-effort and marked to VERIFY against https://stats.bis.org. FRED
  (`sources/fred.py`) is **optional**: used only when `FRED_API_KEY` is set, not wired
  into the default `SERIES`.
- **`datastore.py`**: canonical schema is `[country, year, value]` (annual). `read()`
  falls back to bundled `src/toy_money/seed/seed.csv` when a series is not cached.
- **`align.py`**: the analytical core. Re-expresses each country on a "years since
  anchor" axis (`t = year - anchor[country]`) so the curves overlay.

## Things that will bite you

- **The anchor year is a parameter, never a hardcode.** Different anchors (bubble peak
  vs. working-age-share peak vs. a chosen year) yield different verdicts on "is China
  Japan". Analysis code must take the anchor as input; presets live in `config.py`.
- **`data/` is a gitignored cache.** `fetch` writes it, `build` reads it. Never commit
  it. Deleting it is safe — `build` then reads seed data directly.
- **Seed data is approximate.** `seed/seed.csv` is hand-entered from national sources
  so the tool runs offline; it is not a substitute for a real `fetch`. When `fetch`
  can't reach a provider it writes the seed values into the cache with a `WARN`.
- **China youth-unemployment methodology break (2023):** NBS suspended the 16–24 urban
  series mid-2023 and resumed in 2024 excluding students. The report annotates this via
  `Series.note`; keep that caveat visible in any new youth-labour work.
- **Japanese labour sources** (求人倍率 / MHLW) are Japanese-language; `grad_labor` is
  seed-only for now.

## Scope boundary (Phase 1)

In scope: China/Japan macro comparison from official keyless APIs → HTML.

Explicitly deferred — **do not build without a new decision**:
- social-media topic/keyword scraping (weibo/zhihu/xiaohongshu) — research existing
  tools first
- RAG knowledge base — would start as a `notes/` markdown dir, retrieval only if needed
- additional countries or historical episodes
