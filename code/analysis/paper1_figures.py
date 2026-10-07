"""Paper 1 figures, generated from result data. Writes figures/*.{pdf,png}.

Fig 1  individual fidelity and distribution-only reference benchmark
Fig 2  tail-truncation quantile ladder (the mechanism)
Fig 3  dispersion + tail ratios, 36 configurations -- FOUR design variants (A-D)
Fig 4  context-response curves across distinct evaluation targets
ED Fig 2  country-level correlation and dispersion
"""
import json, glob, sys
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib as mpl
mpl.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parents[2]
FIG = ROOT / "figures"; FIG.mkdir(parents=True, exist_ok=True)
SOURCE = FIG / "source_data"; SOURCE.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(Path(__file__).resolve().parent))

PROV = ["claude", "codex", "kimi"]
TIERS = [1, 2, 3, 4]
# Restrained, colourblind-safe Nature-style palette. Provider colours are fixed across figures.
C = {"claude": "#5185C0", "codex": "#C96144", "kimi": "#55966B",
     "obs": "#222222", "null": "#8A8A8A", "parity": "#9B3A32",
     "reference": "#9B3A32", "ceiling": "#777777"}
TMARK = {1: "o", 2: "s", 3: "^", 4: "D"}
OC = {"Nitrogen": "#5185C0", "Family labour": "#E99D4E",
      "Hired labour": "#55966B", "Nitrogen, Quzhou": "#8281B9"}

mpl.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
    "font.size": 7.5,
    "axes.linewidth": 0.8,
    "axes.edgecolor": "#333333",
    "axes.labelsize": 8,
    "axes.titlesize": 8.5,
    "axes.titleweight": "bold",
    "xtick.labelsize": 7,
    "ytick.labelsize": 7,
    "legend.fontsize": 7,
    "legend.frameon": False,
    "axes.spines.right": False,
    "axes.spines.top": False,
    "xtick.major.width": 0.7,
    "ytick.major.width": 0.7,
    "figure.dpi": 150,
    "savefig.dpi": 600,
    "savefig.bbox": "tight",
    "pdf.fonttype": 42,
    "svg.fonttype": "none",
})

CONT = [("nitrogen_kg_per_ha", "nitrogen_kg_per_ha", "Nitrogen (kg ha$^{-1}$)"),
        ("family_labor_days", "total_family_labor_days", "Family labour (days)"),
        ("hired_labor_days", "total_hired_labor_days", "Hired labour (days)")]


def save(fig, name):
    fig.savefig(FIG / f"{name}.pdf")
    fig.savefig(FIG / f"{name}.svg")
    fig.savefig(FIG / f"{name}.png", dpi=600)
    fig.savefig(FIG / f"{name}.tiff", dpi=600, pil_kwargs={"compression": "tiff_lzw"})
    plt.close(fig); print("wrote", name)


def save_source(frame, name):
    """Write the exact plotted values for source-data review."""
    owners = {
        "fig1_validation_gap": "Results: A distribution-only reference outperforms every agent on marginal similarity",
        "fig1_compression": "Results: Simulated populations are compressed toward typical behaviour",
        "fig2_dispersion_tail": "Results: Simulated populations are compressed toward typical behaviour",
        "fig3_prompt_effects": "Results: Prompt effects depend on model, outcome and evaluation target",
        "fig4_country": "Results: Reproducing individual decisions differs across country samples",
    }
    if "owning_section" not in frame.columns:
        frame = frame.copy()
        frame["owning_section"] = owners[name]
    if frame["owning_section"].isna().any() or (frame["owning_section"] == "").any():
        raise ValueError(f"{name}: every source-data row must name an owning manuscript section")
    frame.to_csv(SOURCE / f"{name}.csv", index=False)


def lsms_agent(akey, prov, t):
    df = pd.read_csv(ROOT / "data/lsms_4country_full.csv")
    out = []
    for f in glob.glob(str(ROOT / f"raw_agent_output/lsms/{prov}/tier{t}/*.json")):
        try: v = float((json.load(open(f)).get("decision") or {}).get(akey))
        except (TypeError, ValueError): continue
        if np.isfinite(v): out.append(v)
    return np.array(out)


def quzhou_real_n():
    gt = json.load(open(ROOT / "raw_agent_output/quzhou/_ground_truth.json"))
    out = []
    for entries in gt.values():
        for e in entries:
            try: v = float(e.get("nitrogen_rate_kg_per_ha"))
            except (TypeError, ValueError): continue
            if np.isfinite(v): out.append(v)
    return np.asarray(out)


def quzhou_agent_n(prov, tier):
    out = []
    for f in glob.glob(str(ROOT / f"raw_agent_output/quzhou/{prov}/tier{tier}/*.json")):
        d = json.load(open(f))
        dec = d.get("decision") or {}
        plan = dec.get("annual_plan") or dec.get("plan") or []
        for e in plan:
            v = e.get("nitrogen_kg_per_mu", e.get("nitrogen_total_kg_per_mu"))
            try: v = float(v) * 15.0
            except (TypeError, ValueError): continue
            if np.isfinite(v): out.append(v)
    return np.asarray(out)


def fig1_validation_gap():
    """Lead result: population similarity does not establish person-level fidelity."""
    metrics = json.load(open(ROOT / "metrics/3prov_metrics.json"))
    refs = json.load(open(ROOT / "metrics/paper1_metrics.json"))
    datasets = [("quzhou", "Quzhou"), ("lsms", "Africa")]
    provider_offset = {"claude": -0.18, "codex": 0.0, "kimi": 0.18}
    tier_offset = {1: -0.030, 2: -0.010, 3: 0.010, 4: 0.030}

    fig, axes = plt.subplots(
        1, 2, figsize=(7.2, 3.05),
        gridspec_kw={"width_ratios": [0.92, 1.30], "wspace": 0.30}
    )
    source_rows = []

    # Panel a: the paired decision signal remains weak across configurations.
    ax = axes[0]
    for i, (ds, label) in enumerate(datasets):
        vals = []
        for provider in PROV:
            for tier in TIERS:
                value = metrics[ds][provider][str(tier)]["n_r"]
                x = i + provider_offset[provider] + tier_offset[tier]
                ax.scatter(x, value, s=33, marker=TMARK[tier], color=C[provider],
                           edgecolors="white", linewidths=0.5, zorder=3)
                vals.append(value)
                source_rows.append({"dataset": ds, "metric": "pearson_r",
                                    "provider": provider, "tier": tier,
                                    "value": value, "benchmark": "agent"})
        ax.plot([i - 0.27, i + 0.27], [np.median(vals)] * 2,
                color=C["obs"], lw=1.5, zorder=4)
    ax.axhline(0, color="#8A8A8A", lw=0.8, ls=":", zorder=1)
    ax.set_ylim(-0.15, 0.45)
    ax.set_ylabel("Pearson correlation")
    ax.set_title("Weak match to individual decisions", loc="left", pad=5)

    # Panel b: even apparently high raw distributional scores need a reference scale.
    ax = axes[1]
    for i, (ds, label) in enumerate(datasets):
        vals = []
        for provider in PROV:
            for tier in TIERS:
                value = metrics[ds][provider][str(tier)]["n_ks"]
                x = i + provider_offset[provider] + tier_offset[tier]
                ax.scatter(x, value, s=33, marker=TMARK[tier], color=C[provider],
                           edgecolors="white", linewidths=0.5, zorder=3)
                vals.append(value)
                source_rows.append({"dataset": ds, "metric": "ks_similarity",
                                    "provider": provider, "tier": tier,
                                    "value": value, "benchmark": "agent"})

        reference = refs[ds]["reference"]["ALL"]["null_shape"]
        ceiling = refs[ds]["reference"]["ALL"]["ceiling"]
        line_end = i + 0.30
        ax.hlines(reference, i - 0.30, line_end, color=C["reference"],
                  lw=1.35, ls="--", zorder=2)
        ax.hlines(ceiling, i - 0.30, line_end, color=C["ceiling"],
                  lw=1.0, zorder=2)
        # Direct labels occupy the otherwise empty area above the agent points.
        label_x = i + 0.34
        if ceiling - reference < 0.04:
            reference_label_y, ceiling_label_y = reference - 0.030, ceiling + 0.025
        else:
            reference_label_y, ceiling_label_y = reference, ceiling
        ax.plot([line_end, label_x - 0.015], [reference, reference_label_y],
                color=C["reference"], lw=0.65, clip_on=False)
        ax.plot([line_end, label_x - 0.015], [ceiling, ceiling_label_y],
                color=C["ceiling"], lw=0.65, clip_on=False)
        ax.text(label_x, reference_label_y, "distribution-only",
                fontsize=6.1, color=C["reference"], va="center", ha="left")
        ax.text(label_x, ceiling_label_y, "resampling reference",
                fontsize=6.1, color=C["ceiling"], va="center", ha="left")
        source_rows.extend([
            {"dataset": ds, "metric": "ks_similarity", "provider": "distribution_only_reference",
             "tier": np.nan, "value": reference, "benchmark": "distribution_only_reference"},
            {"dataset": ds, "metric": "ks_similarity", "provider": "resampling_reference",
             "tier": np.nan, "value": ceiling, "benchmark": "resampling_reference"},
        ])
    ax.set_xlim(-0.43, 1.72)
    ax.set_ylim(0.50, 1.01)
    ax.set_ylabel("KS similarity")
    ax.set_title("Distribution-only reference exceeds every agent", loc="left", pad=5)

    for panel, ax in enumerate(axes):
        ax.set_xticks([0, 1])
        ax.set_xticklabels([label for _, label in datasets])
        ax.grid(axis="y", color="#ECECEC", lw=0.55, zorder=0)
        ax.text(-0.13, 1.06, "ab"[panel], transform=ax.transAxes,
                fontsize=10, fontweight="bold")

    provider_h = [Line2D([], [], marker="o", ls="", color=C[p],
                         label=p.capitalize(), markersize=5) for p in PROV]
    tier_h = [Line2D([], [], marker=TMARK[t], ls="", color="#555555",
                     markerfacecolor="white", label=f"T{t}", markersize=5) for t in TIERS]
    fig.legend(handles=provider_h + tier_h, loc="upper center",
               bbox_to_anchor=(0.52, 1.005), ncol=7, handletextpad=0.35,
               columnspacing=0.90)

    save_source(pd.DataFrame(source_rows), "fig1_validation_gap")
    fig.subplots_adjust(left=0.09, right=0.98, bottom=0.17, top=0.80)
    save(fig, "fig1_validation_gap")


def _pct_ratio(real, agents, lo=5, hi=99, floor_frac=0.28):
    """Agent/observed value at each percentile. Only where observed exceeds a stability
    floor (a fraction of its own p90), because ratios explode against near-zero denominators."""
    ps = np.arange(lo, hi + 1)
    rv = np.percentile(real, ps)
    ok = rv > max(1e-9, floor_frac * np.percentile(real, 90))
    out = []
    for v in agents.values():
        av = np.percentile(v, ps)
        out.append(np.where(ok, av / np.where(ok, rv, 1), np.nan))
    return ps, np.array(out), ok


def fig1():
    """Hero result: simulated distributions contract toward typical behaviour."""
    df = pd.read_csv(ROOT / "data/lsms_4country_full.csv")
    series = []
    for akey, gkey, lab in CONT:
        real = df[gkey].dropna().values
        ag = {(p, t): lsms_agent(akey, p, t) for p in PROV for t in TIERS}
        series.append((lab.split(" (")[0], real, {k: v for k, v in ag.items() if len(v) > 20}))
    agq = {(p, t): quzhou_agent_n(p, t) for p in PROV for t in TIERS}
    series.append(("Nitrogen, Quzhou", quzhou_real_n(),
                   {k: v for k, v in agq.items() if len(v) > 20}))

    fig, (ax, ax2) = plt.subplots(
        1, 2, figsize=(7.2, 3.05),
        gridspec_kw={"width_ratios": [1.62, 1], "wspace": 0.30}
    )
    source_rows = []
    marks = [10, 25, 50, 75, 90, 99]

    for lab, real, ag in series:
        ps, ratios, ok = _pct_ratio(real, ag)
        med = np.full(len(ps), np.nan)
        low = np.full(len(ps), np.nan)
        high = np.full(len(ps), np.nan)
        med[ok] = np.nanmedian(ratios[:, ok], axis=0)
        low[ok] = np.nanmin(ratios[:, ok], axis=0)
        high[ok] = np.nanmax(ratios[:, ok], axis=0)
        col = OC[lab]
        ax.fill_between(ps[ok], low[ok], high[ok], color=col, alpha=0.12, lw=0, zorder=1)
        ax.plot(ps[ok], med[ok], color=col, lw=1.8, zorder=3, label=lab)

        xs, vals = [], []
        for m in marks:
            k = np.where(ps == m)[0][0]
            source_rows.append({
                "outcome": lab,
                "percentile": m,
                "median_ratio": med[k] if ok[k] else np.nan,
                "minimum_ratio": low[k] if ok[k] else np.nan,
                "maximum_ratio": high[k] if ok[k] else np.nan,
            })
            if ok[k] and np.isfinite(med[k]):
                xs.append(m); vals.append(med[k])
        ax2.plot(xs, vals, color=col, lw=1.25, marker="o", ms=3.8, label=lab)

    for a in (ax, ax2):
        a.axhline(1.0, color=C["parity"], lw=1.0, zorder=2)
        a.grid(axis="y", color="#ECECEC", lw=0.55, zorder=0)
        a.set_ylim(0, 1.85)

    ax.text(7, 1.03, "observed parity", color=C["parity"], fontsize=6.6, va="bottom")
    # Keep narrative annotations in data-sparse regions so they do not obscure curves.
    ax.annotate("lower tail elevated", xy=(18, 1.48), xytext=(38, 1.74),
                arrowprops={"arrowstyle": "-", "color": "#777777", "lw": 0.7},
                fontsize=6.7, color="#555555", ha="center")
    ax.annotate("upper tail truncated", xy=(91, 0.34), xytext=(66, 0.15),
                arrowprops={"arrowstyle": "-", "color": "#777777", "lw": 0.7},
                fontsize=6.7, color="#555555")
    ax.set_xlim(5, 99)
    ax.set_xlabel("Observed population percentile")
    ax.set_ylabel("Simulated / observed value")
    ax.set_title("Full percentile profiles", loc="left", pad=5)
    ax.text(-0.13, 1.06, "a", transform=ax.transAxes, fontsize=10, fontweight="bold")

    ax2.set_xlim(7, 102)
    ax2.set_xticks(marks)
    ax2.set_xticklabels([f"p{m}" for m in marks])
    ax2.set_xlabel("Selected percentile")
    ax2.set_ylabel("Median ratio across 12 configurations")
    ax2.set_title("Configuration-median summary", loc="left", pad=5)
    ax2.text(-0.16, 1.06, "b", transform=ax2.transAxes, fontsize=10, fontweight="bold")
    ax2.legend(loc="upper center", bbox_to_anchor=(-0.05, 1.25), ncol=4,
               handlelength=1.6, columnspacing=1.0)

    save_source(pd.DataFrame(source_rows), "fig1_compression")
    fig.subplots_adjust(left=0.085, right=0.99, bottom=0.17, top=0.80)
    save(fig, "fig1_compression")


def load_ratios():
    d = json.load(open(ROOT / "metrics/paper1_multioutcome.json"))
    rows = []
    for akey, blk in d["continuous"].items():
        for cell, c in blk["cells"].items():
            prov, t = cell.split("_T")
            rows.append({"outcome": blk["label"], "prov": prov, "tier": int(t),
                         "sd": c["sd_ratio"], "p90": c["p90_ratio"]})
    return pd.DataFrame(rows)


def fig2_A(R):
    """Dumbbell: every configuration a row, SD -> p90 connected."""
    fig, axes = plt.subplots(1, 3, figsize=(10.2, 4.3), sharex=True)
    for ax, out in zip(axes, R.outcome.unique()):
        s = R[R.outcome == out].sort_values(["prov", "tier"]).reset_index(drop=True)
        y = np.arange(len(s))
        for i, r in s.iterrows():
            ax.plot([r.sd, r.p90], [i, i], color="#cccccc", lw=1.4, zorder=1)
        ax.scatter(s.sd, y, s=26, color=[C[p] for p in s.prov], marker="o", zorder=3, label="SD ratio")
        ax.scatter(s.p90, y, s=30, facecolors="white", edgecolors=[C[p] for p in s.prov],
                   linewidths=1.2, marker="D", zorder=3, label="p90 ratio")
        ax.axvline(1.0, color="#B22222", lw=1.1, zorder=2)
        ax.set_yticks(y); ax.set_yticklabels([f"{r.prov[:2].capitalize()} T{r.tier}" for _, r in s.iterrows()])
        ax.set_title(out, loc="left"); ax.set_xlabel("Simulated ÷ observed")
        ax.set_xlim(0, 1.15); ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="x", lw=0.4, color="#eeeeee", zorder=0)
    axes[0].legend(loc="lower right")
    fig.suptitle("All 36 configurations fall below parity on both dispersion and tail",
                 x=0.02, ha="left", fontsize=9.5, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    save(fig, "fig2A_dumbbell")


def fig2_B(R):
    """Two aligned panels show all 36 dispersion and tail estimates."""
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.85), sharey=True,
                             gridspec_kw={"wspace": 0.16})
    outs = list(R.outcome.unique())
    ybase = {out: len(outs) - 1 - i for i, out in enumerate(outs)}
    poff = {"claude": 0.15, "codex": 0.0, "kimi": -0.15}
    clean = {
        "N rate (kg/ha)": "Nitrogen",
        "family labour (days)": "Family labour",
        "hired labour (days)": "Hired labour",
    }

    for ax, metric, title, panel in zip(
        axes, ["sd", "p90"],
        ["Population dispersion", "Upper-tail magnitude"], ["a", "b"]
    ):
        for _, row in R.iterrows():
            y = ybase[row.outcome] + poff[row.prov]
            ax.scatter(row[metric], y, s=31, marker=TMARK[int(row.tier)],
                       color=C[row.prov], edgecolors="white", linewidths=0.45,
                       alpha=0.95, zorder=3)
        ax.axvline(1.0, color=C["parity"], lw=1.0, zorder=2)
        ax.text(0.985, len(outs) - 0.48, "observed parity", color=C["parity"],
                fontsize=6.4, ha="right", va="top")
        ax.set_xlim(0, 1.06)
        ax.set_ylim(-0.45, len(outs) - 0.55)
        ax.set_xlabel("Simulated / observed")
        ax.set_title(title, loc="left", pad=5)
        ax.text(-0.12, 1.06, panel, transform=ax.transAxes,
                fontsize=10, fontweight="bold")
        ax.grid(axis="x", lw=0.5, color="#ECECEC", zorder=0)
        ax.spines["left"].set_visible(False)

    axes[0].set_yticks([ybase[o] for o in outs])
    axes[0].set_yticklabels([clean.get(o, o) for o in outs])
    axes[1].tick_params(axis="y", left=False)

    provider_h = [Line2D([], [], marker="o", ls="", color=C[p],
                         label=p.capitalize(), markersize=5) for p in PROV]
    tier_h = [Line2D([], [], marker=TMARK[t], ls="", color="#555555",
                     markerfacecolor="white", label=f"T{t}", markersize=5) for t in TIERS]
    fig.legend(handles=provider_h + tier_h, loc="upper center",
               bbox_to_anchor=(0.54, 1.04), ncol=7, handletextpad=0.35,
               columnspacing=0.9)
    save_source(R.rename(columns={"prov": "provider"}), "fig2_dispersion_tail")
    fig.subplots_adjust(left=0.15, right=0.99, bottom=0.19, top=0.78)
    save(fig, "fig2B_strip")


def fig2_C(R):
    """Heatmap: model x tier rows, outcome columns."""
    cmap = mpl.colors.LinearSegmentedColormap.from_list(
        "recovery", ["#F7F7F7", "#DCE6F2", "#AFC4DE", "#6F98C7", "#315C8A"]
    )
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.0),
                             gridspec_kw={"wspace": 0.42})
    last_im = None
    for panel, (ax, metric, name) in enumerate(zip(
        axes, ["sd", "p90"], ["Population dispersion", "90th percentile"]
    )):
        M = R.pivot_table(index=["prov", "tier"], columns="outcome", values=metric)
        last_im = ax.imshow(M.values, cmap=cmap, vmin=0, vmax=1.0, aspect="auto")
        ax.set_xticks(range(M.shape[1]))
        labels = [c.replace("N rate (kg/ha)", "Nitrogen")
                   .replace("family labour (days)", "Family labour")
                   .replace("hired labour (days)", "Hired labour") for c in M.columns]
        ax.set_xticklabels(labels, rotation=20, ha="right")
        ax.set_yticks(range(M.shape[0]))
        ax.set_yticklabels([f"{a.capitalize()} T{b}" for a, b in M.index])
        for i in range(M.shape[0]):
            for j in range(M.shape[1]):
                v = M.values[i, j]
                ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=6.3,
                        color="white" if v > 0.66 else "#222222")
        ax.set_title(name, loc="left", pad=5)
        ax.text(-0.13, 1.04, "ab"[panel], transform=ax.transAxes,
                fontsize=10, fontweight="bold")
        for spine in ax.spines.values(): spine.set_visible(False)
        ax.tick_params(length=0)
    # A dedicated colour-bar axis prevents it from covering the final heatmap column.
    fig.subplots_adjust(left=0.14, right=0.87, bottom=0.20, top=0.94)
    cax = fig.add_axes([0.91, 0.20, 0.018, 0.68])
    cbar = fig.colorbar(last_im, cax=cax)
    cbar.set_label("Simulated / observed", fontsize=7)
    cbar.set_ticks([0, 0.5, 1.0])
    save(fig, "fig2C_heatmap")


def fig2_D(R):
    """Slope chart: SD -> p90 per configuration, coloured by model."""
    fig, axes = plt.subplots(1, 3, figsize=(8.6, 3.6), sharey=True)
    for ax, out in zip(axes, R.outcome.unique()):
        s = R[R.outcome == out]
        for _, r in s.iterrows():
            ax.plot([0, 1], [r.sd, r.p90], color=C[r.prov], lw=1.1, alpha=0.8, marker=TMARK[r.tier], ms=4)
        ax.axhline(1.0, color="#B22222", lw=1.1)
        ax.set_xticks([0, 1]); ax.set_xticklabels(["SD\nratio", "p90\nratio"])
        ax.set_xlim(-0.25, 1.25); ax.set_ylim(0, 1.12)
        ax.set_title(out.split(" (")[0], loc="left")
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_ylabel("Simulated ÷ observed")
    h = [Line2D([], [], color=C[p], lw=1.4, label=p.capitalize()) for p in PROV] + \
        [Line2D([], [], color="#666", marker=TMARK[t], ls="", label=f"T{t}") for t in TIERS]
    axes[2].legend(handles=h, loc="upper right", ncol=2)
    fig.tight_layout()
    save(fig, "fig2D_slope")


def wheat_maize_jaccard():
    """Mean farmer-level crop-set Jaccard from answering {wheat, maize} for every surveyed
    farmer. Uses the survey loader and normalize_crop behind crop_jaccard in 3prov_metrics.json."""
    import comprehensive_eval as ce
    _, gt = ce.load_profiles_quzhou(ce.DATA / "quzhou")
    guess = {"wheat", "maize"}
    sets = [{ce.normalize_crop(e.get("crop_choice", "")) for e in entries if e.get("crop_choice")}
            for entries in gt.values()]
    return float(np.mean([len(guess & s) / len(guess | s) for s in sets]))


def fig3():
    m = json.load(open(ROOT / "metrics/3prov_metrics.json"))
    ratios = load_ratios()
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 4.05),
                             gridspec_kw={"hspace": 0.43, "wspace": 0.28})
    spec = [
        ("quzhou", "crop_jaccard", "Crop-set overlap", "Quzhou | crop choice"),
        ("quzhou", "n_r", "Pearson correlation", "Quzhou | nitrogen decision"),
        ("lsms", "n_r", "Pearson correlation", "Africa | nitrogen decision"),
        ("lsms", "dispersion_median", "Median SD ratio", "Africa | dispersion"),
    ]
    source_rows = []
    for panel, (ax, (ds, key, ylab, title)) in enumerate(zip(axes.ravel(), spec)):
        for p in PROV:
            ts = TIERS
            if key == "dispersion_median":
                vals = [float(ratios[(ratios.prov == p) & (ratios.tier == t)].sd.median())
                        for t in ts]
            else:
                vals = [m[ds][p][str(t)][key] for t in ts]
            ax.plot(ts, vals, "-o", color=C[p], ms=4.3, lw=1.45,
                    label=p.capitalize())
            for t, value in zip(ts, vals):
                source_rows.append({"dataset": ds, "metric": key, "provider": p,
                                    "tier": t, "value": value})
        # T4 is the farmer skill in both settings.
        ax.axvspan(3.72, 4.28, color="#F2CB9F", alpha=0.20, lw=0, zorder=0)
        ax.text(3.98, 0.03, "farmer\nskill", transform=ax.get_xaxis_transform(),
                ha="center", va="bottom", fontsize=5.9, color="#7A684E")
        if key == "crop_jaccard":
            ref = wheat_maize_jaccard()
            ax.axhline(ref, color=C["null"], lw=0.9, ls="--", zorder=1)
            ax.text(3.65, ref + 0.012, "wheat and maize for every farmer",
                    color=C["null"], fontsize=6.2, ha="right", va="bottom")
            source_rows.append({"dataset": ds, "metric": key, "provider": "wheat_and_maize_reference",
                                "tier": pd.NA, "value": ref})
            ax.set_ylim(0.58, 1.02)
        elif ds == "quzhou":
            ax.set_ylim(-0.13, 0.40)
        elif key == "n_r":
            ax.set_ylim(0.14, 0.36)
        else:
            ax.axhline(1.0, color=C["parity"], lw=1.0, zorder=1)
            ax.text(3.93, 0.98, "observed parity", color=C["parity"],
                    fontsize=6.2, ha="right", va="top")
            ax.set_ylim(0.08, 1.03)
        ax.set_xlim(0.85, 4.15)
        ax.set_xticks([1, 2, 3, 4])
        ax.set_xticklabels(["T1", "T2", "T3", "T4"])
        ax.set_ylabel(ylab)
        ax.set_title(title, loc="left", pad=4)
        ax.text(-0.12, 1.05, "abcd"[panel], transform=ax.transAxes,
                fontsize=10, fontweight="bold")
        ax.grid(axis="y", lw=0.5, color="#ECECEC", zorder=0)
    axes[0, 0].legend(loc="upper center", bbox_to_anchor=(1.12, 1.32),
                      ncol=3, columnspacing=1.2)
    save_source(pd.DataFrame(source_rows), "fig3_prompt_effects")
    fig.subplots_adjust(left=0.09, right=0.97, bottom=0.12, top=0.88)
    save(fig, "fig3_context_response")


def fig4():
    d = json.load(open(ROOT / "metrics/paper1_metrics.json"))["lsms"]["by_country"]
    order = ["Nigeria", "Ethiopia", "Malawi", "Tanzania"]
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.7),
                             gridspec_kw={"wspace": 0.28})
    source_rows = []
    for panel, (ax, key, ylab, title) in enumerate(zip(
        axes, ["pearson_r", "sd_ratio"],
        ["Pearson correlation", "Simulated / observed SD"],
        ["Individual-decision match", "Dispersion recovery"]
    )):
        for i, c in enumerate(order):
            for cell, v in d[c].items():
                prov, t = cell.split("_T")
                ax.scatter(i + {"claude": -0.17, "codex": 0.0, "kimi": 0.17}[prov], v[key],
                           s=30, marker=TMARK[int(t)], color=C[prov], alpha=0.9,
                           edgecolors="white", linewidths=0.5, zorder=3)
                source_rows.append({"country": c, "metric": key, "provider": prov,
                                    "tier": int(t), "value": v[key]})
            vals = [v[key] for v in d[c].values()]
            ax.plot([i - 0.28, i + 0.28], [np.median(vals)] * 2,
                    color="#222222", lw=1.45, zorder=4)
        if key == "pearson_r":
            ax.axhline(0, color="#8A8A8A", lw=0.8, ls=":")
            ax.set_ylim(-0.20, 0.50)
        else:
            ax.axhline(1.0, color=C["parity"], lw=1.0)
            ax.text(2.95, 0.98, "observed parity", color=C["parity"],
                    fontsize=6.3, ha="right", va="top")
            ax.set_ylim(0, 1.05)
        ax.set_xticks(range(4))
        ax.set_xticklabels(order)
        ax.set_ylabel(ylab)
        ax.set_title(title, loc="left", pad=5)
        ax.text(-0.12, 1.06, "ab"[panel], transform=ax.transAxes,
                fontsize=10, fontweight="bold")
        ax.grid(axis="y", lw=0.5, color="#ECECEC", zorder=0)
    h = [Line2D([], [], marker="o", ls="", color=C[p], label=p.capitalize()) for p in PROV] + \
        [Line2D([], [], marker=TMARK[t], ls="", color="#555555",
                markerfacecolor="white", label=f"T{t}") for t in TIERS] + \
        [Line2D([], [], color="#222222", lw=1.45, label="median")]
    fig.legend(handles=h, loc="upper center", bbox_to_anchor=(0.53, 1.01),
               ncol=8, columnspacing=0.75, handletextpad=0.3)
    save_source(pd.DataFrame(source_rows), "fig4_country")
    fig.subplots_adjust(left=0.09, right=0.99, bottom=0.19, top=0.79)
    save(fig, "fig4_country")


if __name__ == "__main__":
    R = load_ratios()
    fig1_validation_gap(); fig1(); fig2_A(R); fig2_B(R); fig2_C(R); fig2_D(R); fig3(); fig4()
    print("\nAll figures ->", FIG)
