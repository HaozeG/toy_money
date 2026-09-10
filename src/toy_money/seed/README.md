# Bundled fallback snapshot

`seed.csv` is the last-resort data source used when the local `data/` cache is
absent and the provider APIs cannot be reached.

Provider-backed series (World Bank / IMF / BIS) are a snapshot of the
2026-09-08 `refresh-data` workflow artifact filtered to completed calendar
years (currently through 2025). They are not live data and may be stale; run
`toy-money fetch` or `toy-money pull-cache` for the current cache.

`grad_labor` remains hand-seeded because it is not fetched from a live API.

Seed rows are **China and Japan only** — the bilateral report's pair. The Phase B
comparator episodes (FIN, SWE, KOR, THA, USA, GBR, ESP, IRL, TWN, DEU, ITA) are
not carried in the seed; their offline fallback is `toy-money pull-cache`. The
`capital_formation_gdp` / `hh_consumption_gdp` / `industry_va_gdp` /
`services_va_gdp` rows were added from the 2026-09-10 workflow artifact.
