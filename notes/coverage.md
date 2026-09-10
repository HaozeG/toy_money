# B2 coverage — does each episode have the data its anchor rule needs?

Cache: `refresh-data` run 34446738285 (2026-09-10), 13 fetch countries.
Full matrix: `toy-money coverage`. Per-country year spans: `cache_manifest.json`.

## Anchor rule dry run (property_peak / workingage_peak over each search window)

| episode | rule | window | year picked | ≥3y decline | note |
|---|---|---|---|---|---|
| JPN 1990s | property_peak | 1988–1994 | **1991** | yes | |
| Finland | property_peak | 1987–1993 | **1989** | yes | |
| Sweden | property_peak | 1987–1993 | **1990** | yes | |
| US 2008 | property_peak | 2004–2009 | **2006** | yes | |
| UK 2008 | property_peak | 2004–2009 | **2007** | yes | |
| Spain 2008 | property_peak | 2004–2009 | **2007** | yes | |
| Ireland 2008 | property_peak | 2004–2009 | **2007** | yes | |
| China now | property_peak | 2019–2024 | **2021** | yes | |
| Japan | workingage_peak | 1988–1996 | **1992** | yes | |
| Korea | workingage_peak | 2010–2020 | **2016** | yes | |
| Taiwan | workingage_peak | 2010–2018 | — | — | **no data** — World Bank / IMF / BIS exclude Taiwan; even `workingage_share` (the anchor series) is absent. Episode stays declared; the analyzer marks it unavailable. |
| Germany | workingage_peak | 1982–1992 | **1986** | yes | |
| Italy | workingage_peak | 1988–1996 | **1992** | yes | |
| China | workingage_peak | 2005–2015 | **2010** | yes | |

The rule is windowed argmax + ≥3-year real decline.

**Korea and Thailand removed from `post_bubble`** (user, 2026-09-10): `property_peak`
landed on a window edge for both because the 1997 Asian crisis was a currency/credit
event, not a house-price peak. KOR stays in the working-age set (anchors 2016).
THA dropped from `FETCH_COUNTRIES` entirely. Post-bubble set is now JPN, FIN, SWE,
USA, GBR, ESP, IRL, CHN (8).

## Indicator coverage gaps that bite

- **TWN: nothing** except `gov_debt_gdp` (IMF, 1997–). Drops out of the working-age
  distribution entirely — recorded, not a set change (user kept the full set).
- **Sector value added (`industry_va_gdp`, `services_va_gdp`)**: JPN only from
  **1994**, USA from 1997 (ends 2021). Japan's property anchor (1991) has no sector
  split at t=0 — the mechanism row's production/consumption decomposition for Japan
  relies on `capital_formation_gdp` / `hh_consumption_gdp` instead (both from 1970).
- **`gdp_pc_ppp`**: all countries start **1990**. Germany's working-age anchor
  (1986) and the Nordic property anchors (1989–90) predate it — the `slope` basis
  falls back to the nearest t with a warning.
- **BIS credit (`credit_hh_gdp`, `credit_nfc_gdp`)**: CHN from 2006, IRL from 2002,
  THA from 1991. All post-anchor windows are covered; pre-anchor context is thin for
  CHN/IRL.
- **`gov_debt_gdp`** runs to 2031 (IMF projections); `MAX_YEAR` = 2025 clips them.

## Resolved

- Korea / Thailand removed from `post_bubble` (see above). If a credit-peak anchor
  rule is built later, the Asian-crisis episodes can be revisited on that basis.
