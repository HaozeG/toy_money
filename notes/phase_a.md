# Phase A result

Live cache: `refresh-data` run **34331709154** (branch, 2026-09-09). Numbers are in
`artifacts/findings.{bubble_peak,workingage_peak}.json` and the report table — not
repeated here.

## Live vs. seed — what it shows

`tests/test_live_vs_seed.py` passed in the Action for all 9 provider-backed series
(no value off the seed snapshot beyond tolerance).

It catches provider **revisions** and a key that **starts** returning different
values. It does **not** prove the keys were right originally: the provider-backed
seed is itself a snapshot of an earlier fetch with the same keys (`seed/README.md`),
so an always-wrong key sits in both and passes.

Remaining wrong-key defences: `sources/bis.py` rejects a response whose dimension
columns don't match the request; `toy-money verify` prints URLs + rows for a human —
**the only check on the dimension choice**.

## BIS — to check against stats.bis.org (`toy-money verify`)

`WS_TC` key = `Q . {CN|JP} . {H|N} . A . M . 770` (freq, country, borrower,
all-lenders, market value, % of GDP). `WS_SPP` = `Q . {CN|JP} . R . 628` (real).

| series | CHN sample (year, value) |
|---|---|
| `credit_hh_gdp` | 2006 10.9 · 2016 41.4 · 2025 59.2 |
| `credit_nfc_gdp` | 2006 99.4 · 2016 148.1 · 2025 142.3 |
| `real_property_prices` | 2005 89.1 · 2016 98.0 · 2026 85.1 (raw BIS 2010=100) |

Open: confirm `TC_LENDERS=A`, `VALUATION=M`, `WS_SPP` unit `628` are the intended
concepts.

## Reading — numbers only, no verdict

**`bubble_peak` (China 2021 ↔ Japan 1990) has only ~5 post-anchor years of China
data against Japan's 35.** Too short for a trajectory claim; it shows where China
sits now, not whether it is on Japan's path. Use **`workingage_peak`** (16
post-anchor years) for any trajectory reading.

`MAX_YEAR` now stops at the last completed year. Before this, China's `gov_debt_gdp`
reference point landed on **2026 — an IMF projection** (106.9%) instead of realised
2025 (99.2%).

Direction flips between the two alignments on 5 of 9 indicators (working-age share,
gov debt, both credit series). Which alignment is the right analogue is a Phase B1
question — see the report table's two anchor columns.
