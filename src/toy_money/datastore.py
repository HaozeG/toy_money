"""Local cache: one parquet file per series, columns [country, year, value]."""

from __future__ import annotations

import json

import pandas as pd

from .config import DATA_DIR, SEED_DIR

_COLUMNS = ["country", "year", "value"]


def _path(key: str):
    return DATA_DIR / f"{key}.parquet"


def _meta_path(key: str):
    return DATA_DIR / f"{key}.meta.json"


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce to the canonical schema, drop nulls, sort, dedupe."""
    df = df[_COLUMNS].copy()
    df["country"] = df["country"].astype(str).str.upper()
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["year", "value"])
    df["year"] = df["year"].astype(int)
    df = (
        df.drop_duplicates(subset=["country", "year"], keep="last")
        .sort_values(["country", "year"])
        .reset_index(drop=True)
    )
    return df


def write(key: str, df: pd.DataFrame, provenance: str = "live") -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    normalize(df).to_parquet(_path(key), index=False)
    _meta_path(key).write_text(json.dumps({"provenance": provenance}), encoding="utf-8")


def has(key: str) -> bool:
    return _path(key).exists()


def provenance(key: str) -> str:
    """'live', 'seed', or 'missing' — where the currently-readable data comes from."""
    if _path(key).exists():
        try:
            return json.loads(_meta_path(key).read_text())["provenance"]
        except (FileNotFoundError, ValueError, KeyError):
            return "live"
    return "seed" if seed_frame(key) is not None else "missing"


def read(key: str) -> pd.DataFrame:
    """Read a series from cache; fall back to the bundled seed data if present."""
    if _path(key).exists():
        return normalize(pd.read_parquet(_path(key)))
    seed = seed_frame(key)
    if seed is not None:
        return seed
    raise FileNotFoundError(
        f"No cached data for '{key}'. Run `toy-money fetch` first "
        f"(and check network access to the data providers)."
    )


_SEED_FILE = SEED_DIR / "seed.csv"


def seed_frame(key: str) -> pd.DataFrame | None:
    """Bundled offline fallback values, from seed/seed.csv (key,country,year,value)."""
    if not _SEED_FILE.exists():
        return None
    allrows = pd.read_csv(_SEED_FILE)
    sub = allrows[allrows["key"] == key]
    if sub.empty:
        return None
    return normalize(sub)
