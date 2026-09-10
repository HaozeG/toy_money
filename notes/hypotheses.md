# Sub-hypotheses (Phase B1) — checkpoint, no code

"China is retracing Japan's path" is four separate claims with different anchors,
indicators, and time horizons. Each is tested as **China's position in the
distribution of comparable episodes** at matched time-since-anchor — Japan is one
point in that set, not the benchmark. The rows below give Japan's actual path as
the reference trajectory and the episode set as the real test surface.

Numbers are from the live cache (`refresh-data` run 34331709154). Japan Δ = change
from its own anchor; China so far has 4 post-anchor years under the 2021 property
anchor, ~15 under the 2010 working-age anchor.

---

## Anchor rules (functions of data, applied identically to every episode)

- **`property_peak`** — argmax of the real residential property price index,
  restricted to the modern series and requiring ≥3 subsequent years of decline.
  → JPN **1991**, CHN **2021**. The current `bubble_peak` preset uses JPN **1990**,
  so **the Japan figures in #2–#4 below (computed on 1991) will not match the
  shipped `findings.bubble_peak.json` / report until B3 replaces the typed year.**
- **`workingage_peak`** — argmax of the working-age (15–64) population share.
  → JPN **1992**, CHN **2010**.
- **`explicit`** — keep manual anchors for ad-hoc use.

Deflation and labour-scarring both anchor on `property_peak`: they are consequences
of the balance-sheet shock, measured later on the same clock. (A naive "first
sub-1% CPI year" rule picks transient disinflation — JPN 1986 — and is rejected.)

---

## 1. Demographic growth slowdown

| | |
|---|---|
| **Anchor** | `workingage_peak` (JPN 1992, CHN 2010) |
| **Indicators / basis** | working-age share (Δpp from anchor); real GDP/capita (log-change); real GDP growth (level) |
| **Japan Δ path** (t = 5 / 10 / 15 / 20) | working-age share −0.8 / −2.7 / −5.2 / −7.7; GDP/cap log +0.06 / +0.06 / +0.14 / +0.13; growth 1.4 / 0.1 / 1.7 / 1.6 |
| **China so far** (t = 15) | working-age share −3.2; GDP/cap log +0.87; growth 5.0 |
| **Falsify "Japan-like"** | China's real GDP/capita Δ path stays above the top of the working-age-peak episode distribution while its working-age-share Δ tracks the middle → the demographic drag is not binding on growth the way it was for Japan. Already at t=15 China's GDP/cap log-change (+0.87) is far outside Japan's (+0.14); open question is whether that persists to t=20. |
| **Comparators** | working-age-peak economies: JPN, KOR, TWN, DEU, ITA, CHN. Years shown elsewhere in this doc (KOR ~2016 etc.) are recalled placeholders for orientation only — B2 runs the `workingage_peak` rule over each country's data and records what it selects. |

## 2. Post-property-bubble balance-sheet recession

| | |
|---|---|
| **Anchor** | `property_peak` (JPN 1991, CHN 2021) |
| **Indicators / basis** | real property prices (index, 100 = anchor); household credit / GDP (Δpp); non-financial corporate credit / GDP (Δpp); government debt / GDP (Δpp) |
| **Japan Δ path** (t = 5 / 10 / 15 / 20) | property 84 / 72 / 56 / 54; household credit +1 / 0 / −6 / −6; **corporate credit −1 / −25 / −38 / −37**; gov debt +31 / +73 / +98 / +137 |
| **China so far** (t = 4) | property **80** (−20%); household credit −1; **corporate credit +16** (still rising); gov debt +27 |
| **Falsify "Japan-like"** | China's corporate-credit/GDP Δ path stays in the upper half of the post-bubble episode distribution through t≈7–8 (no private-sector deleveraging), i.e. China does not move toward the Japan/Nordic tail. Already observed at t=4: property (−20% vs Japan −16% at t=5) and public debt (+27 vs +31) sit near Japan; corporate credit (+16pp vs Japan −1pp at t=5) is at the opposite end — firms still levering while prices fall. |
| **Comparators** | post-bubble set (countries): JPN, FIN, SWE, KOR, THA, USA, GBR, ESP, IRL. Anchor years are **not** set here — B2's first step runs `property_peak` over each country and records the year it selects. |

## 3. Deflation entrenchment

| | |
|---|---|
| **Anchor** | `property_peak` (JPN 1991, CHN 2021) |
| **Indicators / basis** | CPI inflation (level); GDP deflator if available (level) |
| **Japan Δ path** (t = 5 / 10 / 15 / 20) | CPI 0.1 / −0.7 / 0.2 / −0.3 — sub-1% from t≈4 and stays there |
| **China so far** (t = 0 → 4) | CPI 1.0 → 2.0 → 0.2 → 0.2 → 0.1 — already sub-1% by t≈2, faster than Japan |
| **Falsify "Japan-like"** | CPI recovers durably above ~1.5% within t≈6 without a policy regime break → the disinflation was cyclical, not entrenched. So far China is *more* deflationary than Japan at the same t, not less. |
| **Comparators** | same post-bubble set as #2; deflation was the exception (mainly JPN), so the test is whether China is an outlier toward the Japan tail. |

## 4. New-entrant labour-market scarring

*(the row that answers the README's graduate-student question)*

| | |
|---|---|
| **Anchor** | `property_peak` (JPN 1991, CHN 2021) |
| **Indicators / basis** | youth unemployment 15–24 (Δpp from anchor); **within-country** graduate-cohort measures (Phase C: JPN 求人倍率 & 学校基本調査 placement rate; CHN MoE graduate count, CIER index) — compared as Δ from anchor only, never cross-country levels |
| **Japan Δ path** (t = 5 / 10 / 15 / 20) | youth unemployment +2.3 / +5.1 / +3.8 / +3.9 — rises for a decade (就職氷河期 1993–2005), partially recovers |
| **China so far** (t = 4) | youth unemployment +3.4 (ILO-modelled; NBS 16–24 series has the 2023 break) — tracking the Japan rise, slightly steeper |
| **Falsify "Japan-like"** | China's youth-unemployment Δ path peaks and reverts within t≈5 (staying in the lower half of the post-bubble episode distribution — no multi-year scarring cohort), or the graduate jobs-to-applicants ratio does not fall for a sustained stretch |
| **Comparators** | post-bubble set (countries as in #2); add a jobs-to-applicants / graduate-placement series where a national one exists (KOR, USA at minimum). |

---

## What B2–B4 turn this into

- **B2** — `EPISODES` table in `config.py`: `(iso3, anchor_rule, label)` for the sets
  above. **First step: run each anchor rule over every comparator country and record
  the year it selects** — no anchor year is carried in from this doc. WB/IMF cover
  all; BIS credit/property coverage varies by country and start year — recorded
  per-episode in the cache manifest, marked "unavailable" per indicator rather than
  dropped silently.
- **B3** — the two anchor rules as functions in `align.py`, applied to every episode.
- **B4** — `episodes` analyzer: per indicator and post-anchor t, China's Δ, the
  episode distribution (min / Q1 / median / Q3 / max), Japan's Δ, China's rank. The
  report draws China against the episode band, Japan separately.

## Open for the reviewer

- Comparator set — trim the 9 post-bubble + 5 working-age candidates, or keep all.
- Horizon N per hypothesis: currently sketched to t=20; #4 (scarring) may only need
  t≈8–10.
- Whether `property_peak` should require the ≥3-year-decline confirmation (excludes
  episodes still unfolding — e.g. would China itself qualify with only 4 down years?
  It does: 2022–2025 all declined).
