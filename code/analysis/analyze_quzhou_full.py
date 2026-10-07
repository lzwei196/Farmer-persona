"""
Quzhou full-scale analysis — Claude & Codex × T1-T4.

Computes per-provider × per-tier metrics:
  - Validity / parse rate
  - Crop diversity, top crops
  - Distributional consistency vs real farmer distributions (N rate, irrigation)
  - Per-farmer accuracy: does the agent's plan match this specific farmer's crops?
  - N-rate MAE and correlation (on matched crops)
  - Seed type normalized distribution
  - Differentiation: do agents respond to age, gender, farm_size?

NOTE: yield_kg_per_mu in ground truth stores raw Yield column values (jin/mu).
      To compare to agent's expected_yield_kg_per_mu we'd divide GT by 2.
      Yield analysis is skipped here until the field is corrected upstream.
"""
import json, glob, sys
from collections import Counter
from pathlib import Path
import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))
from profiles import load_profiles_quzhou

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
RESULTS = PACKAGE_ROOT / "raw_agent_output" / "quzhou"
DATA = PACKAGE_ROOT / "data" / "quzhou"


def normalize_crop(s: str) -> str:
    s = (s or "").strip().lower()
    s = s.replace("summer ", "").replace("winter ", "").replace("spring ", "")
    mapping = {
        "corn": "maize", "mazie": "maize", "peanuts": "peanut", "soy": "soybean",
        "soya": "soybean", "mung bean": "mungbean",
    }
    return mapping.get(s, s)


def normalize_seed(s: str) -> str:
    s = (s or "").strip().lower()
    if "hybrid" in s: return "hybrid"
    if "improved" in s: return "improved"
    if "traditional" in s or "saved" in s or s in ("local", "common"): return "traditional"
    return "other"


def load_agent_results(provider, tier):
    files = sorted(glob.glob(str(RESULTS / provider / f"tier{tier}" / "*.json")))
    by_farmer = {}
    for f in files:
        d = json.load(open(f))
        fid = d.get("farmer_id")
        dec = d.get("decision")
        if not dec or not fid:
            continue
        plan = dec.get("annual_plan") or dec.get("plan") or []
        entries = []
        for e in plan:
            entries.append({
                "crop": normalize_crop(e.get("crop", "")),
                "n_kg_per_mu": e.get("nitrogen_kg_per_mu"),
                "irrigation": e.get("irrigation_times"),
                "seed": normalize_seed(e.get("seed_type", "")),
                "pest": e.get("pesticide_applications"),
                "area_mu": e.get("area_mu") or e.get("field_area_mu"),
            })
        by_farmer[fid] = entries
    return by_farmer, len(files)


def extract_real_dists(gt):
    """Build lists of real-farmer values for distributional tests."""
    n_rates_kg_ha = []
    irrigations = []
    crops_per_farmer = {}
    for fid, entries in gt.items():
        crops_per_farmer[fid] = set()
        for e in entries:
            n = e.get("nitrogen_rate_kg_per_ha")
            if n is not None and not (isinstance(n, float) and np.isnan(n)):
                n_rates_kg_ha.append(n)
            irr = e.get("irrigation_times")
            if irr is not None and not (isinstance(irr, float) and np.isnan(irr)):
                irrigations.append(irr)
            c = normalize_crop(e.get("crop_choice", ""))
            if c:
                crops_per_farmer[fid].add(c)
    return n_rates_kg_ha, irrigations, crops_per_farmer


def agent_n_kg_ha(entries):
    """Convert agent's kg/mu to kg/ha (1 ha = 15 mu)."""
    out = []
    for e in entries:
        n = e.get("n_kg_per_mu")
        if isinstance(n, (int, float)):
            out.append(n * 15)
    return out


def agent_irrigations(entries):
    return [e["irrigation"] for e in entries
            if isinstance(e["irrigation"], (int, float))]


def crop_overlap(agent_crops: set, real_crops: set) -> float:
    """Jaccard overlap; 1.0 if identical sets, 0.0 if disjoint."""
    if not agent_crops and not real_crops:
        return 1.0
    union = agent_crops | real_crops
    if not union:
        return 1.0
    return len(agent_crops & real_crops) / len(union)


def plausibility(values, ref_values):
    """Fraction of values within Q1-1.5*IQR ... Q3+1.5*IQR of reference."""
    ref = np.asarray(ref_values)
    q1, q3 = np.percentile(ref, [25, 75])
    iqr = q3 - q1
    lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    vals = [v for v in values if isinstance(v, (int, float))]
    if not vals:
        return None
    return sum(1 for v in vals if lo <= v <= hi) / len(vals)


def ks_similarity(values, ref_values):
    """1 - KS statistic between two distributions. 1 = identical."""
    a = np.asarray([v for v in values if isinstance(v, (int, float))])
    if len(a) < 2: return None
    ks, _ = stats.ks_2samp(a, np.asarray(ref_values))
    return round(1 - ks, 3)


def main():
    profs, gt = load_profiles_quzhou(DATA)
    prof_by_id = {p.source_id: p for p in profs}
    real_n_kg_ha, real_irrig, real_crops = extract_real_dists(gt)

    print("=" * 92)
    print("  QUZHOU FULL-SCALE ANALYSIS — Claude & Codex, T1 → T4")
    print(f"  n_farmers={len(profs)}, real n_rates={len(real_n_kg_ha)}, real irr={len(real_irrig)}")
    print("=" * 92)

    # ─── Table 1: Coverage & central tendency ──────────────────────────
    print("\n## Table 1: Coverage & Central Tendency (N rate in kg/ha, irrigation in # events)\n")
    print(f"{'Prov':<7} {'Tier':<5} {'Valid':>7} {'#Crops':>7} {'N_mean':>7} {'N_med':>6} "
          f"{'Irr_m':>6} {'Pest_m':>7} {'Hybrid%':>8} {'Improved%':>10} {'Trad%':>6}")
    print("-" * 92)

    for p in ["claude", "codex"]:
        for t in [1, 2, 3, 4]:
            by_farmer, n_files = load_agent_results(p, t)
            all_entries = [e for entries in by_farmer.values() for e in entries]
            n_vals = agent_n_kg_ha(all_entries)
            ir_vals = agent_irrigations(all_entries)
            pest = [e["pest"] for e in all_entries if isinstance(e["pest"], (int, float))]
            unique_crops = len({e["crop"] for e in all_entries if e["crop"]})
            seeds = Counter(e["seed"] for e in all_entries)
            tot = sum(seeds.values()) or 1
            hyb = 100 * seeds["hybrid"] / tot
            imp = 100 * seeds["improved"] / tot
            trad = 100 * seeds["traditional"] / tot
            print(f"{p:<7} T{t:<4} {len(by_farmer):>4}/{n_files}   {unique_crops:>5}  "
                  f"{np.mean(n_vals):>5.0f}  {np.median(n_vals):>5.0f}  "
                  f"{np.mean(ir_vals):>5.2f}  {np.mean(pest) if pest else 0:>5.2f}   "
                  f"{hyb:>5.1f}%    {imp:>5.1f}%   {trad:>4.1f}%")
    print(f"{'REAL':<7} {'--':<5} {len(real_crops):>7} {'--':>7}  "
          f"{np.mean(real_n_kg_ha):>5.0f}  {np.median(real_n_kg_ha):>5.0f}  "
          f"{np.mean(real_irrig):>5.2f}  {'-':>6} {'-':>8} {'-':>10} {'-':>6}")

    # ─── Table 2: Distributional fidelity (KS similarity) ──────────────
    print("\n## Table 2: Distributional Fidelity vs Real Farmers (1.0 = identical)\n")
    print(f"{'Prov':<7} {'Tier':<5} {'N_KS':>6} {'N_plaus%':>9} {'Irr_KS':>7} {'Irr_plaus%':>11}")
    print("-" * 50)

    for p in ["claude", "codex"]:
        for t in [1, 2, 3, 4]:
            by_farmer, _ = load_agent_results(p, t)
            all_entries = [e for entries in by_farmer.values() for e in entries]
            n_vals = agent_n_kg_ha(all_entries)
            ir_vals = agent_irrigations(all_entries)
            n_ks = ks_similarity(n_vals, real_n_kg_ha) or 0
            n_pl = plausibility(n_vals, real_n_kg_ha) or 0
            i_ks = ks_similarity(ir_vals, real_irrig) or 0
            i_pl = plausibility(ir_vals, real_irrig) or 0
            print(f"{p:<7} T{t:<4} {n_ks:>6.3f}  {100*n_pl:>7.1f}%  {i_ks:>6.3f}  {100*i_pl:>9.1f}%")

    # ─── Table 3: Per-farmer crop-choice accuracy ──────────────────────
    print("\n## Table 3: Per-Farmer Crop-Choice Match (Jaccard overlap)\n")
    print(f"{'Prov':<7} {'Tier':<5} {'N_compared':>11} {'Mean':>6} {'Exact%':>7}")
    print("-" * 45)

    for p in ["claude", "codex"]:
        for t in [1, 2, 3, 4]:
            by_farmer, _ = load_agent_results(p, t)
            jaccards = []
            exact = 0
            for fid, entries in by_farmer.items():
                if fid not in real_crops: continue
                ac = {e["crop"] for e in entries if e["crop"]}
                rc = real_crops[fid]
                j = crop_overlap(ac, rc)
                jaccards.append(j)
                if j == 1.0: exact += 1
            if not jaccards: continue
            print(f"{p:<7} T{t:<4} {len(jaccards):>11}  {np.mean(jaccards):>5.3f}   {100*exact/len(jaccards):>5.1f}%")

    # ─── Table 4: Per-farmer N-rate accuracy (MAE on overlapping crops) ─
    print("\n## Table 4: Per-Farmer N-Rate MAE (kg/ha, matched on crop)\n")
    print(f"{'Prov':<7} {'Tier':<5} {'N_pairs':>9} {'MAE':>7} {'MdAE':>7} {'r':>6}")
    print("-" * 45)

    for p in ["claude", "codex"]:
        for t in [1, 2, 3, 4]:
            by_farmer, _ = load_agent_results(p, t)
            pairs = []
            for fid, entries in by_farmer.items():
                if fid not in gt: continue
                # Build per-crop agent avg
                ag_by_crop = {}
                for e in entries:
                    c = e["crop"]
                    n = e.get("n_kg_per_mu")
                    if c and isinstance(n, (int, float)):
                        ag_by_crop.setdefault(c, []).append(n * 15)
                # Match against real entries
                for re in gt[fid]:
                    rc = normalize_crop(re.get("crop_choice", ""))
                    rn = re.get("nitrogen_rate_kg_per_ha")
                    if rc in ag_by_crop and isinstance(rn, (int, float)) and not np.isnan(rn):
                        ag_avg = np.mean(ag_by_crop[rc])
                        pairs.append((ag_avg, rn))
            if len(pairs) < 3: continue
            a = np.array([x[0] for x in pairs])
            r = np.array([x[1] for x in pairs])
            mae = np.mean(np.abs(a - r))
            mdae = np.median(np.abs(a - r))
            corr, _ = stats.pearsonr(a, r)
            print(f"{p:<7} T{t:<4} {len(pairs):>9}   {mae:>5.0f}  {mdae:>5.0f}  {corr:>5.3f}")

    # ─── Table 5: Differentiation by farmer attribute (Kruskal on N_kg_ha) ─
    print("\n## Table 5: Differentiation on N-rate by Farmer Attribute (Kruskal-Wallis p-value)\n")
    print("  Does agent produce different N rates across farmer groups?\n")

    def bucket_farm_size(ha):
        if ha is None: return None
        if ha < 0.2: return "small"
        if ha < 1.0: return "medium"
        return "large"
    def bucket_age(a):
        if a is None: return None
        try: a = float(a)
        except (TypeError, ValueError): return None
        if a < 45: return "young"
        if a < 60: return "middle"
        return "senior"

    print(f"{'Prov':<7} {'Tier':<5} {'by_gender':>11} {'by_age':>9} {'by_size':>9}")
    print("-" * 50)
    for p in ["claude", "codex"]:
        for t in [1, 2, 3, 4]:
            by_farmer, _ = load_agent_results(p, t)
            # Build farmer-level avg N kg/ha
            by_attr = {"gender": {}, "age": {}, "size": {}}
            for fid, entries in by_farmer.items():
                prof = prof_by_id.get(fid)
                if not prof: continue
                n_vals = agent_n_kg_ha(entries)
                if not n_vals: continue
                avg_n = np.mean(n_vals)
                if prof.gender:
                    by_attr["gender"].setdefault(prof.gender, []).append(avg_n)
                ab = bucket_age(prof.age)
                if ab: by_attr["age"].setdefault(ab, []).append(avg_n)
                sb = bucket_farm_size(prof.farm_size_ha)
                if sb: by_attr["size"].setdefault(sb, []).append(avg_n)
            def kruskal_p(groups):
                arrs = [np.array(v) for v in groups.values() if len(v) >= 2]
                if len(arrs) < 2: return None
                _, pv = stats.kruskal(*arrs)
                return pv
            pg = kruskal_p(by_attr["gender"])
            pa = kruskal_p(by_attr["age"])
            ps = kruskal_p(by_attr["size"])
            def fmt(p):
                if p is None: return "   --"
                star = "*" if p < 0.05 else " "
                return f"{p:.4f}{star}"
            print(f"{p:<7} T{t:<4} {fmt(pg):>11} {fmt(pa):>9} {fmt(ps):>9}")

    print("\n   (* = p<0.05 → agent's N-rate differs across farmer groups on that attribute)")
    print("=" * 92)


if __name__ == "__main__":
    main()
