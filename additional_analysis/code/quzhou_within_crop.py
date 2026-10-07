"""Quzhou matched nitrogen correlations pooled across crops and within wheat and within maize
(Results 3.4). Writes results/quzhou_within_crop.csv.
Run from anywhere: python3 additional_analysis/code/quzhou_within_crop.py
"""
import sys
from pathlib import Path
import numpy as np, pandas as pd
from scipy import stats
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "code" / "analysis"), str(ROOT / "code" / "runners")]
import analyze_quzhou_full as Q

_, gt = Q.load_profiles_quzhou(Q.DATA)
rows = []
for prov in ("claude", "codex", "kimi"):
    for t in (1, 2, 3, 4):
        by_farmer, _ = Q.load_agent_results(prov, t)
        for fid, entries in by_farmer.items():
            if fid not in gt:
                continue
            by_crop = {}
            for e in entries:
                if e["crop"] and isinstance(e.get("n_kg_per_mu"), (int, float)):
                    by_crop.setdefault(e["crop"], []).append(e["n_kg_per_mu"] * 15)
            for g in gt[fid]:
                c = Q.normalize_crop(g.get("crop_choice", ""))
                ob = g.get("nitrogen_rate_kg_per_ha")
                if c in by_crop and isinstance(ob, (int, float)) and np.isfinite(ob):
                    rows.append(dict(prov=prov, tier=t, fid=fid, crop=c, a=np.mean(by_crop[c]), o=ob))
df = pd.DataFrame(rows)
print("crop counts in matched pairs (claude T2):", df[(df.prov == "claude") & (df.tier == 2)].crop.value_counts().head(6).to_dict())

# crop-identity reference: leave-one-out observed crop mean
obs = pd.DataFrame([dict(fid=f, crop=Q.normalize_crop(g.get("crop_choice", "")), o=g.get("nitrogen_rate_kg_per_ha"))
                    for f, gs in gt.items() for g in gs])
obs = obs[pd.to_numeric(obs.o, errors="coerce").notna()].astype({"o": float})
s, n = obs.groupby("crop").o.transform("sum"), obs.groupby("crop").o.transform("count")
loo = ((s - obs.o) / (n - 1)).where(n > 1, obs.o.mean())
print(f"LOO crop-mean reference over {len(obs)} observed records: r={stats.pearsonr(loo, obs.o)[0]:.3f}")

out = []
for (p, t), g in df.groupby(["prov", "tier"]):
    rec = dict(prov=p, tier=t, n=len(g), r_pooled=stats.pearsonr(g.a, g.o)[0])
    for c in ("wheat", "maize"):
        h = g[g.crop == c]
        rec[f"r_{c}"] = stats.pearsonr(h.a, h.o)[0] if len(h) > 10 and h.a.std() > 0 else np.nan
        rec[f"n_{c}"] = len(h)
    out.append(rec)
res = pd.DataFrame(out)
res.to_csv(ROOT / "additional_analysis" / "results" / "quzhou_within_crop.csv", index=False)
print(res.round(3).to_string())
