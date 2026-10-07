# Prompt designs

Every prompt in the study is built from the files in this folder. Each design keeps the information of the previous design and adds one more class of information about the farmer:

| Design | Class added | Quzhou households | African plots |
|---|---|---|---|
| T1 | Profile: who the farmer is | 49-word farmer role; age, gender, education and county; annual-plan task and JSON schema | Identity card: country, region, manager age, gender and education, plot and farm size, ownership, intercropping, main crop; eight-question task and JSON schema |
| T2 | Current circumstances: the farm and its setting | Adds farming experience, farm size, reported crops, cropping system, household size and off-farm work | Adds the agro-ecological zones of the country and the plot's region |
| T3 | Procedural guidance: how the farmer decides | Replaces the short role with a 487-word decision guide (no numbers) | Adds a 929-word first-person decision guide (no numbers) |
| T4 | Semantic knowledge: what the farmer knows | Replaces the guide with the Quzhou farmer skill (1,682 words: persona, decision rules, regional practice ranges, local units, own output format) | Adds the African farmer skill: practice norms by country, zone and crop, plot-scaled nitrogen and labour ranges, consistency checks |

## Files and assembly

**Quzhou** (`quzhou/`). Prompt = system text + two newlines + user text.

| Design | System text | User text |
|---|---|---|
| T1 | `T1_T2_role.txt` | `T1_user.txt` |
| T2 | `T1_T2_role.txt` | `T2_T3_user.txt` |
| T3 | `T3_guide.txt` | `T2_T3_user.txt` |
| T4 | `T4_farmer_skill/SKILL.md` | `T4_user.txt` (no JSON schema; the skill defines the output) |

**African plots** (`lsms/`). Each design places its block above the previous prompt.

| Design | Assembly |
|---|---|
| T1 | `T1_identity_card.txt` |
| T2 | `T2_zone_context/<country>.md` + `You are in the {region} region.` + `---` + T1 |
| T3 | `T3_guide.txt` + `---` + T2 |
| T4 | `T4_farmer_skill/SKILL.md` + T2. The skill file holds the T4 checks followed by the T3 guide, so T4 = checks + T3. Its fields are filled from the plot's area and `T4_farmer_skill/country_norms.json`. |

Fields in braces are filled from each survey record by `code/runners/run_quzhou_full.py` and `code/runners/run_lsms_full.py`. `examples/` holds the complete prompts for one Quzhou household (AZ_DF_1) and one African plot (Nigeria_0).

Rebuilding all 3,140 prompts (505 households and 280 plots at T1 to T4) from these files reproduces, byte for byte, the text produced by the builders used in the runs. The model clients may add their own system instructions, which are not included here.

## Builder details that affect interpretation

- Quzhou: every T2 to T4 profile states access to well irrigation. Missing household size is set to 4 (13 profiles) and missing farming experience to 20 years (2 profiles). Eight profiles without a recorded age read "unknown-year-old". Education is passed as the survey's category label (for example "middle" or "high"). Age refers to the household head.
- Quzhou: 146 profiles pass on the survey's spelling "mazie" for maize. The analysis maps it to maize.
- African T4: the asset-index line reads 0.00 for every plot, because the panel has no asset index. The nitrogen check states its threshold as 120 kg × plot area, a plot total, while the task asks for kg per hectare.
- African T1 says "based only on the identity card below", although the T2 to T4 blocks are placed above it.

## The two farmer skills

`quzhou/T4_farmer_skill/SKILL.md` and `lsms/T4_farmer_skill/SKILL.md` are the T4 farmer skills. In the study they were sent as plain prompt text inside the single call. They were not installed as tools, and the agents had no memory between calls. The practice values in the African skill are approximate national or regional figures, not estimates from the evaluation panel.
