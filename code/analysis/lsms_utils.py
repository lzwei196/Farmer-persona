"""Shared LSMS-ISA preprocessing helpers.

If you find yourself re-implementing yn_to_int or region cleaning, STOP
and import from here instead. This module holds the filters and conventions
for the LSMS-ISA extract (see data/README.md).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import paths as P


# ---------- scalar/column helpers ----------

YN_COLS = [
    "inorganic_fertilizer",
    "female_manager",
    "formal_education_manager",
    "primary_education_manager",
    "irrigated",
    "married_manager",
    "plot_owned",
    "female_respondent",
    "formal_education_respondent",
    "primary_education_respondent",
    "married_respondent",
]


def yn_to_int(series: pd.Series) -> pd.Series:
    """Map a 'Yes'/'No' categorical column to nullable Int64 (1/0/<NA>)."""
    return series.map({"Yes": 1, "No": 0}).astype("Int64")


def clean_region(df: pd.DataFrame, country: str) -> pd.Series:
    """Return a normalized region string series.

    - Strips whitespace
    - Strips Nigeria-style leading number prefixes like "2. North East"
    - For Malawi falls back to admin_2_name (district) because admin_1_name
      is empty in the harmonized panel.
    """
    s = df["admin_1_name"].astype(str).str.strip()
    s = s.str.replace(r"^\d+\.\s*", "", regex=True)
    if country == "Malawi" and "admin_2_name" in df.columns:
        mask = s.isin(["", "nan", "None"])
        s = s.where(~mask, df["admin_2_name"].astype(str).str.strip())
    return s


# ---------- main load pipeline ----------

def load_plot_dataset(country: str | None = None, wave: int | None = None) -> pd.DataFrame:
    """Load Plot_dataset.dta (optionally filtered to country/wave).

    Does NOT apply any filters or transformations. Use `load_country` for that.
    """
    P.ensure_data_exists()
    df = pd.read_stata(str(P.LSMS_PLOT_DTA))
    if country is not None:
        df = df[df["country"] == country]
    if wave is not None:
        df = df[df["wave"] == wave]
    return df.copy()


def load_country(plot_df: pd.DataFrame, country: str, wave: int) -> pd.DataFrame:
    """Apply canonical LSMS preprocessing for one country/wave.

    Steps (in order):
      1. Filter to country + wave
      2. Convert Yes/No categoricals to nullable Int64 (YN_COLS)
      3. Normalize region_clean
      4. Apply plot area filter [PLOT_AREA_MIN_HA, PLOT_AREA_MAX_HA]
      5. Compute nitrogen_kg_per_ha, cap at N_HA_CAP (> cap → NaN)
      6. Compute yield_kg_per_ha, cap at YIELD_HA_CAP (> cap → NaN)
      7. Ethiopia: redefine fert_user as (inorg=1 AND nitrogen_kg>0)
         Other countries: fert_user = (inorganic_fertilizer == 1)
      8. Compute family_labor_d_per_ha (for display, NOT cross-country pooling)

    Returns a copy with new columns: region_clean, nitrogen_kg_per_ha,
    yield_kg_per_ha, fert_user, family_labor_d_per_ha.
    """
    c = plot_df[(plot_df["country"] == country) & (plot_df["wave"] == wave)].copy()

    for col in YN_COLS:
        if col in c.columns:
            c[col] = yn_to_int(c[col])

    c["region_clean"] = clean_region(c, country)

    c = c[(c["plot_area_GPS"] >= P.PLOT_AREA_MIN_HA)
          & (c["plot_area_GPS"] <= P.PLOT_AREA_MAX_HA)].copy()

    c["nitrogen_kg_per_ha"] = c["nitrogen_kg"] / c["plot_area_GPS"]
    c.loc[c["nitrogen_kg_per_ha"] > P.N_HA_CAP, "nitrogen_kg_per_ha"] = np.nan

    c["yield_kg_per_ha"] = c["harvest_kg"] / c["plot_area_GPS"]
    c.loc[c["yield_kg_per_ha"] > P.YIELD_HA_CAP, "yield_kg_per_ha"] = np.nan

    if country == "Ethiopia":
        c["fert_user"] = ((c["inorganic_fertilizer"] == 1)
                          & (c["nitrogen_kg"] > 0)).astype(int)
    else:
        c["fert_user"] = (c["inorganic_fertilizer"] == 1).astype("Int64").fillna(0).astype(int)

    c["family_labor_d_per_ha"] = c["total_family_labor_days"] / c["plot_area_GPS"]

    return c


# ---------- prompt rendering ----------

def row_to_identity_fields(row: pd.Series) -> dict:
    """Build the dict of format fields needed by the Tier 1+ prompt templates."""
    def _safe(v, default="unknown"):
        return default if pd.isna(v) else v

    return {
        "country": _safe(row.get("country")),
        "region": _safe(row.get("region_clean"), "unknown"),
        "age": int(row["age_manager"]) if pd.notna(row.get("age_manager")) else "unknown",
        "gender": "female" if row.get("female_manager") == 1 else "male",
        "education": ("some formal schooling"
                      if row.get("formal_education_manager") == 1
                      else "no formal schooling"),
        "plot_area_ha": f"{row['plot_area_GPS']:.2f}" if pd.notna(row.get("plot_area_GPS")) else "unknown",
        "farm_size_ha": f"{row['farm_size']:.2f}" if pd.notna(row.get("farm_size")) else "unknown",
        "main_crop": _safe(row.get("main_crop")),
        "plot_owned": "yes" if row.get("plot_owned") == 1 else "no/rented",
        "intercropped": "yes" if row.get("intercropped") == 1 else "no",
    }


def render_prompt(template_path, row: pd.Series) -> str:
    """Load a template file and render with fields from one sample row."""
    with open(template_path, "r") as f:
        tmpl = f.read()
    return tmpl.format(**row_to_identity_fields(row))
