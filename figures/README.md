# Figures

File names come from the scripts that draw them; the table maps them to the paper. Each plotted figure is saved as PDF, SVG, PNG (600 dpi) and TIFF, and its plotted values are in `source_data/`.

| Paper | File | Made by | Plotted values |
|---|---|---|---|
| Fig. 1 | `fig1_prompt_architecture.pptx` (editable), `.pdf`, `.png` | PowerPoint | |
| Fig. 2 | `fig_validation_levels` | `code/analysis/fig_validation_levels.py` | `fig_validation_levels.csv`, built from `fig1_current_numeric.csv` |
| Fig. 3 | `fig1_validation_gap` | `code/analysis/paper1_figures.py` | `fig1_validation_gap.csv` |
| Fig. 4 | `fig2B_strip` | `code/analysis/paper1_figures.py` | `fig2_dispersion_tail.csv` |
| Fig. 5 | `fig1_compression` | `code/analysis/paper1_figures.py` | `fig1_compression.csv` |
| Fig. 6 | `fig3_context_response` | `code/analysis/paper1_figures.py` | `fig3_prompt_effects.csv` |
| Supplementary Fig. 1 | `fig2C_heatmap` | `code/analysis/paper1_figures.py` | `fig2_dispersion_tail.csv` |
| Supplementary Fig. 2 | `fig2A_dumbbell` | `code/analysis/paper1_figures.py` | `fig2_dispersion_tail.csv` |
| Supplementary Fig. 3 | `fig2D_slope` | `code/analysis/paper1_figures.py` | `fig2_dispersion_tail.csv` |
| Supplementary Fig. 4 | `fig4_country` | `code/analysis/paper1_figures.py` | `fig4_country.csv` |

Rebuild with `python3 code/analysis/current_fig1_source.py`, then `python3 code/analysis/fig_validation_levels.py` and `python3 code/analysis/paper1_figures.py`. The first writes `fig1_current_numeric.csv`, the per-cell values behind Fig. 2.

Colours: Claude blue, Codex terracotta, Kimi green. Markers: T1 circle, T2 square, T3 triangle, T4 diamond. Dark red marks parity with the survey.
