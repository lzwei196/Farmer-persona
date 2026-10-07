"""
Build the 4-country LSMS-ISA pilot sample (Nigeria, Ethiopia, Tanzania, Malawi).

Filters:
  - plot_area_GPS in [0.05, 20] ha
  - Ethiopia fert_user redefined: inorganic_fertilizer == 'Yes' AND nitrogen_kg > 0
  - Compute N/ha as the primary fertilizer rate target
  - Cap N/ha at 300 kg/ha (set to NaN above)
  - Yield cap at 8000 kg/ha
  - Labor: keep as-is, evaluated within-country only

Sampling:
  - 13 farmers per country (52 total) - balanced stratification on fert use,
    gender, and education where possible
"""
import pandas as pd
import numpy as np
from pathlib import Path

OUT_CSV = Path('agriagent/data/lsms/lsms_4country_pilot.csv')
OUT_STATS = Path('agriagent/data/lsms/lsms_4country_pilot_stats.md')
SEED = 42
PER_COUNTRY = 13

COUNTRY_WAVES = {
    'Nigeria': 4,
    'Ethiopia': 3,
    'Tanzania': 3,
    'Malawi': 4,
}


def yn_to_int(s):
    """Map 'Yes'/'No' to 1/0, NaN passthrough."""
    return s.map({'Yes': 1, 'No': 0}).astype('Int64')


def load_country(plot, country, wave):
    c = plot[(plot['country'] == country) & (plot['wave'] == wave)].copy()

    # Convert Yes/No categoricals to ints
    for col in ['inorganic_fertilizer', 'female_manager', 'formal_education_manager',
                'primary_education_manager', 'irrigated', 'married_manager', 'plot_owned']:
        if col in c.columns:
            c[col] = yn_to_int(c[col])

    # Region normalization
    if 'admin_1_name' in c.columns:
        c['region_clean'] = c['admin_1_name'].astype(str).str.strip()
        # Strip leading number prefixes (Nigeria "2. North East" -> "North East")
        c['region_clean'] = c['region_clean'].str.replace(r'^\d+\.\s*', '', regex=True)
        # Malawi admin_1_name is empty -- fall back to admin_2_name (district)
        if country == 'Malawi' and 'admin_2_name' in c.columns:
            mask = c['region_clean'].isin(['', 'nan'])
            c.loc[mask, 'region_clean'] = c.loc[mask, 'admin_2_name'].astype(str).str.strip()

    # Plot area filter
    c = c[(c['plot_area_GPS'] >= 0.05) & (c['plot_area_GPS'] <= 20)].copy()

    # Compute N/ha
    c['nitrogen_kg_per_ha'] = c['nitrogen_kg'] / c['plot_area_GPS']
    c.loc[c['nitrogen_kg_per_ha'] > 300, 'nitrogen_kg_per_ha'] = np.nan

    # Yield cap
    c['yield_kg_per_ha'] = c['harvest_kg'] / c['plot_area_GPS']
    c.loc[c['yield_kg_per_ha'] > 8000, 'yield_kg_per_ha'] = np.nan

    # fert_user definition
    if country == 'Ethiopia':
        # Redefinition: require N>0 (drops organic-only false positives)
        c['fert_user'] = ((c['inorganic_fertilizer'] == 1) & (c['nitrogen_kg'] > 0)).astype(int)
    else:
        c['fert_user'] = (c['inorganic_fertilizer'] == 1).astype('Int64').fillna(0).astype(int)

    # Labor per ha (for display, NOT cross-country comparison)
    c['family_labor_d_per_ha'] = c['total_family_labor_days'] / c['plot_area_GPS']

    return c


def stratified_sample(df, n, country):
    """Stratified: ~50/50 fert/non-fert, diversity in gender & education."""
    rng = np.random.RandomState(SEED + hash(country) % 1000)

    # Must have: female_manager, formal_education_manager, age_manager, main_crop
    req = df[df['female_manager'].notna()
             & df['formal_education_manager'].notna()
             & df['age_manager'].notna()
             & df['main_crop'].notna()
             & df['nitrogen_kg'].notna()].copy()

    n_fert = n // 2
    n_non = n - n_fert

    fert_pool = req[req['fert_user'] == 1]
    non_pool = req[req['fert_user'] == 0]

    # If fert_user count is small, fall back to what's available
    n_fert = min(n_fert, len(fert_pool))
    n_non = min(n - n_fert, len(non_pool))

    def pick(pool, k):
        if len(pool) == 0 or k == 0:
            return pool.iloc[:0]
        # Try to get balance across (female × formal_education) strata
        pool = pool.copy()
        pool['_strat'] = pool['female_manager'].astype(str) + '_' + pool['formal_education_manager'].astype(str)
        strata = pool['_strat'].unique()
        per = max(1, k // len(strata))
        picks = []
        for s in strata:
            sub = pool[pool['_strat'] == s]
            take = min(per, len(sub))
            if take > 0:
                picks.append(sub.sample(n=take, random_state=rng.randint(0, 1e9)))
        out = pd.concat(picks) if picks else pool.iloc[:0]
        if len(out) < k:
            remaining = pool.drop(out.index)
            extra = remaining.sample(n=min(k - len(out), len(remaining)), random_state=rng.randint(0, 1e9))
            out = pd.concat([out, extra])
        elif len(out) > k:
            out = out.sample(n=k, random_state=rng.randint(0, 1e9))
        return out.drop(columns='_strat')

    return pd.concat([pick(fert_pool, n_fert), pick(non_pool, n_non)]).reset_index(drop=True)


def main():
    print('Loading Plot_dataset.dta...')
    plot = pd.read_stata('agriagent/ LSMS-ISA data/Plot_dataset.dta')

    all_samples = []
    stats_lines = ['# LSMS 4-Country Pilot Sample Stats\n']

    for country, wave in COUNTRY_WAVES.items():
        print(f'\n=== {country} W{wave} ===')
        c = load_country(plot, country, wave)
        print(f'  After filters (area 0.05-20 ha): {len(c)}')
        print(f'  Fert users: {c["fert_user"].sum()} ({c["fert_user"].mean()*100:.0f}%)')

        sample = stratified_sample(c, PER_COUNTRY, country)
        sample['country'] = country
        sample['wave'] = wave
        print(f'  Sampled: {len(sample)} '
              f'(fert={sample["fert_user"].sum()}, female={sample["female_manager"].sum()}, '
              f'educ={sample["formal_education_manager"].sum()})')

        stats_lines.append(f'\n## {country} (Wave {wave})')
        stats_lines.append(f'- Pool after area filter: {len(c)}')
        stats_lines.append(f'- Fert users in pool: {c["fert_user"].sum()} ({c["fert_user"].mean()*100:.1f}%)')
        stats_lines.append(f'- Sampled: {len(sample)} farmers')
        stats_lines.append(f'- Sample fert users: {sample["fert_user"].sum()}')
        stats_lines.append(f'- Sample female managers: {sample["female_manager"].sum()}')
        stats_lines.append(f'- Sample with formal education: {sample["formal_education_manager"].sum()}')
        stats_lines.append(f'- Main crops: {dict(sample["main_crop"].value_counts())}')
        stats_lines.append(f'- Median plot area (ha): {sample["plot_area_GPS"].median():.2f}')
        stats_lines.append(f'- Median N kg/ha (fert users): '
                           f'{sample[sample["fert_user"]==1]["nitrogen_kg_per_ha"].median():.1f}')

        all_samples.append(sample)

    combined = pd.concat(all_samples, ignore_index=True)

    # Keep only columns we need for the experiment
    keep_cols = [
        'country', 'wave', 'hh_id_merge', 'plot_id_merge',
        'admin_1_name', 'region_clean', 'main_crop',
        'plot_area_GPS', 'farm_size',
        'age_manager', 'female_manager', 'formal_education_manager', 'primary_education_manager',
        'married_manager',
        'fert_user', 'inorganic_fertilizer', 'nitrogen_kg', 'nitrogen_kg_per_ha',
        'organic_fertilizer',
        'improved', 'used_pesticides', 'irrigated',
        'harvest_kg', 'yield_kg_per_ha',
        'total_family_labor_days', 'total_hired_labor_days', 'family_labor_d_per_ha',
        'intercropped',
        'drought_shock', 'pests_shock', 'flood_shock', 'crop_shock',
        'dist_popcenter', 'elevation', 'plot_owned',
    ]
    keep_cols = [c for c in keep_cols if c in combined.columns]
    combined = combined[keep_cols]

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(OUT_CSV, index=False)
    print(f'\nSaved: {OUT_CSV} ({len(combined)} rows, {len(combined.columns)} cols)')

    stats_lines.append(f'\n## Combined')
    stats_lines.append(f'- Total: {len(combined)}')
    stats_lines.append(f'- Fert users: {combined["fert_user"].sum()}')
    stats_lines.append(f'- Female: {combined["female_manager"].sum()}')
    stats_lines.append(f'- Formal education: {combined["formal_education_manager"].sum()}')
    OUT_STATS.write_text('\n'.join(stats_lines))
    print(f'Saved: {OUT_STATS}')

    print('\n=== Sample preview ===')
    print(combined[['country', 'main_crop', 'plot_area_GPS', 'fert_user',
                    'nitrogen_kg_per_ha', 'female_manager', 'formal_education_manager']].to_string())


if __name__ == '__main__':
    main()
