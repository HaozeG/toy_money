# toy_money

This repo serves as gathering information from the market, on macro- and micro-economics, that provides me an analysis past and present economics and test my strategy against past data. Similar to quantitative trading tool, this tool would focus more on people's actions, that if certain emotion or trend is reasonable under serious analysis rather than emotions.

Consider such use case: 
- The graduate student thinks this year is problematic for him/her. He/her thinks the past years' experience is no longer helpful, as the situation has changed.
- However, such thoughts are highly influenced by social medias and secondary information, and he/she may take the past experience as the guidance and following that gives the highest probability to a good outcome.

Consider such useful data:
- Macroeconomy: Where does the money goes, the economic situation of different countries, the domestic, foreign and state-owned capital in certain country, the market growth represented by if human capital needs are expanded, and the comparison against new graduates provided to the market
- Topic and keywords discussed in certain forums, like weibo, zhihu, xiaohongshu (find relevant existing tools on this)

Data should be reliable. These information could be structured into local knowledge base, that we shall find a mature and popular implementation online. Not only can they used as factural data against the hypothesis I provide, but also guidance on how should I understand the market. 

One possible test case is on comparing the economics of current China with Japan in 1990s, seeing if the claims that China would step onto the similar path Japan has undergo years ago.

The final results should be an interface with visualizations, preferably HTML pages.

---

## Status — Phase 1

Reframed as **hypothesis-testing against historical analogues** (not backtesting: there
is no trading strategy). Phase 1 builds one vertical slice — **China now vs. Japan
1990s** — from free official APIs (World Bank, IMF, BIS; FRED optional) and renders a
static HTML report.

```bash
uv sync --extra dev
uv run toy-money fetch          # populate data/ cache (falls back to bundled seed data offline)
uv run toy-money build          # -> artifacts/china_japan.html
uv run toy-money build --anchor workingage_peak   # try a different alignment
```

If the data providers (World Bank / IMF / BIS) are blocked on your network, let the
`refresh-data` GitHub Action fetch them for you and pull the result:

```bash
gh workflow run refresh-data.yml    # fetch on GitHub's runners
uv run toy-money pull-cache         # download the parquet cache locally
```

The comparison hinges on the **anchor year** (when do the two timelines line up?), which
is a parameter with named presets — `bubble_peak` (JPN 1990 ↔ CHN 2021) and
`workingage_peak` (JPN 1992 ↔ CHN 2010). Different anchors give different verdicts; that
is the point. See `CLAUDE.md` for architecture and data caveats.

Deferred to later phases: social-media topic scraping, the RAG knowledge base.

