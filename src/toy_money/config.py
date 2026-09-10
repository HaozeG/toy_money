"""Single source of truth: paths, the indicator table, and anchor presets.

Design note: the *anchor year* is deliberately a parameter, never hardcoded into
analysis logic. Different anchors ("when did the bubble peak?", "when did the
working-age share peak?") produce different verdicts on whether China is
retracing Japan's path, so the choice must stay explicit and swappable.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from pathlib import Path

# The tool compares realised history, so stop at the last completed calendar
# year. IMF WEO and some BIS series publish current-year forecasts/partials;
# including them would make "China's latest observation" a projection.
LAST_COMPLETED_YEAR = _dt.date.today().year - 1
MAX_YEAR = LAST_COMPLETED_YEAR

# Shared analytical window, in years since each country's anchor. The figure
# and the overlap test use the same window so we do not claim comparability
# across the entire available history (e.g. China pre-reform vs. Japan 1960s).
ANALYSIS_WINDOW = (-25, 35)

# --- paths -------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
ARTIFACTS_DIR = REPO_ROOT / "artifacts"
SEED_DIR = Path(__file__).resolve().parent / "seed"

# --- countries -------------------------------------------------------------

COUNTRIES = {"CHN": "China", "JPN": "Japan"}

# The bilateral pair above is Phase 1's report and the alignment-completeness set
# (`resolve_alignment` requires an anchor year for every country in `COUNTRIES`).
# Phase B compares China against a *distribution* of episodes, so the fetch layer
# pulls a wider set — `FETCH_COUNTRIES` — while the bilateral report still runs on
# `COUNTRIES` only. A country with no provider coverage (e.g. TWN in World Bank /
# IMF / BIS) simply comes back empty; that is recorded in the cache manifest and
# `toy-money coverage`, not silently dropped.
FETCH_COUNTRIES = {
    "CHN": "China",
    "JPN": "Japan",
    "FIN": "Finland",
    "SWE": "Sweden",
    "KOR": "South Korea",
    "THA": "Thailand",
    "USA": "United States",
    "GBR": "United Kingdom",
    "ESP": "Spain",
    "IRL": "Ireland",
    "TWN": "Taiwan",
    "DEU": "Germany",
    "ITA": "Italy",
}


# --- indicator table ------------------------------------------------------

@dataclass(frozen=True)
class Series:
    key: str  # cache filename / internal id
    label: str  # human label for charts
    unit: str
    source: str  # worldbank | imf | bis | fred | seed
    params: dict = field(default_factory=dict)
    note: str = ""  # caveat shown in the report whatever the data source
    seed_note: str = ""  # extra caveat shown only when this series fell back to seed
    in_report: bool = True  # include this panel in the default comparison grid
    # What kind of cross-country comparison is meaningful for this indicator:
    #   "level"              - ratios/rates, natively comparable (debt/GDP, %, ...)
    #   "indexed_to_anchor"  - index numbers on a provider base; re-scale each
    #                          country to 100 at its own anchor year before use
    #   "slope"              - only the trajectory compares; the level gap is itself
    #                          a finding (e.g. GDP per capita: "old before rich")
    compare_as: str = "level"
    # Half-width, in the indicator's natural unit (after `compare_as`), within
    # which China and Japan count as "crossing" rather than "above"/"below" at a
    # matched t. `None` => report only above/below (sign of the raw difference).
    # A "crossing" call should mean "within revision noise of equal".
    band: float | None = None
    # Rendered with the panel and in the caveats list whatever the data source;
    # for comparisons that are not definition-comparable across episodes.
    definition_note: str = ""


SERIES: list[Series] = [
    Series(
        key="gdp_growth",
        label="Real GDP growth",
        unit="% per year",
        source="worldbank",
        params={"indicator": "NY.GDP.MKTP.KD.ZG"},
        band=0.5,
    ),
    Series(
        key="workingage_share",
        label="Working-age population (15–64)",
        unit="% of total",
        source="worldbank",
        params={"indicator": "SP.POP.1564.TO.ZS"},
        band=0.3,
    ),
    Series(
        key="gdp_pc_ppp",
        label="GDP per capita, PPP",
        unit="cumulative log-change from anchor",
        source="worldbank",
        params={"indicator": "NY.GDP.PCAP.PP.KD"},
        compare_as="slope",
        band=None,  # a log-change has no natural absolute "crossing" width
    ),
    Series(
        key="cpi_inflation",
        label="CPI inflation",
        unit="% per year",
        source="worldbank",
        params={"indicator": "FP.CPI.TOTL.ZG"},
        band=0.5,
    ),
    Series(
        key="gov_debt_gdp",
        label="General government gross debt",
        unit="% of GDP",
        source="imf",
        # IMF DataMapper indicator; keyless JSON API.
        params={"indicator": "GGXWDG_NGDP"},
        band=3.0,
        definition_note=(
            "IMF WEO GGXWDG_NGDP is general-government gross debt on a narrow "
            "definition. Japan 1990 and China now are not definition-comparable — "
            "China's figure excludes large LGFV and other off-balance-sheet "
            "local-government liabilities."
        ),
    ),
    Series(
        key="credit_hh_gdp",
        label="Household credit",
        unit="% of GDP",
        source="bis",
        # BIS WS_TC (credit to non-financial sector). Borrower sector H = households.
        params={"borrowers": "H"},
        band=2.0,
    ),
    Series(
        key="credit_nfc_gdp",
        label="Non-financial corporate credit",
        unit="% of GDP",
        source="bis",
        params={"borrowers": "N"},
        band=3.0,
    ),
    Series(
        key="real_property_prices",
        label="Real residential property prices",
        unit="100 = anchor year",
        source="bis",
        # BIS WS_SPP selected residential property prices, real.
        params={"dataset": "WS_SPP", "unit_measure": "628"},
        compare_as="indexed_to_anchor",
        band=3.0,  # index points on the re-based 100 = anchor scale
        note=(
            "BIS publishes this on a common 2010=100 base, so raw levels are not "
            "cross-country comparable. Re-indexed here to 100 at each country's own "
            "anchor year — the curves show the path relative to each country's own "
            "peak."
        ),
    ),
    # --- mechanism row (hypotheses.md, approved 2026-09-10): production /
    # consumption split. WB keyless, no adapter change. Not in the bilateral grid
    # yet — the mechanism analysis lands with Phase B4.
    Series(
        key="capital_formation_gdp",
        label="Gross capital formation",
        unit="% of GDP",
        source="worldbank",
        params={"indicator": "NE.GDI.TOTL.ZS"},
        band=2.0,
        in_report=False,
    ),
    Series(
        key="hh_consumption_gdp",
        label="Household final consumption",
        unit="% of GDP",
        source="worldbank",
        params={"indicator": "NE.CON.PRVT.ZS"},
        band=2.0,
        in_report=False,
    ),
    Series(
        key="industry_va_gdp",
        label="Industry (incl. construction) value added",
        unit="% of GDP",
        source="worldbank",
        params={"indicator": "NV.IND.TOTL.ZS"},
        band=2.0,
        in_report=False,
    ),
    Series(
        key="services_va_gdp",
        label="Services value added",
        unit="% of GDP",
        source="worldbank",
        params={"indicator": "NV.SRV.TOTL.ZS"},
        band=2.0,
        in_report=False,
    ),
    Series(
        key="youth_unemployment",
        label="Youth unemployment (15–24, ILO modelled)",
        unit="%",
        source="worldbank",
        params={"indicator": "SL.UEM.1524.ZS"},
        band=1.0,
        note=(
            "China's official 16–24 urban jobless rate had a methodology break: "
            "NBS suspended it in mid-2023 and resumed in 2024 excluding students. "
            "The World Bank / ILO-modelled series shown here smooths over that; "
            "treat recent Chinese values as indicative, not exact."
        ),
    ),
    Series(
        key="grad_labor",
        label="New graduates vs. labour demand",
        unit="see tooltip",
        source="seed",
        params={"file": "grad_labor.csv"},
        # Excluded from the default grid: Japan 求人倍率 and China's CIER index are
        # different constructions, so overlaying them on one axis would assert a
        # like-for-like comparison that does not hold. Kept for ad-hoc use.
        in_report=False,
        note=(
            "Japan = effective jobs-to-applicants ratio (求人倍率, MHLW); "
            "China = CIER labour-market tightness index (Zhaopin/Renmin Univ.). "
            "Different constructions — concept-level comparison only, not directly "
            "comparable levels. Japanese/Chinese primary sources; seed-only for now."
        ),
    ),
]

SERIES_BY_KEY = {s.key: s for s in SERIES}


# --- anchor presets ------------------------------------------------------

@dataclass(frozen=True)
class AnchorPreset:
    name: str
    description: str
    anchors: dict  # ISO3 -> year


ANCHOR_PRESETS: dict[str, AnchorPreset] = {
    "bubble_peak": AnchorPreset(
        name="bubble_peak",
        description="asset-bubble peak",
        anchors={"JPN": 1990, "CHN": 2021},
    ),
    "workingage_peak": AnchorPreset(
        name="workingage_peak",
        description="working-age population share peak",
        anchors={"JPN": 1992, "CHN": 2010},
    ),
}

DEFAULT_ANCHOR = "bubble_peak"


# --- comparator episodes (Phase B) -------------------------------------------

@dataclass(frozen=True)
class Episode:
    """One comparator episode. `search_window` names *which* episode (the years it
    unfolded); the anchor year itself is still computed from data by `anchor_rule`
    inside that window — see `align.anchor_year`. Naming the window is not
    hardcoding the anchor: house prices in SWE / USA later exceeded their crisis
    peaks, so a global argmax would select ~2021, not the episode we mean.
    """

    iso3: str
    anchor_rule: str  # "property_peak" | "workingage_peak"
    search_window: tuple[int, int]  # inclusive years the episode unfolded
    label: str
    set_name: str  # "post_bubble" | "workingage_peak"


EPISODES: list[Episode] = [
    # Post-property-bubble set (hypotheses #2, #3, #4). Windows are orientation
    # bounds; `property_peak` picks the real-house-price peak year within each.
    Episode("JPN", "property_peak", (1988, 1994), "Japan 1990s", "post_bubble"),
    Episode("FIN", "property_peak", (1987, 1993), "Finland / Nordic crisis", "post_bubble"),
    Episode("SWE", "property_peak", (1987, 1993), "Sweden / Nordic crisis", "post_bubble"),
    Episode("KOR", "property_peak", (1994, 2001), "Korea / Asian crisis", "post_bubble"),
    Episode("THA", "property_peak", (1994, 2000), "Thailand / Asian crisis", "post_bubble"),
    Episode("USA", "property_peak", (2004, 2009), "US 2008", "post_bubble"),
    Episode("GBR", "property_peak", (2004, 2009), "UK 2008", "post_bubble"),
    Episode("ESP", "property_peak", (2004, 2009), "Spain 2008", "post_bubble"),
    Episode("IRL", "property_peak", (2004, 2009), "Ireland 2008", "post_bubble"),
    Episode("CHN", "property_peak", (2019, 2024), "China now", "post_bubble"),
    # Working-age-share-peak set (hypothesis #1). Windows bound the demographic
    # peak; `workingage_peak` picks the argmax within each.
    Episode("JPN", "workingage_peak", (1988, 1996), "Japan", "workingage_peak"),
    Episode("KOR", "workingage_peak", (2010, 2020), "Korea", "workingage_peak"),
    Episode("TWN", "workingage_peak", (2010, 2018), "Taiwan", "workingage_peak"),
    Episode("DEU", "workingage_peak", (1982, 1992), "Germany", "workingage_peak"),
    Episode("ITA", "workingage_peak", (1988, 1996), "Italy", "workingage_peak"),
    Episode("CHN", "workingage_peak", (2005, 2015), "China", "workingage_peak"),
]

# Per-hypothesis comparison horizon (years post-anchor), set at the B1 checkpoint.
EPISODE_HORIZONS = {
    "demographic": 20,
    "balance_sheet": 20,
    "deflation": 20,
    "scarring": 10,
    "mechanism": 15,
}
