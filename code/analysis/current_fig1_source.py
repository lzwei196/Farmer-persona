"""Reconstruct numeric source values for panels b-e of the September Fig. 1.

The submitted five-panel TIFF is an editorial figure and has no archived
rendering script. This writes its underlying numeric comparisons, not the TIFF.
Quzhou's individual-error panel uses the original unweighted matched-crop
estimator documented in analyze_quzhou_full.py; the later area-weighted
matched analysis is archived separately under additional_analysis/.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

import analyze_quzhou_full as Q


ROOT = Path(__file__).resolve().parents[2]
PROVIDERS = ("claude", "codex", "kimi")
TIERS = (1, 2, 3, 4)


def quzhou_reference_and_pairs():
    _, ground_truth = Q.load_profiles_quzhou(Q.DATA)
    real = np.array([
        entry["nitrogen_rate_kg_per_ha"]
        for entries in ground_truth.values()
        for entry in entries
        if isinstance(entry.get("nitrogen_rate_kg_per_ha"), (int, float))
        and np.isfinite(entry["nitrogen_rate_kg_per_ha"])
    ], dtype=float)
    for provider in PROVIDERS:
        for tier in TIERS:
            by_farmer, _ = Q.load_agent_results(provider, tier)
            pairs = []
            for farmer_id, entries in by_farmer.items():
                if farmer_id not in ground_truth:
                    continue
                by_crop = {}
                for entry in entries:
                    crop = entry["crop"]
                    nitrogen = entry.get("n_kg_per_mu")
                    if crop and isinstance(nitrogen, (int, float)):
                        by_crop.setdefault(crop, []).append(nitrogen * 15)
                for entry in ground_truth[farmer_id]:
                    crop = Q.normalize_crop(entry.get("crop_choice", ""))
                    observed = entry.get("nitrogen_rate_kg_per_ha")
                    if crop in by_crop and isinstance(observed, (int, float)) and np.isfinite(observed):
                        pairs.append((float(np.mean(by_crop[crop])), float(observed)))
            yield provider, tier, real, pairs, by_farmer


def lsms_agent_values(provider, tier):
    values = []
    for path in sorted((ROOT / "raw_agent_output" / "lsms" / provider / f"tier{tier}").glob("*.json")):
        decision = json.loads(path.read_text()).get("decision") or {}
        try:
            value = float(decision.get("nitrogen_kg_per_ha"))
        except (TypeError, ValueError):
            continue
        if np.isfinite(value):
            values.append(value)
    return np.asarray(values, dtype=float)


def main():
    metrics = json.loads((ROOT / "metrics" / "paper1_metrics.json").read_text())
    lsms_real = pd.read_csv(ROOT / "data" / "lsms_4country_full.csv")["nitrogen_kg_per_ha"].dropna().to_numpy(float)
    rows = []

    for provider in PROVIDERS:
        for tier in TIERS:
            cell = metrics["lsms"]["cells"][f"{provider}_T{tier}"]
            values = lsms_agent_values(provider, tier)
            reference = metrics["lsms"]["reference"]["ALL"]
            median_null_mae = np.mean(np.abs(lsms_real - np.median(lsms_real)))
            threshold = np.percentile(lsms_real, 90)
            rows.append({
                "dataset": "Africa", "provider": provider, "tier": tier,
                "mean_ratio_panel_b": cell["mean_ratio"],
                "ks_minus_shape_null_panel_c": cell["ks_sim"] - reference["null_shape"],
                "individual_mae_skill_panel_d": 1 - cell["mae"] / median_null_mae,
                "agent_at_or_above_observed_p90_pct_panel_e": 100 * np.mean(values >= threshold),
                "observed_at_or_above_p90_pct": 100 * np.mean(lsms_real >= threshold),
                "observed_p90_kg_ha": threshold,
                "n_agent_nitrogen_values": len(values),
                "n_individual_pairs": cell["n"],
                "individual_matching": "plot-row matched",
            })

    for provider, tier, real, pairs, by_farmer in quzhou_reference_and_pairs():
        cell = metrics["quzhou"]["cells"][f"{provider}_T{tier}"]
        reference = metrics["quzhou"]["reference"]["ALL"]
        values = np.asarray(Q.agent_n_kg_ha([entry for entries in by_farmer.values() for entry in entries]), dtype=float)
        observed_pairs = np.asarray([pair[1] for pair in pairs], dtype=float)
        predicted_pairs = np.asarray([pair[0] for pair in pairs], dtype=float)
        median_null_mae = np.mean(np.abs(observed_pairs - np.median(real)))
        threshold = np.percentile(real, 90)
        rows.append({
            "dataset": "China", "provider": provider, "tier": tier,
            "mean_ratio_panel_b": cell["mean_ratio"],
            "ks_minus_shape_null_panel_c": cell["ks_sim"] - reference["null_shape"],
            "individual_mae_skill_panel_d": 1 - np.mean(np.abs(predicted_pairs - observed_pairs)) / median_null_mae,
            "agent_at_or_above_observed_p90_pct_panel_e": 100 * np.mean(values >= threshold),
            "observed_at_or_above_p90_pct": 100 * np.mean(real >= threshold),
            "observed_p90_kg_ha": threshold,
            "n_agent_nitrogen_values": len(values),
            "n_individual_pairs": len(pairs),
            "individual_matching": "farmer-crop matched, unweighted survey records",
        })

    out = ROOT / "figures" / "source_data" / "fig1_current_numeric.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out, index=False)
    print(f"Wrote {len(rows)} configuration rows to {out}")


if __name__ == "__main__":
    main()
