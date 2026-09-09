# Phase A result

Live cache: `refresh-data` run **34331709154** (branch `fix/live-validation`,
2026-09-09). Committed outputs: `artifacts/findings.bubble_peak.json`,
`artifacts/findings.workingage_peak.json`, `artifacts/cache_manifest.json`.

## Live vs. seed

`tests/test_live_vs_seed.py` ran in the Action after the fetch and **passed for all
9 provider-backed series** — no live value disagreed with the hand-checked seed
snapshot beyond tolerance (1.5 pp absolute for growth-rate/share series, 10 %
relative otherwise, one outlier allowed). `grad_labor` is seed-only and not
checked.

So the World Bank / IMF / BIS keys currently in `config.py` select series whose
values match what was hand-verified for the seed. This does **not** by itself prove
the BIS *flow/dimension choice* is the intended economic concept — that still needs
the human check below.

## BIS rows to check against stats.bis.org (`toy-money verify`)

| series | request URL (CHN) | sample rows |
|---|---|---|
| `credit_hh_gdp` | `.../WS_TC/Q.CN.H.A.M.770/all?format=csv` | CHN (2006, 10.85) (2016, 41.43) (2025, 59.23); JPN (1964, 20.10) (1995, 68.48) (2025, 61.33) |
| `credit_nfc_gdp` | `.../WS_TC/Q.CN.N.A.M.770/all?format=csv` | CHN (2006, 99.40) (2016, 148.13) (2025, 142.25); JPN (1964, 90.70) (1995, 139.93) (2025, 111.68) |
| `real_property_prices` | `.../WS_SPP/Q.CN.R.628/all?format=csv` | CHN (2005, 89.07) (2016, 98.03) (2026, 85.13); JPN (1955, 13.35) (1990, 184.64) (2025, 122.62) |

`WS_TC` key layout `FREQ.BORROWERS_CTY.TC_BORROWERS.TC_LENDERS.VALUATION.UNIT_TYPE`
= `Q . {CN|JP} . {H|N} . A(all lenders) . M(market value) . 770(% of GDP)`.
`WS_SPP` = `Q . {CN|JP} . R(real) . 628`. Property-price values are BIS's own
2010 = 100 index (re-indexed to the anchor only at build time).

**Open**: confirm `TC_LENDERS=A` / `VALUATION=M` and `WS_SPP` unit `628` are the
intended definitions for a "China vs Japan bubble" comparison, not e.g. nominal
value or a narrower lender set. The dimension *values* are validated
(`sources/bis.py`); the *choice* is not.

## Reading of the live-data report — numbers only, no verdict

**Read the `bubble_peak` alignment with its limit in mind first.** China's anchor
is 2021 and `MAX_YEAR` is 2025, so every indicator has only **4–5 post-anchor
years** of China data to set against Japan's ~35. Five points is too short to
characterise a *trajectory*; the `bubble_peak` directions below describe where
China sits now, not whether it is on Japan's path. The `workingage_peak` alignment
(China anchor 2010) gives **16** post-anchor years and is the one to weight for any
trajectory reading.

`MAX_YEAR` matters here: before it was pinned to the last completed year, China's
`gov_debt_gdp` reference point landed on **2026**, an IMF WEO *projection*
(106.9 % vs the realised 2025 value 99.2 %). Current-year and forward IMF/BIS
values are now excluded from "China's latest observation".

**`bubble_peak` (China 2021 ↔ Japan 1990), at China's t = 4 (2025) vs Japan's t = 4
(1994):**
- Real GDP growth 4.96 % vs 0.99 %; working-age share 69.7 vs 69.9 (within band);
  GDP/capita cumulative real growth since anchor +18 log-pts vs +3; CPI 0.06 % vs
  0.70 %; gov gross debt 99.2 % of GDP vs 73.3 %; household credit 59.2 % of GDP vs
  68.2 %; non-financial corporate credit 142.3 % vs 141.7 % (within band); real
  house prices 80.0 vs 87.4 (each re-indexed to 100 at its own peak);
  youth unemployment 15.8 % vs 5.5 %.
- Japan's subsequent decade from that point (t = 5 → 14, precedent not forecast):
  house prices 86 → 61, corporate credit 140 → 99, household credit 68 → 65,
  gov debt 81 → 149, working-age share 69.7 → 66.5, CPI ≈ 0, growth ≈ 2 %.

**`workingage_peak` (China 2010 ↔ Japan 1992), at China's t = 15 (2025) vs Japan's
t = 15 (2007):**
- GDP growth 4.96 % vs 1.73 %; working-age share 69.7 vs 64.8; GDP/capita
  cumulative growth +87 log-pts vs +14; CPI 0.06 % vs 0.06 % (within band); gov
  debt 99.2 % vs 150.4 %; household credit 59.2 % vs 59.9 % (within band);
  corporate credit 142.3 % vs 98.9 %; real house prices 89.5 vs 58.6 (re-indexed);
  youth unemployment 15.8 % vs 7.9 %.
- Japan's next decade from t = 15 (t = 16 → 25): gov debt 154 → 203, working-age
  share 64 → 59, house prices flat ≈ 57–60, corporate credit 101 → 95, household
  credit ≈ flat, youth unemployment 7.3 → 4.6.

The direction on several indicators (`workingage_share`, `gov_debt_gdp`,
`credit_nfc_gdp`, `credit_hh_gdp`) flips between the two alignments — recorded in
the report's anchor matrix. Which alignment is the right analogue is a Phase B1
question.
