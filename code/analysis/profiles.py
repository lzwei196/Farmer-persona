"""
Extract farmer profiles from each dataset.
Each loader returns (list[FarmerProfile], ground_truth_dict).
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys

# The archived profile loader lives in analysis; its FarmerProfile dataclass
# remains in the original runner module.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "runners"))
from agent import FarmerProfile


# ── Quzhou County, China NCP ────────────────────────────────

# Education code mapping
EDUCATION_MAP = {
    "illiteracy": "no formal education",
    "primary school": "primary school",
    "junior high school": "middle school",
    "junior middle school": "middle school",
    "senior high school": "high school",
    "senior middle school": "high school",
    "bachelor": "university degree",
    "college": "university degree",
}

# Gender code: 1=male, 2=female in the dataset
GENDER_MAP = {1: "male", 2: "female", "1": "male", "2": "female"}

# Main occupation codes (from codebook)
OCCUPATION_MAP = {
    1: "farming",
    2: "local non-farm work",
    3: "migrant work",
    4: "self-employed business",
    5: "other",
}

MU_TO_HA = 1.0 / 15.0  # 1 mu = 1/15 hectare


def _compute_n_kg_per_ha(row):
    """
    Compute total N applied (kg/ha) from crop record.
    Sources: pure N fertilizer + basal compound + topdressing compound.
    Amounts are in jin/mu in the dataset (1 jin = 0.5 kg, 1 mu = 1/15 ha).
    """
    total_n_jin_per_mu = 0.0

    # Pure nitrogen fertilizer
    n_pct = pd.to_numeric(row.get("N%", 0), errors="coerce") or 0
    n_amt = pd.to_numeric(row.get("Nitrogen_amount", 0), errors="coerce") or 0
    total_n_jin_per_mu += n_amt * (n_pct / 100.0)

    # Basal compound
    cn_pct = pd.to_numeric(row.get("N%.1", 0), errors="coerce") or 0
    c_amt = pd.to_numeric(row.get("Compound_amount", 0), errors="coerce") or 0
    total_n_jin_per_mu += c_amt * (cn_pct / 100.0)

    # Topdressing compound
    tn_pct = pd.to_numeric(row.get("N%.2", 0), errors="coerce") or 0
    t_amt = pd.to_numeric(row.get("Compound_amount.1", 0), errors="coerce") or 0
    total_n_jin_per_mu += t_amt * (tn_pct / 100.0)

    # Convert jin/mu -> kg/ha: * 0.5 (jin->kg) * 15 (mu->ha)
    total_n_kg_per_ha = total_n_jin_per_mu * 0.5 * 15.0
    return round(total_n_kg_per_ha, 1)


def _compute_p_kg_per_ha(row):
    """Compute P2O5 applied (kg/ha) from crop record."""
    total = 0.0
    p_pct = pd.to_numeric(row.get("P2O5%", 0), errors="coerce") or 0
    p_amt = pd.to_numeric(row.get("Phosphate_amount", 0), errors="coerce") or 0
    total += p_amt * (p_pct / 100.0)

    cp_pct = pd.to_numeric(row.get("P2O5%.1", 0), errors="coerce") or 0
    c_amt = pd.to_numeric(row.get("Compound_amount", 0), errors="coerce") or 0
    total += c_amt * (cp_pct / 100.0)

    tp_pct = pd.to_numeric(row.get("P2O5%.2", 0), errors="coerce") or 0
    t_amt = pd.to_numeric(row.get("Compound_amount.1", 0), errors="coerce") or 0
    total += t_amt * (tp_pct / 100.0)

    return round(total * 0.5 * 15.0, 1)


def _compute_k_kg_per_ha(row):
    """Compute K2O applied (kg/ha) from crop record."""
    total = 0.0
    k_pct = pd.to_numeric(row.get("K2O%", 0), errors="coerce") or 0
    k_amt = pd.to_numeric(row.get("Potash_amount", 0), errors="coerce") or 0
    total += k_amt * (k_pct / 100.0)

    ck_pct = pd.to_numeric(row.get("K2O%.1", 0), errors="coerce") or 0
    c_amt = pd.to_numeric(row.get("Compound_amount", 0), errors="coerce") or 0
    total += c_amt * (ck_pct / 100.0)

    tk_pct = pd.to_numeric(row.get("K2O%.2", 0), errors="coerce") or 0
    t_amt = pd.to_numeric(row.get("Compound_amount.1", 0), errors="coerce") or 0
    total += t_amt * (tk_pct / 100.0)

    return round(total * 0.5 * 15.0, 1)


def load_profiles_quzhou(data_dir: str):
    """
    Load farmer profiles from Quzhou household + crop datasets.
    Links household demographics to field-level management decisions.

    Returns (list[FarmerProfile], dict of ground_truth keyed by household ID).
    """
    hh = pd.read_csv(f"{data_dir}/Farm_household_data.csv", encoding="latin1")
    crop = pd.read_csv(f"{data_dir}/Crop_data.csv", encoding="latin1")

    profiles = []
    ground_truth = {}

    for _, row in hh.iterrows():
        hh_id = str(row["ID"])

        # Decision-maker demographics
        dm_gender_code = row.get("Decision maker's gender", 1)
        dm_gender = GENDER_MAP.get(dm_gender_code, "unknown")

        dm_edu_raw = str(row.get("Decision_maker's_schooling year", "unknown")).strip().lower()
        dm_edu = EDUCATION_MAP.get(dm_edu_raw, dm_edu_raw)

        dm_farming_years = pd.to_numeric(
            row.get("Decision_maker's_farming year", None), errors="coerce"
        )
        dm_farming_years = int(dm_farming_years) if pd.notna(dm_farming_years) else None

        # Use head-of-household age as decision-maker age
        dm_age = row.get("Age", None)
        dm_age = str(int(dm_age)) if pd.notna(dm_age) else "unknown"

        farm_type = str(row.get("Farm_type", "Smallholder"))
        household_size = int(row["Household_size"]) if pd.notna(row.get("Household_size")) else None

        # Farm size in mu -> ha
        farm_size_mu = pd.to_numeric(row.get("Farm_size (mu)", 0), errors="coerce") or 0
        farm_size_ha = round(farm_size_mu * MU_TO_HA, 2)

        # Cropping systems from CS_1..CS_6
        cs_cols = [c for c in hh.columns if c.startswith("CS_")]
        cropping_systems = []
        for c in cs_cols:
            v = str(row.get(c, "0")).strip()
            if v and v != "0" and v != "nan":
                cropping_systems.append(v)

        # Get crops from crop dataset
        hh_crops = crop[crop["ID"] == hh_id]
        crops_grown = sorted(hh_crops["Crop"].dropna().unique().tolist()) if not hh_crops.empty else []
        if not crops_grown:
            crops_grown = ["wheat", "maize"]  # default for Quzhou

        # Determine off-farm work: any household member with non-agro income > 0
        off_farm = False
        for suffix in ["", ".1", ".2", ".3", ".4", ".5"]:
            col = f"Non-agro_income{suffix}"
            if col in row.index:
                val = pd.to_numeric(row.get(col, 0), errors="coerce") or 0
                if val > 0:
                    off_farm = True
                    break

        cropping_system = cropping_systems[0] if cropping_systems else "wheat-maize double cropping"

        profile = FarmerProfile(
            country="China",
            region="North China Plain, Hebei Province, Quzhou County",
            age=dm_age,
            education=dm_edu,
            gender=dm_gender,
            farm_size_ha=farm_size_ha,
            farm_type=farm_type.lower(),
            crops_grown=crops_grown,
            irrigation=True,  # virtually all Quzhou farms irrigated
            climate_context=(
                "Semi-arid continental, ~500mm annual precipitation, "
                "groundwater irrigation, wheat-maize double cropping region"
            ),
            cropping_system=cropping_system,
            farming_experience_years=dm_farming_years,
            off_farm_work=off_farm,
            household_size=household_size,
            source_dataset="quzhou",
            source_id=hh_id,
        )
        profiles.append(profile)

        # Ground truth from crop records
        if not hh_crops.empty:
            gt_records = []
            for _, cr in hh_crops.iterrows():
                gt = {
                    "crop_choice": cr.get("Crop"),
                    "tillage_method": cr.get("Tillage_methods"),
                    "nitrogen_rate_kg_per_ha": _compute_n_kg_per_ha(cr),
                    "phosphorus_rate_kg_per_ha": _compute_p_kg_per_ha(cr),
                    "potassium_rate_kg_per_ha": _compute_k_kg_per_ha(cr),
                    "irrigation_use": str(cr.get("Normal_irrigation", "0")).strip() not in ("0", "nan", ""),
                    "irrigation_times": pd.to_numeric(cr.get("Irrigation_times", 0), errors="coerce") or 0,
                    "pesticide_use": (
                        (pd.to_numeric(cr.get("Insecticide_times", 0), errors="coerce") or 0) > 0
                        or (pd.to_numeric(cr.get("Herbicide_times", 0), errors="coerce") or 0) > 0
                        or (pd.to_numeric(cr.get("Fungicide_times", 0), errors="coerce") or 0) > 0
                    ),
                    "yield_kg_per_mu": pd.to_numeric(cr.get("Yield", 0), errors="coerce") or 0,
                    "yield_kg_per_ha": round(
                        (pd.to_numeric(cr.get("Yield", 0), errors="coerce") or 0) * 15.0, 0
                    ),
                    "sowing_date": cr.get("Sowing_date "),
                    "harvest_date": cr.get("Harvest_date"),
                    "area_mu": pd.to_numeric(cr.get("Area", 0), errors="coerce") or 0,
                    "variety": cr.get("Variety"),
                    "fertilizer_use": True,  # virtually all Quzhou farmers use fertilizer
                }
                gt_records.append(gt)
            ground_truth[hh_id] = gt_records

    return profiles, ground_truth


# ── Canada Census of Agriculture (placeholder) ──────────────

def load_profiles_canada(data_dir: str):
    """
    Load farmer profiles from Canada Census of Agriculture PUMF.

    NOTE: The currently downloaded data appears to be Census of Population,
    not Census of Agriculture. This loader is a placeholder that will need
    updating once the Agriculture PUMF is obtained.

    Expected Agriculture PUMF variables: OPRAGE, OPRSEX, FARMTYPE, TFARMA,
    PROV, FERT, TILL, IRRIG, etc.
    """
    raise NotImplementedError(
        "The Canada data appears to be Census of Population, not Agriculture. "
        "Download the Census of Agriculture PUMF from Statistics Canada and "
        "update this loader with the correct column mappings."
    )


# ── LSMS-ISA (placeholder) ──────────────────────────────────

def load_profiles_lsms(data_dir: str):
    """
    Load farmer profiles from LSMS-ISA harmonized panel.
    Placeholder — update after downloading the data.
    """
    raise NotImplementedError(
        "Download the LSMS-ISA harmonized panel from the World Bank "
        "Microdata Library and update this loader."
    )
