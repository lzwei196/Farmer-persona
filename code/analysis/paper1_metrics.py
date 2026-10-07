"""Paper 1 consolidated metrics: individual vs population fidelity, with NULL BASELINES.

Produces metrics/paper1_metrics.{json,md}.

The key addition over comprehensive_eval.py is a set of reference models that let a
KS-similarity number be interpreted on a scale:

  CEILING   resample n draws from the real distribution itself  -> best achievable at this n
  NULL-mean every farmer gets the real population mean
  NULL-med  every farmer gets the real population median
  NULL-shape correct zero-fraction + lognormal fit to the positive part, assigned at
            RANDOM to farmers (knows the population, nothing about any individual)

An agent that beats NULL-shape carries individual-level information into the
distribution. An agent below NULL-shape does not.
"""
import json, glob, sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_quzhou_full as Q  # noqa: E402

RNG = np.random.default_rng(20260808)
NBOOT = 400
PROVIDERS = ["claude", "codex", "kimi"]
TIERS = [1, 2, 3, 4]


def ksim(a, b):
    a = np.asarray(a, float); b = np.asarray(b, float)
    if len(a) < 2 or len(b) < 2: return float("nan")
    return float(1.0 - stats.ks_2samp(a, b).statistic)


def reference_models(real, n_draw):
    """Interpretive scale for KS-similarity against `real`."""
    real = np.asarray([v for v in real if np.isfinite(v)], float)
    out = {"n_real": int(len(real)), "real_mean": float(real.mean()),
           "real_sd": float(real.std()), "real_median": float(np.median(real)),
           "real_zero_frac": float((real == 0).mean())}
    v = [ksim(RNG.choice(real, n_draw, replace=True), real) for _ in range(NBOOT)]
    out["ceiling"] = float(np.mean(v))
    out["ceiling_lo"], out["ceiling_hi"] = float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))
    out["null_mean"] = ksim(np.full(n_draw, real.mean()), real)
    out["null_median"] = ksim(np.full(n_draw, np.median(real)), real)
    pos = real[real > 0]; z = float((real == 0).mean())
    if len(pos) > 5:
        lp = np.log(pos)
        v = [ksim(np.where(RNG.random(n_draw) < z, 0.0,
                           np.exp(RNG.normal(lp.mean(), lp.std(), n_draw))), real) for _ in range(NBOOT)]
        out["null_shape"] = float(np.mean(v))
    else:
        out["null_shape"] = float("nan")
    return out


def paired_stats(agent, real):
    """agent/real are aligned per-farmer arrays."""
    a, r = np.asarray(agent, float), np.asarray(real, float)
    m = np.isfinite(a) & np.isfinite(r)
    a, r = a[m], r[m]
    if len(a) < 3: return {}
    out = {"n": int(len(a)), "mae": float(np.mean(np.abs(a - r)))}
    out["pearson_r"] = float(stats.pearsonr(a, r)[0]) if a.std() > 0 and r.std() > 0 else float("nan")
    out["spearman_r"] = float(stats.spearmanr(a, r)[0]) if a.std() > 0 and r.std() > 0 else float("nan")
    out["agent_mean"], out["agent_sd"] = float(a.mean()), float(a.std())
    out["sd_ratio"] = float(a.std() / r.std()) if r.std() > 0 else float("nan")
    out["mean_ratio"] = float(a.mean() / r.mean()) if r.mean() != 0 else float("nan")
    out["ks_sim"] = ksim(a, r)
    out["agent_zero_frac"] = float((a == 0).mean())
    return out


# ─────────────────────────── LSMS ───────────────────────────
def lsms_block():
    df = pd.read_csv(ROOT / "data" / "lsms_4country_full.csv")
    real_by_idx = df["nitrogen_kg_per_ha"].to_dict()
    country_by_idx = df["country"].to_dict()
    res = {"reference": {}, "cells": {}, "by_country": {}}
    real_all = df["nitrogen_kg_per_ha"].dropna().values
    res["reference"]["ALL"] = reference_models(real_all, len(df))
    for c, g in df.groupby("country"):
        res["reference"][c] = reference_models(g["nitrogen_kg_per_ha"].dropna().values, len(g))

    for prov in PROVIDERS:
        for t in TIERS:
            pairs = []
            for f in glob.glob(str(ROOT / f"raw_agent_output/lsms/{prov}/tier{t}/*.json")):
                d = json.load(open(f))
                idx = d.get("farmer_idx")
                dec = d.get("decision") or {}
                if idx is None or idx not in real_by_idx: continue
                try: v = float(dec.get("nitrogen_kg_per_ha"))
                except (TypeError, ValueError): continue
                if not np.isfinite(v): continue
                pairs.append((idx, v, real_by_idx[idx], country_by_idx[idx]))
            if len(pairs) < 10: continue
            a = [p[1] for p in pairs]; r = [p[2] for p in pairs]
            res["cells"][f"{prov}_T{t}"] = paired_stats(a, r)
            for c in sorted(set(p[3] for p in pairs)):
                sub = [p for p in pairs if p[3] == c]
                res["by_country"].setdefault(c, {})[f"{prov}_T{t}"] = \
                    paired_stats([p[1] for p in sub], [p[2] for p in sub])
    return res


# ─────────────────────────── Quzhou ───────────────────────────
def quzhou_block():
    profs, gt = Q.load_profiles_quzhou(Q.DATA)
    real_n, _, _ = Q.extract_real_dists(gt)
    real_n = np.array([v for v in real_n if np.isfinite(v)], float)
    res = {"reference": {"ALL": reference_models(real_n, len(real_n))}, "cells": {}}
    for prov in PROVIDERS:
        for t in TIERS:
            by_farmer, _ = Q.load_agent_results(prov, t)
            if not by_farmer: continue
            ent = [e for v in by_farmer.values() for e in v]
            nv = np.array(Q.agent_n_kg_ha(ent), float)
            if len(nv) < 10: continue
            # Quzhou is plot-level and unpaired -> distributional metrics only
            res["cells"][f"{prov}_T{t}"] = {
                "n": int(len(nv)), "agent_mean": float(nv.mean()), "agent_sd": float(nv.std()),
                "sd_ratio": float(nv.std() / real_n.std()),
                "mean_ratio": float(nv.mean() / real_n.mean()),
                "ks_sim": ksim(nv, real_n),
            }
    return res


def md_table(cells, ref, cols, hdr):
    L = ["| cell | " + " | ".join(hdr) + " |", "|" + "---|" * (len(hdr) + 1)]
    for k in sorted(cells):
        row = []
        for c in cols:
            v = cells[k].get(c)
            row.append("--" if v is None or (isinstance(v, float) and not np.isfinite(v)) else f"{v:.3f}" if abs(v) < 100 else f"{v:.1f}")
        L.append(f"| {k} | " + " | ".join(row) + " |")
    L.append("")
    L.append(f"*Reference for this outcome:* CEILING **{ref['ceiling']:.3f}** "
             f"(95% {ref['ceiling_lo']:.3f}–{ref['ceiling_hi']:.3f}) · "
             f"NULL-shape **{ref['null_shape']:.3f}** · NULL-median {ref['null_median']:.3f} · "
             f"NULL-mean {ref['null_mean']:.3f} · real sd {ref['real_sd']:.1f}, "
             f"real mean {ref['real_mean']:.1f}, zero-frac {ref['real_zero_frac']:.2f}")
    return "\n".join(L)


def main():
    out = {"lsms": lsms_block(), "quzhou": quzhou_block()}
    ad = ROOT / "metrics"
    ad.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(ad / "paper1_metrics.json", "w"), indent=1)

    M = ["# Paper 1 metrics — individual vs population fidelity, with null baselines",
         "", "Generated by `code/analysis/paper1_metrics.py`. Outcome = nitrogen kg/ha.",
         "KS-sim = 1 − KS statistic (1.0 = identical distributions).", "",
         "## LSMS-ISA 4-country (Africa) — paired per-farmer", "",
         md_table(out["lsms"]["cells"], out["lsms"]["reference"]["ALL"],
                  ["n", "pearson_r", "spearman_r", "mae", "ks_sim", "sd_ratio", "mean_ratio", "agent_zero_frac"],
                  ["n", "r", "rho", "MAE", "KS-sim", "SD ratio", "mean ratio", "agent zero%"]),
         "", "## Quzhou (China) — unpaired plot-level distribution", "",
         md_table(out["quzhou"]["cells"], out["quzhou"]["reference"]["ALL"],
                  ["n", "ks_sim", "sd_ratio", "mean_ratio", "agent_mean", "agent_sd"],
                  ["n", "KS-sim", "SD ratio", "mean ratio", "agent mean", "agent SD"]), ""]
    M += ["## LSMS by country", ""]
    for c in sorted(out["lsms"]["by_country"]):
        M += [f"### {c}", "",
              md_table(out["lsms"]["by_country"][c], out["lsms"]["reference"][c],
                       ["n", "pearson_r", "mae", "ks_sim", "sd_ratio"],
                       ["n", "r", "MAE", "KS-sim", "SD ratio"]), ""]
    open(ad / "paper1_metrics.md", "w").write("\n".join(M))
    print("\n".join(M))


if __name__ == "__main__":
    main()
