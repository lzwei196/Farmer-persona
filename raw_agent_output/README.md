# Raw agent output

One JSON file per stored response: `<dataset>/<model>/tier<N>/<id>.json`, where `tier<N>` is design T*N* (see `prompts/README.md`).

| Folder | Profiles | Files |
|---|---|---|
| `quzhou/<model>/tier1` to `tier4` | 505 households | 6,060 |
| `lsms/<model>/tier1` to `tier4` | 280 plots | 3,360 |

`<model>` is `claude` (Claude Opus 4.6 through Claude Code, no tool permissions), `codex` (GPT-5.4 through the Codex CLI) or `kimi` (kimi-for-coding through the Kimi CLI). Each dataset folder also holds `_ground_truth.json` (the survey decisions used for evaluation), `_metadata.json` (run settings) and an `errors.log` per model listing failed attempts.

## Fields

| Field | Content |
|---|---|
| `raw_response` | The model's full answer: first-person reasoning followed by JSON |
| `decision` | The JSON object extracted from the answer; `null` when none could be extracted |
| `error` | Client error message, present only when every attempt failed |
| `model` | Client and model label as recorded (`claude-cli`, `codex-cli/gpt-5.4`, `kimi-cli/kimi-for-coding`) |
| `attempts`, `elapsed_seconds` | Calls made for this response and time taken |
| `farmer_id` | Quzhou survey household ID, or `<Country>_<row>` for African plots |
| `farmer_idx`, `country` | African plots only: row in `data/lsms_4country_full.csv` and country |
| `tier`, `provider` | Design number and model |

Quzhou T4 answers use the field names defined in the farmer skill (for example `nitrogen_total_kg_per_mu`); `normalize_plan_entry` in `code/runners/run_quzhou_full.py` maps them to the T1 to T3 names.

## Counts

Of the 9,420 primary responses, 9,301 contain a parsed decision. The other 119 are all in Quzhou: 116 Codex calls still empty after four attempts, one empty Kimi response and two responses with no extractable decision (Supplementary Table 4). Failed calls were retried up to three times, after 30, 60 and 120 s. A further 2,149 Kimi calls in Quzhou returned no usable decision and were re-run; the first usable response was kept. `python3 scripts/verify_inventory.py` recounts every cell.

## Read before use

- **African T4.** The stored African T4 files match a T4 built on the earlier numerical T3, not on the decision guide described in the paper. They will be replaced in a later commit by the run built on the decision guide.
- **Prompts** are not stored in the response files. Rebuild them with the runners (`prompts/README.md`).
- **Redaction.** In the Codex error banners, the local project path is replaced by `<project_dir>` and the home directory by `<home>`. Nothing else was edited. The banners also record the Codex client settings (GPT-5.4, reasoning effort none, workspace-write sandbox).
- **Yield.** In `quzhou/_ground_truth.json`, `yield_kg_per_mu` carries the survey's Yield field unconverted. Its values (wheat median 1,000) indicate jin per mu (0.5 kg). Yield is not analysed in the paper.
