# Bundled fallback snapshot

`seed.csv` is the last-resort data source used when the local `data/` cache is
absent and the provider APIs cannot be reached.

Provider-backed series (World Bank / IMF / BIS) are a snapshot of the
2026-09-08 `refresh-data` workflow artifact filtered to completed calendar
years (currently through 2025). They are not live data and may be stale; run
`toy-money fetch` or `toy-money pull-cache` for the current cache.

`grad_labor` remains hand-seeded because it is not fetched from a live API.
