# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`toy_money` tests the question *"is this time really different, or does historical
precedent still apply?"* against macro data. It is **hypothesis-testing against
historical analogues, not backtesting** — there is no trading strategy. Phase 1 is a
single vertical slice: **China now vs. Japan 1990s**, testing the claim that China is
retracing Japan's post-bubble path.

## Working rules

- **Anchor years stay parameters.** In Phase B they become *rules computed from data*
  (property-price peak, working-age-share peak), applied identically to every episode.
  Never type a year into analysis code.
- **No aggregate similarity score, no probability.** Findings carry numbers; the
  report states them. n=1 precedent supports neither.
- **No scoreboard in the headline.** Counting above/below directions is arithmetic,
  but a reader takes a tally as a verdict. The headline names what was compared and
  under which anchors; the per-indicator table carries the directions.
- Every design decision is recorded under `## Decisions` below, one line + reason.
- Social-media scraping and the RAG knowledge base stay out of scope.

## Commands

```bash
uv sync --extra dev                      # set up the environment
uv run toy-money fetch                   # refresh data cache (data/*.parquet)
uv run toy-money fetch --source worldbank --force   # one source, ignore cache
uv run toy-money fetch --source seed     # materialise bundled fallback snapshot
uv run toy-money pull-cache              # download cache from the refresh-data Action (firewall workaround)
uv run toy-money verify                  # print BIS request URLs + sample rows for a human to check
uv run toy-money build                   # render artifacts/china_japan.html + findings.<anchor>.json + cache_manifest.json
uv run toy-money build --anchor workingage_peak     # alternate alignment
uv run toy-money build --anchor-jpn 1991 --anchor-chn 2021   # explicit anchors
uv run toy-money build --method precedent           # pick the analysis method
uv run pytest -q                         # all tests
uv run pytest tests/test_live_vs_seed.py -q         # live parquet vs seed (skips without a live cache)
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
The latest branch run fetched all 9 provider-backed series successfully and
exercised the BIS dimension validation against the live SDMX CSV. The BIS
flow/dimension choice still deserves a human review when adding a new series.

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
  (`t = year - anchor[country]`); `apply_comparison_basis` then applies `compare_as`
  (`level` unchanged; `indexed_to_anchor` → 100 at each country's anchor;
  `slope` → `log(value / value_at_anchor)`, a cumulative log-change trajectory).
  `MAX_YEAR` is the last completed calendar year, so current-year IMF/BIS
  forecasts/partials are not treated as realised data.
- **`analysis.py`**: turns aligned panels into stated conclusions. The **reference
  point is China's latest observation** — every `Finding` answers "given where China is
  now, what does the Japan precedent say?". An analyzer is any
  `(panels, alignment) -> list[Finding]`; register it in `ANALYZERS`. `precedent` is the
  first. `Finding` is the stable contract the report renders — add a second method
  before generalising the interface, not before. **Deliberate non-features:** no
  aggregate similarity score; no probability (n=1 precedent); **no tracks/diverges
  verdict** (see Working rules); **no scoreboard in the headline**. A `Finding` carries
  the numbers — `direction` (China vs Japan at matched t, using the per-series absolute
  `Series.band` for a `crossing` call; `band=None` ⇒ above/below only),
  `n_pre`/`n_post` (overlap split at the anchor), `jpn_forward` (Japan's next ≤10 years,
  *precedent not forecast*), `level_gap_at_anchor` (for `compare_as="slope"`, where the
  level gap is a finding in its own right). `verdict` is only `compared` or
  `indeterminate` (**gate: `n_post >= MIN_POST`** — the hypothesis is about the
  *post-anchor* path, so pre-anchor years do not count; also indeterminate when Japan
  has no observation at China's reference t). Overlap is counted inside `ANALYSIS_WINDOW`
  (`t=-25..35`), the same window the figure shows. The report recomputes `direction`
  under **all** anchor presets; a direction that flips is the finding.
  - `MIN_POST = 3` is a **placeholder** — a floor for "can say anything". Phase B1 sets
    the comparison window per sub-hypothesis and this should follow from that.
  - **Under `bubble_peak` every indicator has only ~5 post-anchor years** (China's 2021
    anchor vs `MAX_YEAR`): thin for a *trajectory* claim. `workingage_peak` (2010) gives ~16.
- **`report.py`**: `prepared_panels()` (from `analysis`) is the shared input for both
  the figure and the analyzers; each `PreparedPanel` carries `df` (comparison-basis
  applied) and `raw_df` (aligned, native units). Chart follows the `dataviz` skill —
  shared x-axis, CVD-validated palette, grey band marking t beyond China's data.
  `build` also writes `artifacts/findings.<anchor>.json` (per alignment) and
  `artifacts/cache_manifest.json` (anchor-independent: provenance, rows, year range,
  parquet sha256) — the reviewable outputs; the HTML (`include_plotlyjs="cdn"`) stays
  gitignored.
- **BIS trust chain**: `sources/bis.py` `_validate_dimensions` rejects a response
  whose echoed dimension columns don't match the requested key.
  `tests/test_live_vs_seed.py` (run in `refresh-data.yml`) catches **divergence from
  the seed snapshot** — a provider revision or a key that *starts* returning different
  values — but not original wrong-key selection, since the provider-backed seed rows
  are themselves a snapshot of an earlier fetch through the same code
  (`seed/README.md`). `toy-money verify` prints URLs + rows for a human to check the
  dimension *choice* against stats.bis.org — **the only check on the choice itself**,
  and it needs re-running when a new BIS series is added.

## Things that will bite you

- **The anchor year is a parameter, never a hardcode.** Different anchors (bubble peak
  vs. working-age-share peak vs. a chosen year) yield different directions on "is China
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

## Decisions

- **`compare_as="slope"` = `log(value / value_at_anchor)`** — the trajectory compares;
  the anchor-level gap is recorded on the `Finding` (`level_gap_at_anchor`) and shown
  in the panel text. The GDP-per-capita chart panel is therefore a log-change
  trajectory, not "$ on a log axis". *Reason:* the config always said "the level gap
  is itself a finding"; this makes both true.
- **`Series.band` is absolute, per series, in native units** (`gdp_growth` 0.5 pp,
  `workingage_share` 0.3 pp, `cpi_inflation` 0.5 pp, `gov_debt_gdp` 3, `credit_hh_gdp`
  2, `credit_nfc_gdp` 3, `real_property_prices` 3, `youth_unemployment` 1;
  `gdp_pc_ppp` `None`). *Reason:* a relative band is scale-biased — the module's own
  objection; a `crossing` call should mean "within revision noise of equal".
- **Verdict gate is `n_post >= MIN_POST`; `MIN_OVERLAP` deleted.** *Reason:* the
  hypothesis is about the post-anchor path, so pre-anchor overlap must not decide the
  verdict.
- **`headline()` states scope only, no direction tally.** *Reason:* Working rules — a
  reader takes a count as a verdict.
- **Reviewable outputs = JSON, HTML stays gitignored.** `findings.<anchor>.json` +
  `cache_manifest.json` committed; HTML switched to `include_plotlyjs="cdn"` (~40 KB)
  but not committed. *Reason:* a single-line minified HTML blob is not a useful diff.
- **`findings.<label>.json` is per anchor preset** (`custom` for explicit anchors);
  `cache_manifest.json` is single (provenance/rows/years/sha256 are pre-alignment).
- **`gov_debt_gdp.definition_note`**: IMF `GGXWDG_NGDP` is not definition-comparable
  Japan-1990 vs China-now (LGFV / off-balance-sheet). Rendered with the panel.

## Scope boundary (Phase 1)

In scope: China/Japan macro comparison from official keyless APIs → HTML.

Explicitly deferred — **do not build without a new decision**:
- social-media topic/keyword scraping (weibo/zhihu/xiaohongshu) — research existing
  tools first
- RAG knowledge base — would start as a `notes/` markdown dir, retrieval only if needed
- additional countries or historical episodes
