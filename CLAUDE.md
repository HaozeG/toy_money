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
uv run toy-money fetch --source seed     # materialise bundled fallback snapshot
uv run toy-money pull-cache              # download cache from the refresh-data Action (firewall workaround)
uv run toy-money build                   # render artifacts/china_japan.html
uv run toy-money build --anchor workingage_peak     # alternate alignment
uv run toy-money build --anchor-jpn 1991 --anchor-chn 2021   # explicit anchors
uv run toy-money build --method precedent           # pick the analysis method
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
   `.meta.json` — the sidecars carry provenance; without them `provenance()`
   returns `unknown` and the report flags the panel). `pull-cache` wraps
   `gh run download` to fetch it.
   Trigger a fresh run with `gh workflow run refresh-data.yml`.
2. **HTTP(S) proxy**, if a tunnel is available: `_http.py` uses `requests`, which
   honours `HTTPS_PROXY` / `ALL_PROXY` automatically — `HTTPS_PROXY=… uv run
   toy-money fetch` needs no code change (add `pysocks` for `socks5://`).

The `refresh-data` Action log is the **live integration test** of `sources/*.py`.
The latest run fetched all 9 provider-backed series successfully; the next run
will exercise the new BIS dimension validation. The BIS flow/dimension choice
still deserves a human review when adding a new series.

## Architecture

Pipeline: `sources/*` fetch → `datastore` caches as parquet → `align` transforms →
`analysis` states the conclusion → `report` renders one self-contained HTML file.

- **`config.py` is the single source of truth.** `SERIES` (the indicator table) and
  `ANCHOR_PRESETS` live here. Add an indicator by appending a `Series(...)` row, not by
  touching the pipeline. Each `Series` also declares `compare_as` — `"level"` (ratios/
  rates, natively comparable), `"indexed_to_anchor"` (index numbers on a provider base
  — re-scaled to 100 at each country's anchor year), or `"slope"` (only the trajectory
  compares; the level gap is itself a finding). Analyzers read this to do the right
  thing per indicator without re-deriving the economics.
- **`sources/`**: one adapter per provider, each exposing
  `fetch(series) -> DataFrame[country, year, value]`. World Bank and IMF DataMapper are
  keyless. BIS uses the SDMX CSV API; `bis.py` validates the dimension values the API
  echoes back (country, borrower type, valuation, unit) so a wrong key cannot silently
  masquerade as a correct series. A new BIS flow still needs a human check against
  https://stats.bis.org. FRED (`sources/fred.py`) is **optional**: used only when
  `FRED_API_KEY` is set, not wired into the default `SERIES`.
- **`datastore.py`**: canonical schema is `[country, year, value]` (annual). `read()`
  falls back to bundled `src/toy_money/seed/seed.csv` when a series is not cached.
  `provenance()` returns `live`, `seed`, `unknown` (parquet without a `.meta.json`), or
  `missing`; the report surfaces non-live panels.
- **`align.py`**: re-expresses each country on a "years since anchor" axis
  (`t = year - anchor[country]`); `apply_comparison_basis` then applies `compare_as`.
  `MAX_YEAR` is the last completed calendar year, so current-year IMF/BIS
  forecasts/partials are not treated as realised data.
- **`analysis.py`**: turns aligned panels into stated conclusions. The **reference
  point is China's latest observation** — every `Finding` answers "given where China is
  now, what does the Japan precedent say?". An analyzer is any
  `(panels, alignment) -> list[Finding]`; register it in `ANALYZERS`. `precedent` is the
  first. `Finding` is the stable contract the report renders — add a second method
  before generalising the interface, not before. **Deliberate non-features:** no
  aggregate similarity score; no probability (n=1 precedent); **no tracks/diverges
  verdict** — that binary needs a similarity band, and every level-relative band is
  scale-biased (a ~67-base indicator and a ~3-base one with the same shape agreement get
  opposite verdicts). A `Finding` instead carries the numbers — `direction` (China vs
  Japan at matched t), `n_overlap`, `jpn_forward` (Japan's next ≤10 years, *precedent
  not forecast*) — and `verdict` is only `compared` or `indeterminate` (< `MIN_OVERLAP`
  overlapping years, or no Japan observation at China's reference t). Overlap is counted
  inside `ANALYSIS_WINDOW` (`t=-25..35`), the same window the figure shows. The headline
  counts *directions* (arithmetic). The report recomputes `direction` under **all** anchor
  presets; a direction that flips is the finding. **Remaining soft spot:** BIS dimension
  values are validated against the returned CSV, but the flow/dimension choice still
  needs a human check when a new BIS series is added.
- **`report.py`**: `prepared_panels()` (from `analysis`) is the shared input for both
  the figure and the analyzers. Chart follows the `dataviz` skill — shared x-axis
  across the grid, CVD-validated palette, grey band marking t beyond China's data.

## Things that will bite you

- **The anchor year is a parameter, never a hardcode.** Different anchors (bubble peak
  vs. working-age-share peak vs. a chosen year) yield different verdicts on "is China
  Japan". Analysis code must take the anchor as input; presets live in `config.py`.
- **`data/` is a gitignored cache.** `fetch` writes it, `build` reads it. Never commit
  it. Deleting it is safe — `build` then reads the bundled fallback snapshot directly.
- **Seed data is a fallback snapshot, not live data.** `seed/seed.csv` contains a
  snapshot of provider-backed series plus hand-seeded `grad_labor`; see
  `seed/README.md`. It is not a substitute for a real `fetch`. When `fetch` can't reach
  a provider it writes the fallback values into the cache with a `WARN`.
- **Current-year forecasts are not history.** `MAX_YEAR` excludes the current calendar
  year, and overlap is counted only in `ANALYSIS_WINDOW`; if you change either, update
  the report footer and tests together.
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
