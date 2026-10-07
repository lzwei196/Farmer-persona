"""Validation-level figure (manuscript Fig. 2): three validation levels and their
person-blind references.

a  schematic of the three validation levels
b  simulated / observed mean nitrogen               (observed parity)
c  KS similarity minus the distribution-only reference
d  mean-absolute-error skill relative to the median null
e  % of generated values at or above the observed p90 (observed share, about 10%)

Reads figures/source_data/fig1_current_numeric.csv (written by current_fig1_source.py).
Writes figures/fig_validation_levels.{pdf,svg,png,tiff} and
figures/source_data/fig_validation_levels.csv.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib as mpl
mpl.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parents[2]
FIG = ROOT / "figures"
SOURCE = FIG / "source_data"

# Palette, markers and rcParams copied from paper1_figures.py, whose import creates
# output folders and changes global matplotlib state.
PROV = ["claude", "codex", "kimi"]
TIERS = [1, 2, 3, 4]
C = {"claude": "#5185C0", "codex": "#C96144", "kimi": "#55966B",
     "obs": "#222222", "null": "#8A8A8A", "parity": "#9B3A32",
     "reference": "#9B3A32", "ceiling": "#777777"}
TMARK = {1: "o", 2: "s", 3: "^", 4: "D"}
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
    # Italic person index in panel a in the body font; the default cursive slot
    # has no match on macOS and only triggers a findfont warning.
    "mathtext.fontset": "custom",
    "mathtext.rm": "Arial",
    "mathtext.it": "Arial:italic",
    "mathtext.cal": "Arial",
})

NAME = "fig_validation_levels"
OWNER = "Results: Group summaries can match the survey while matched decisions do not"
DATASETS = [("China", "quzhou", "Quzhou"), ("Africa", "lsms", "Africa")]  # csv value, key, label
TIER_X = {1: -0.165, 2: -0.055, 3: 0.055, 4: 0.165}

# Layout in inches from the figure's top-left; the saved files are cropped to content.
W, H = 7.345, 4.547
PANEL_LEFT, PANEL_PITCH, PANEL_W, PANEL_TOP, PANEL_H = 0.492, 1.818, 1.212, 2.303, 1.627
A_LEFT, A_RIGHT, A_TOP, A_BOTTOM = 0.492, 7.158, 0.233, 1.733
ROW_Y = [0.612, 1.061, 1.510]          # row centres in panel a
TEXT_X, RIGHT_X = 0.527, 4.733
ICON_LEFT, ICON_W, ICON_H = 3.392, 0.967, 0.300
LETTER_X = PANEL_LEFT - 0.13 * PANEL_W  # panel letters share one left edge

ROWS = [  # title, question, icon, what a person-blind generator achieves
    ("Group-summary agreement",
     "Does the simulated population reproduce\nthe summary statistic?",
     "bars", "Reproduced by construction"),
    ("Marginal distributional fidelity",
     "Are simulated values draws from\nthe observed distribution?",
     "curve", "Reproduced by construction"),
    ("Paired individual fidelity",
     "Does the agent for person $i$ reproduce\nthe decision of person $i$?",
     "scatter", "Not reproduced at all"),
]
SCATTER = np.array([  # fixed schematic points (box coordinates), no relation to the 1:1 line
    (0.103, 0.544), (0.141, 0.772), (0.196, 0.633), (0.189, 0.531), (0.252, 0.483),
    (0.203, 0.283), (0.189, 0.194), (0.310, 0.239), (0.390, 0.206), (0.509, 0.878),
    (0.500, 0.544), (0.510, 0.339), (0.541, 0.328), (0.584, 0.461), (0.602, 0.406),
    (0.636, 0.533), (0.643, 0.911), (0.741, 0.378), (0.766, 0.244), (0.860, 0.878),
    (0.876, 0.617), (0.903, 0.528)])

PANELS = [  # csv column, source metric, title, y label, y limits, reference label, label x, ha
    ("mean_ratio_panel_b", "mean_ratio", "Group-summary agreement",
     "Simulated ÷ observed mean", (0.47, 1.46), "observed parity", 1.47, "right"),
    ("ks_minus_shape_null_panel_c", "ks_similarity_minus_distribution_only_reference",
     "Marginal distribution", "KS similarity − reference", (-0.378, 0.07),
     "distribution-only reference", -0.47, "left"),
    ("individual_mae_skill_panel_d", "mae_skill_vs_median_null", "Individual error",
     "Skill vs median null", (-0.88, 0.265), "median\nnull", -0.47, "left"),
    ("agent_at_or_above_observed_p90_pct_panel_e", "pct_at_or_above_observed_p90", "Upper tail",
     "Share ≥ observed p90 (%)", (-1.23, 26.86), "observed 10%", 1.47, "right"),
]
REFERENCE = {"mean_ratio_panel_b": "observed_parity",
             "ks_minus_shape_null_panel_c": "distribution_only_reference",
             "individual_mae_skill_panel_d": "median_null",
             "agent_at_or_above_observed_p90_pct_panel_e": "observed_share_at_or_above_p90"}


def box(left, top, width, height):
    return [left / W, 1 - (top + height) / H, width / W, height / H]


def icon(fig, kind, yc):
    ax = fig.add_axes(box(ICON_LEFT, yc - ICON_H / 2, ICON_W, ICON_H))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.set_xticks([]); ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(True); spine.set_color("#B8B8B8"); spine.set_linewidth(0.6)
    if kind == "bars":
        ax.bar([0.29, 0.706], [0.78, 0.75], width=0.205, color=[C["obs"], C["claude"]])
    elif kind == "curve":
        x = np.linspace(0.04, 0.96, 200)
        y = 0.02 + 0.767 * np.exp(-0.5 * ((x - 0.5) / 0.14) ** 2)
        ax.fill_between(x, 0.02, y, color=C["claude"], alpha=0.35, lw=0)
        ax.plot(x, y, color=C["obs"], lw=1.1)
    else:
        ax.scatter(SCATTER[:, 0], SCATTER[:, 1], s=4.5, color=C["claude"], lw=0, zorder=3)
        ax.plot([0, 1], [0, 1], color=C["parity"], lw=1.0, ls="--", zorder=2)


def schematic(fig):
    ax = fig.add_axes(box(A_LEFT, A_TOP, A_RIGHT - A_LEFT, A_BOTTOM - A_TOP))
    ax.set_xlim(A_LEFT, A_RIGHT); ax.set_ylim(A_BOTTOM, A_TOP)  # inches from the top-left
    ax.axis("off")
    title = {"fontsize": 8.2, "fontweight": "bold"}
    ax.text(TEXT_X, 0.355, "Three validation levels", color="#111111", **title)
    ax.text(RIGHT_X, 0.355, "What a generator blind to individuals achieves",
            color=C["parity"], **title)
    for i, ((name, question, kind, outcome), yc) in enumerate(zip(ROWS, ROW_Y)):
        failed = i == len(ROWS) - 1
        if failed:
            ax.axhspan(yc + 0.200, yc - 0.202, color=C["parity"], alpha=0.055, lw=0, zorder=0)
        ax.text(TEXT_X, yc - 0.093, name, color="#111111", **title)
        for j, line in enumerate(question.split("\n")):
            ax.text(TEXT_X, yc + 0.0325 + 0.139 * j, line, color="#444444", fontsize=7.1)
        ax.text(RIGHT_X, yc + 0.027, outcome,
                color=C["parity"] if failed else "#5B5B5B",
                fontweight="bold" if failed else "normal")
        ax.plot([A_LEFT, A_RIGHT], [yc + 0.217] * 2, color="#E4E4E4", lw=0.7)
        icon(fig, kind, yc)


def strip(ax, df, column, ylim, ref_label, label_x, ha):
    vals = df[column].to_numpy(float)
    assert ylim[0] < vals.min() and vals.max() < ylim[1], f"{column} outside {ylim}"
    rows = []
    for i, (raw, key, _) in enumerate(DATASETS):
        sub = df[df.dataset == raw]
        for _, r in sub.iterrows():
            ax.scatter(i + TIER_X[int(r.tier)], r[column], s=20, marker=TMARK[int(r.tier)],
                       color=C[r.provider], edgecolors="white", linewidths=0.5, zorder=3)
            rows.append({"dataset": key, "provider": r.provider, "tier": int(r.tier),
                         "value": r[column], "benchmark": "agent"})
        ax.plot([i - 0.28, i + 0.28], [sub[column].median()] * 2, color=C["obs"], lw=1.5, zorder=4)

    name = REFERENCE[column]
    if column.endswith("panel_e"):  # each sample carries its own observed share
        for i, (raw, key, _) in enumerate(DATASETS):
            ref = df.loc[df.dataset == raw, "observed_at_or_above_p90_pct"].iloc[0]
            ax.hlines(ref, i - 0.40, i + 0.40, color=C["parity"], lw=1.0, ls="--", zorder=2)
            rows.append({"dataset": key, "provider": name, "tier": np.nan,
                         "value": ref, "benchmark": name})
        label_y = ref  # label sits over the right-hand (Africa) segment
    else:
        label_y = 1.0 if column.endswith("panel_b") else 0.0
        ax.axhline(label_y, color=C["parity"], lw=1.0, ls="--", zorder=2)
        rows += [{"dataset": key, "provider": name, "tier": np.nan, "value": label_y,
                  "benchmark": name} for _, key, _ in DATASETS]
    ax.annotate(ref_label, (label_x, label_y), xytext=(0, 1.2), textcoords="offset points",
                ha=ha, va="bottom", fontsize=6.6, color=C["parity"], linespacing=1.1)
    ax.set_xlim(-0.5, 1.5)
    ax.set_ylim(*ylim)
    ax.set_xticks([0, 1])
    ax.set_xticklabels([label for *_, label in DATASETS])
    ax.grid(axis="y", color="#ECECEC", lw=0.55, zorder=0)
    return rows


def main():
    df = pd.read_csv(SOURCE / "fig1_current_numeric.csv")
    assert len(df) == 24 and set(df.dataset) == {raw for raw, *_ in DATASETS}

    fig = plt.figure(figsize=(W, H))
    schematic(fig)
    fig.text(LETTER_X / W, 1 - 0.200 / H, "a", fontsize=10, fontweight="bold")

    source_rows = []
    for k, (column, metric, title, ylabel, ylim, ref_label, label_x, ha) in enumerate(PANELS):
        ax = fig.add_axes(box(PANEL_LEFT + k * PANEL_PITCH, PANEL_TOP, PANEL_W, PANEL_H))
        rows = strip(ax, df, column, ylim, ref_label, label_x, ha)
        source_rows += [{"panel": "bcde"[k], "metric": metric, **r} for r in rows]
        ax.set_ylabel(ylabel)
        ax.set_title(title, loc="left", pad=5)
        ax.text(-0.13, 1.09, "bcde"[k], transform=ax.transAxes, fontsize=10, fontweight="bold")

    provider_h = [Line2D([], [], marker="o", ls="", color=C[p], label=p.capitalize(),
                         markersize=6) for p in PROV]
    tier_h = [Line2D([], [], marker=TMARK[t], ls="", color="#555555", markerfacecolor="white",
                     label=f"T{t}", markersize=6) for t in TIERS]
    median_h = [Line2D([], [], color=C["obs"], lw=1.5, label="median")]
    fig.legend(handles=provider_h + tier_h + median_h, loc="center",
               bbox_to_anchor=((A_LEFT + A_RIGHT) / 2 / W, 1 - 4.362 / H), ncol=8,
               handletextpad=0.3, columnspacing=0.75)

    source = pd.DataFrame(source_rows)
    source["owning_section"] = OWNER
    source.to_csv(SOURCE / f"{NAME}.csv", index=False)
    fig.savefig(FIG / f"{NAME}.pdf")
    fig.savefig(FIG / f"{NAME}.svg")
    fig.savefig(FIG / f"{NAME}.png", dpi=600)
    fig.savefig(FIG / f"{NAME}.tiff", dpi=600, pil_kwargs={"compression": "tiff_lzw"})
    plt.close(fig)
    print("wrote", NAME)


if __name__ == "__main__":
    main()
