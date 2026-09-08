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

# Observations after this year are treated as projections and dropped at build
# time (IMF WEO, some BIS series publish forward estimates).
MAX_YEAR = _dt.date.today().year

# --- paths -------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
ARTIFACTS_DIR = REPO_ROOT / "artifacts"
SEED_DIR = Path(__file__).resolve().parent / "seed"

# --- countries -------------------------------------------------------------

COUNTRIES = {"CHN": "China", "JPN": "Japan"}


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


SERIES: list[Series] = [
    Series(
        key="gdp_growth",
        label="Real GDP growth",
        unit="% per year",
        source="worldbank",
        params={"indicator": "NY.GDP.MKTP.KD.ZG"},
    ),
    Series(
        key="workingage_share",
        label="Working-age population (15–64)",
        unit="% of total",
        source="worldbank",
        params={"indicator": "SP.POP.1564.TO.ZS"},
    ),
    Series(
        key="gdp_pc_ppp",
        label="GDP per capita, PPP (constant 2021 $)",
        unit="constant intl. $",
        source="worldbank",
        params={"indicator": "NY.GDP.PCAP.PP.KD"},
    ),
    Series(
        key="cpi_inflation",
        label="CPI inflation",
        unit="% per year",
        source="worldbank",
        params={"indicator": "FP.CPI.TOTL.ZG"},
    ),
    Series(
        key="gov_debt_gdp",
        label="General government gross debt",
        unit="% of GDP",
        source="imf",
        # IMF DataMapper indicator; keyless JSON API.
        params={"indicator": "GGXWDG_NGDP"},
    ),
    Series(
        key="credit_hh_gdp",
        label="Household credit",
        unit="% of GDP",
        source="bis",
        # BIS WS_TC (credit to non-financial sector). Borrower sector H = households.
        params={"borrowers": "H"},
    ),
    Series(
        key="credit_nfc_gdp",
        label="Non-financial corporate credit",
        unit="% of GDP",
        source="bis",
        params={"borrowers": "N"},
    ),
    Series(
        key="real_property_prices",
        label="Real residential property prices",
        unit="index",
        source="bis",
        # BIS WS_SPP selected residential property prices, real.
        params={"dataset": "WS_SPP", "unit_measure": "628"},
        seed_note=(
            "seed values are indexed to 100 at each country's bubble-peak year "
            "(JPN 1990, CHN 2021), so a non-default --anchor misaligns the two "
            "index bases. Live BIS data uses the provider's own base and avoids this."
        ),
    ),
    Series(
        key="youth_unemployment",
        label="Youth unemployment (15–24, ILO modelled)",
        unit="%",
        source="worldbank",
        params={"indicator": "SL.UEM.1524.ZS"},
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
