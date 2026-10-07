"""Comprehensive 3-provider evaluation across both datasets.

Produces:
  - metrics/3prov_metrics.json  — per provider × tier metrics
  - with --plots, diagnostic PNGs in metrics/ (not part of the package):
    3prov_quzhou_tier_response.png, 3prov_lsms_tier_response.png,
    3prov_peak_tier_heatmap.png

Adds Kimi to all comparisons and computes:
  - Per-decision per-tier per-provider fidelity (KS, r, match)
  - Peak-tier-per-decision summary
  - Cross-provider distance-from-real ranking
"""
import json, glob, sys
from pathlib import Path
from collections import defaultdict, Counter
import numpy as np
from scipy import stats
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "raw_agent_output"
DATA = ROOT / "data"
OUT = ROOT / "metrics"

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.append(str(Path(__file__).resolve().parents[1] / "runners"))  # profiles imports agent.py
from profiles import load_profiles_quzhou


# ── shared helpers ──────────────────────────────────────────

def normalize_crop(s):
    s = (s or "").strip().lower()
    s = s.replace("summer ", "").replace("winter ", "").replace("spring ", "")
    return {"corn": "maize", "mazie": "maize", "peanuts": "peanut"}.get(s, s)


def normalize_seed(s):
    s = (s or "").strip().lower()
    if "hybrid" in s: return "hybrid"
    if "improved" in s: return "improved"
    if "traditional" in s or "saved" in s or s in ("local", "common"): return "traditional"
    return "other"


# ── Quzhou loader ───────────────────────────────────────────

def load_quzhou(provider, tier):
    files = glob.glob(str(RESULTS / "quzhou" / provider / f"tier{tier}" / "*.json"))
    by_farmer = {}
    for f in files:
        try:
            d = json.load(open(f))
        except: continue
        if not d.get("decision"): continue
        plan = (d["decision"].get("annual_plan") or
                d["decision"].get("plan") or [])
        ents = []
        for e in plan:
            ents.append({
                "crop": normalize_crop(e.get("crop", "")),
                "n": e.get("nitrogen_kg_per_mu"),
                "p": e.get("phosphorus_kg_per_mu"),
                "k": e.get("potassium_kg_per_mu"),
                "irr": e.get("irrigation_times"),
                "seed": normalize_seed(e.get("seed_type", "")),
                "area": e.get("area_mu") or e.get("field_area_mu"),
            })
        by_farmer[d.get("farmer_id")] = ents
    return by_farmer


def quzhou_metrics():
    """Return dict[provider][tier][metric] = value."""
    profs, gt = load_profiles_quzhou(DATA / "quzhou")
    real_n = [e["nitrogen_rate_kg_per_ha"] for entries in gt.values() for e in entries
              if isinstance(e.get("nitrogen_rate_kg_per_ha"), (int, float))
              and not np.isnan(e["nitrogen_rate_kg_per_ha"])]
    real_irr = [e["irrigation_times"] for entries in gt.values() for e in entries
                if isinstance(e.get("irrigation_times"), (int, float))
                and not np.isnan(e["irrigation_times"])]

    out = defaultdict(lambda: defaultdict(dict))
    for prov in ["claude", "codex", "kimi"]:
        for t in [1, 2, 3, 4]:
            agent = load_quzhou(prov, t)

            # Crop-choice Jaccard
            jaccs = []
            for fid, entries in agent.items():
                if fid not in gt: continue
                ac = {e["crop"] for e in entries if e["crop"]}
                rc = {normalize_crop(e.get("crop_choice", "")) for e in gt[fid] if e.get("crop_choice")}
                if not (ac | rc): continue
                jaccs.append(len(ac & rc) / len(ac | rc))
            out[prov][t]["crop_jaccard"] = float(np.mean(jaccs)) if jaccs else None

            # N-rate matched pairs (kg/ha)
            pairs = []
            for fid, entries in agent.items():
                if fid not in gt: continue
                a_by_crop = defaultdict(list)
                for e in entries:
                    if e["crop"] and isinstance(e["n"], (int, float)):
                        a_by_crop[e["crop"]].append(e["n"] * 15)
                for re in gt[fid]:
                    rc = normalize_crop(re.get("crop_choice", ""))
                    rn = re.get("nitrogen_rate_kg_per_ha")
                    if rc in a_by_crop and isinstance(rn, (int, float)) and not np.isnan(rn):
                        pairs.append((np.mean(a_by_crop[rc]), rn))
            if len(pairs) >= 5:
                a = np.array([p[0] for p in pairs])
                r = np.array([p[1] for p in pairs])
                out[prov][t]["n_r"] = float(stats.pearsonr(a, r)[0])
                out[prov][t]["n_mae"] = float(np.mean(np.abs(a - r)))
            else:
                out[prov][t]["n_r"] = None
                out[prov][t]["n_mae"] = None

            # N-rate KS distributional fidelity
            avals = [e["n"] * 15 for entries in agent.values() for e in entries
                     if isinstance(e["n"], (int, float))]
            if avals and real_n:
                ks, _ = stats.ks_2samp(np.array(avals), np.array(real_n))
                out[prov][t]["n_ks"] = float(1 - ks)
            else:
                out[prov][t]["n_ks"] = None

            # Irrigation KS
            ivals = [e["irr"] for entries in agent.values() for e in entries
                     if isinstance(e["irr"], (int, float))]
            if ivals and real_irr:
                ks, _ = stats.ks_2samp(np.array(ivals), np.array(real_irr))
                out[prov][t]["irr_ks"] = float(1 - ks)
            else:
                out[prov][t]["irr_ks"] = None

            # Seed-label cleanliness
            seeds = [e["seed"] for entries in agent.values() for e in entries if e["seed"]]
            canon = sum(1 for s in seeds if s in ("hybrid", "improved", "traditional"))
            out[prov][t]["seed_clean"] = canon / len(seeds) if seeds else None

    return dict(out)


# ── LSMS loader ─────────────────────────────────────────────

def load_lsms_gt():
    """Load real LSMS sample as dict[hhid] -> {n_kg_ha, fert_user, irrigated, family_labor, hired_labor}."""
    import pandas as pd
    df = pd.read_csv(DATA / "lsms_4country_full.csv")
    out = {}
    for _, r in df.iterrows():
        hhid = f"{r['country']}_{r.name}"  # matches file naming pattern
        out[hhid] = {
            "n_kg_ha": r.get("nitrogen_kg_per_ha"),
            "fert_user": r.get("inorganic_fertilizer"),
            "irrigated": r.get("irrigated"),
            "family_labor": r.get("total_family_labor_days"),
            "hired_labor": r.get("total_hired_labor_days"),
            "country": r["country"],
        }
    return out


def load_lsms_agent(provider, tier):
    files = glob.glob(str(RESULTS / "lsms" / provider / f"tier{tier}" / "*.json"))
    out = {}
    for f in files:
        try:
            d = json.load(open(f))
        except: continue
        if not d.get("decision"): continue
        dec = d["decision"]
        # The LSMS schema is flat
        out[d["farmer_id"]] = {
            "n_kg_ha": dec.get("nitrogen_kg_per_ha"),
            "fert_user": 1.0 if dec.get("inorganic_fertilizer") else 0.0,
            "irrigated": 1.0 if dec.get("irrigated") else 0.0,
            "family_labor": dec.get("family_labor_days"),
            "hired_labor": dec.get("hired_labor_days"),
        }
    return out


def lsms_metrics():
    gt = load_lsms_gt()
    real_n = [v["n_kg_ha"] for v in gt.values()
              if isinstance(v["n_kg_ha"], (int, float)) and not np.isnan(v["n_kg_ha"])]
    out = defaultdict(lambda: defaultdict(dict))
    for prov in ["claude", "codex", "kimi"]:
        for t in [1, 2, 3, 4]:
            agent = load_lsms_agent(prov, t)
            common = set(agent) & set(gt)

            # N rate matched
            pairs = []
            for k in common:
                a = agent[k]["n_kg_ha"]
                r = gt[k]["n_kg_ha"]
                if isinstance(a, (int, float)) and isinstance(r, (int, float)) and not np.isnan(r):
                    pairs.append((float(a), float(r)))
            if len(pairs) >= 5:
                a = np.array([p[0] for p in pairs]); r = np.array([p[1] for p in pairs])
                out[prov][t]["n_r"] = float(stats.pearsonr(a, r)[0])
                out[prov][t]["n_mae"] = float(np.mean(np.abs(a - r)))
            else:
                out[prov][t]["n_r"] = None
                out[prov][t]["n_mae"] = None

            # Distributional
            avals = [agent[k]["n_kg_ha"] for k in common
                     if isinstance(agent[k]["n_kg_ha"], (int, float))]
            if avals and real_n:
                ks, _ = stats.ks_2samp(np.array(avals), np.array(real_n))
                out[prov][t]["n_ks"] = float(1 - ks)
            else:
                out[prov][t]["n_ks"] = None

            # Fertilizer-use match %
            matches = []
            for k in common:
                a, r = agent[k]["fert_user"], gt[k]["fert_user"]
                if isinstance(a, (int, float)) and isinstance(r, (int, float)) and not np.isnan(r):
                    matches.append(int(a == r))
            out[prov][t]["fert_match"] = float(np.mean(matches)) if matches else None

            # Irrigated match %
            matches = []
            for k in common:
                a, r = agent[k]["irrigated"], gt[k]["irrigated"]
                if isinstance(a, (int, float)) and isinstance(r, (int, float)) and not np.isnan(r):
                    matches.append(int(a == r))
            out[prov][t]["irr_match"] = float(np.mean(matches)) if matches else None
    return dict(out)


# ── PLOT 1: Quzhou tier curves all 3 providers ──────────────

def plot_quzhou(qm):
    fig, axes = plt.subplots(2, 2, figsize=(13, 9))
    tiers = [1, 2, 3, 4]
    x = np.arange(4)
    colors = {"claude": "#d62728", "codex": "#1f77b4", "kimi": "#2ca02c"}
    markers = {"claude": "o", "codex": "s", "kimi": "^"}
    metrics = [
        ("crop_jaccard", "Crop choice (Jaccard)", 0, 1),
        ("n_r", "N-rate Pearson r", -0.15, 0.5),
        ("n_ks", "N-rate KS similarity", 0.4, 0.8),
        ("seed_clean", "Seed label cleanliness", 0.5, 1.05),
    ]
    for ax, (key, title, lo, hi) in zip(axes.flat, metrics):
        for prov in ["claude", "codex", "kimi"]:
            vals = [qm[prov][t].get(key) for t in tiers]
            ax.plot(x, vals, color=colors[prov], marker=markers[prov], markersize=10,
                    linewidth=2.3, label=prov.capitalize(), alpha=0.85)
            # peak star
            if all(v is not None for v in vals):
                pk = int(np.argmax(vals))
                ax.scatter([x[pk]], [vals[pk]], marker="*", s=320,
                           color=colors[prov], edgecolor="black", linewidth=1.2, zorder=5)
        ax.set_xticks(x); ax.set_xticklabels(["T1","T2","T3","T4"], fontsize=10)
        ax.set_ylim(lo, hi); ax.grid(alpha=0.3)
        ax.set_title(title, fontsize=11.5)
        if title.startswith("N-rate Pearson"):
            ax.axhline(0, color="grey", ls=":", alpha=0.4)
        ax.legend(fontsize=9, loc="best", frameon=False)
    fig.suptitle("Quzhou full-scale: 3-provider tier response  (★ = peak tier)",
                 fontsize=13, y=0.995)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    out = OUT / "3prov_quzhou_tier_response.png"
    fig.savefig(out, dpi=160, bbox_inches="tight")
    print(f"saved {out}")


def plot_lsms(lm):
    fig, axes = plt.subplots(2, 2, figsize=(13, 9))
    x = np.arange(4)
    colors = {"claude": "#d62728", "codex": "#1f77b4", "kimi": "#2ca02c"}
    markers = {"claude": "o", "codex": "s", "kimi": "^"}
    metrics = [
        ("n_r", "N-rate Pearson r", 0, 0.45),
        ("n_ks", "N-rate KS similarity", 0.65, 0.95),
        ("fert_match", "Fertilizer-use match %", 0.55, 0.7),
        ("irr_match", "Irrigated match %", 0.92, 1.0),
    ]
    for ax, (key, title, lo, hi) in zip(axes.flat, metrics):
        for prov in ["claude", "codex", "kimi"]:
            vals = [lm[prov][t].get(key) for t in [1,2,3,4]]
            ax.plot(x, vals, color=colors[prov], marker=markers[prov], markersize=10,
                    linewidth=2.3, label=prov.capitalize(), alpha=0.85)
            if all(v is not None for v in vals):
                pk = int(np.argmax(vals))
                ax.scatter([x[pk]], [vals[pk]], marker="*", s=320,
                           color=colors[prov], edgecolor="black", linewidth=1.2, zorder=5)
        ax.set_xticks(x); ax.set_xticklabels(["T1","T2","T3","T4"], fontsize=10)
        ax.set_ylim(lo, hi); ax.grid(alpha=0.3)
        ax.set_title(title, fontsize=11.5)
        ax.legend(fontsize=9, loc="best", frameon=False)
    fig.suptitle("LSMS 4-country: 3-provider tier response  (★ = peak tier)",
                 fontsize=13, y=0.995)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    out = OUT / "3prov_lsms_tier_response.png"
    fig.savefig(out, dpi=160, bbox_inches="tight")
    print(f"saved {out}")


def plot_peak_heatmap(qm, lm):
    """For each (decision, provider, dataset) cell: which tier peaks?"""
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))
    rows_q = ["Crop choice", "N-rate r", "N-rate KS", "Seed clean"]
    keys_q = ["crop_jaccard", "n_r", "n_ks", "seed_clean"]
    rows_l = ["N-rate r", "N-rate KS", "Fert match", "Irr match"]
    keys_l = ["n_r", "n_ks", "fert_match", "irr_match"]
    provs = ["Claude", "Codex", "Kimi"]
    for ax, dataset_name, m, rows, keys in [
        (axes[0], "Quzhou", qm, rows_q, keys_q),
        (axes[1], "LSMS",   lm, rows_l, keys_l),
    ]:
        grid = np.zeros((len(rows), 3))
        labels = []
        for i, k in enumerate(keys):
            row_labels = []
            for j, prov in enumerate(["claude", "codex", "kimi"]):
                vals = [m[prov][t].get(k) for t in [1,2,3,4]]
                if all(v is not None for v in vals):
                    pk = int(np.argmax(vals))
                    grid[i, j] = pk + 1  # tier number
                    row_labels.append(f"T{pk+1}\n({vals[pk]:.2f})")
                else:
                    grid[i, j] = 0
                    row_labels.append("--")
            labels.append(row_labels)
        # Heatmap: color = tier index (T1 light, T4 dark)
        cmap = plt.cm.viridis
        ax.imshow(grid, aspect="auto", cmap=cmap, vmin=1, vmax=4)
        for i in range(len(rows)):
            for j in range(3):
                txt_color = "white" if grid[i, j] >= 3 else "black"
                ax.text(j, i, labels[i][j], ha="center", va="center",
                        color=txt_color, fontsize=10, fontweight="bold")
        ax.set_xticks(range(3)); ax.set_xticklabels(provs, fontsize=11)
        ax.set_yticks(range(len(rows))); ax.set_yticklabels(rows, fontsize=11)
        ax.set_title(dataset_name, fontsize=13)
    fig.suptitle("Peak tier per (decision × provider × dataset)\n"
                 "Cell shows winning tier and metric value at that tier",
                 fontsize=12.5, y=1.02)
    fig.tight_layout()
    out = OUT / "3prov_peak_tier_heatmap.png"
    fig.savefig(out, dpi=160, bbox_inches="tight")
    print(f"saved {out}")


# ── MAIN ────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Computing Quzhou metrics…")
    qm = quzhou_metrics()
    print("Computing LSMS metrics…")
    lm = lsms_metrics()

    # Save raw metrics for downstream use
    metric_path = OUT / "3prov_metrics.json"
    with open(metric_path, "w") as f:
        json.dump({"quzhou": qm, "lsms": lm}, f, indent=2, default=str)
    print(f"saved {metric_path}")

    if "--plots" in sys.argv:
        plot_quzhou(qm)
        plot_lsms(lm)
        plot_peak_heatmap(qm, lm)

    # Print summary tables
    print("\n" + "="*90)
    print("QUZHOU — N-rate r (individual accuracy) by provider × tier")
    print("="*90)
    print(f"{'Provider':<10}  T1     T2     T3     T4   peak")
    for prov in ["claude", "codex", "kimi"]:
        vals = [qm[prov][t].get("n_r") for t in [1,2,3,4]]
        peak = int(np.argmax(vals)) + 1 if all(v is not None for v in vals) else "?"
        s = "  ".join(f"{v:>5.2f}" if v is not None else "  --" for v in vals)
        print(f"{prov.capitalize():<10}  {s}    T{peak}")

    print("\n" + "="*90)
    print("QUZHOU — N-rate KS (population fidelity) by provider × tier")
    print("="*90)
    print(f"{'Provider':<10}  T1     T2     T3     T4   peak")
    for prov in ["claude", "codex", "kimi"]:
        vals = [qm[prov][t].get("n_ks") for t in [1,2,3,4]]
        peak = int(np.argmax(vals)) + 1 if all(v is not None for v in vals) else "?"
        s = "  ".join(f"{v:>5.2f}" if v is not None else "  --" for v in vals)
        print(f"{prov.capitalize():<10}  {s}    T{peak}")

    print("\n" + "="*90)
    print("LSMS — N-rate r (individual accuracy) by provider × tier")
    print("="*90)
    print(f"{'Provider':<10}  T1     T2     T3     T4   peak")
    for prov in ["claude", "codex", "kimi"]:
        vals = [lm[prov][t].get("n_r") for t in [1,2,3,4]]
        peak = int(np.argmax(vals)) + 1 if all(v is not None for v in vals) else "?"
        s = "  ".join(f"{v:>5.2f}" if v is not None else "  --" for v in vals)
        print(f"{prov.capitalize():<10}  {s}    T{peak}")
