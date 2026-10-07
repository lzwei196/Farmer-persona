# Survey data

Both sources are openly licensed. Cite them as below if you reuse these files.

## Quzhou County, China (`quzhou/`)

`Farm_household_data.csv` (505 households, 955 fields), `Crop_data.csv` (farmer-crop records) and `Village_data.csv`. The survey interviewed 525 households in 35 villages in July and August 2020 about the June 2019 to June 2020 season; 505 records are valid. The study uses all 505 households and the 1,349 crop records linked to 504 of them.

- Source: Xu, Z., Li, F., Cheng, J., Liang, Z., Groot, J., Zhang, C., van der Werf, W., 2023. Survey data on livelihoods and inputs and outputs of crop production activities in Quzhou county on the North China Plain. Mendeley Data, V1. https://doi.org/10.17632/jp3v9859cx.1
- Licence: CC BY 4.0
- Data article: Xu et al., 2024. Data in Brief 53, 110269. https://doi.org/10.1016/j.dib.2024.110269

The household and crop files are Windows-1252 encoded (read them with `encoding="latin-1"`). The Yield field is recorded in jin per mu (0.5 kg), judging by its values (wheat median 1,000). `code/analysis/profiles.py` builds the farmer profiles and computes nitrogen, phosphorus and potassium rates in kg ha⁻¹ from the fertiliser records.

## Four-country African panel (`lsms_4country_full.csv`)

280 plots, 70 each from Ethiopia (ESS 2015/16), Malawi (IHPS 2019), Nigeria (GHS-Panel 2018/19) and Tanzania (NPS 2012/13), belonging to 274 households. Within each country, 35 plots are flagged as inorganic-fertiliser users and 35 as non-users, so the panel cannot estimate national adoption rates. Plots were drawn from those with a GPS area of 0.05 to 20 ha and complete manager, crop and nitrogen fields, balancing female and male managers with and without schooling where possible. After the area filter and before the field requirements, the pools were Ethiopia 11,448, Malawi 5,715, Nigeria 6,902 and Tanzania 6,190 plots (`lsms_4country_full_stats.md`). Nitrogen rates above 300 kg ha⁻¹ were set to missing (five plots).

- Source: the LSMS-ISA harmonised panel of Bentze, T. and Wollburg, P., v2.0. Zenodo. https://doi.org/10.5281/zenodo.15773365
- Licence: CC0 1.0 (v2.0; the earlier v1 record, https://doi.org/10.5281/zenodo.14040658, is CC BY 4.0)
- Data article: Bentze, T. and Wollburg, P., 2025. A longitudinal cross-country dataset on agricultural productivity and welfare in sub-Saharan Africa. Scientific Data 12, 1843.
- The underlying LSMS-ISA surveys are distributed by the World Bank Microdata Library.

`hh_id_merge` and `plot_id_merge` are the harmonised panel's identifiers. The script that drew these 280 plots was not archived. `code/runners/build_lsms_4country_sample.py` is the pilot version (13 plots per country) with the same filters.

## Ground truth

`raw_agent_output/<dataset>/_ground_truth.json` holds the survey decisions each response is scored against, keyed as in the response files.
