"""
Regenerate all cohort/* CSVs from current Final_Vector + source shapefiles.

Cohort = (CDL, TempC, PrecC, SoilClass) intersection among Good+Average fields.
Fields = Good+Average only (these define the peer benchmark pool).
Uses raw CDL code (not Crop name) so cohort statistics reflect the actual
benchmark groups used by the Generating_AttainableET pipeline and by
01_build_analysis_outputs.py sensitivity scenarios. Dual-crop codes 226,
228, 230, 232, 233, 236 are thus kept as their own cohorts, matching
Final_Vector / Table S5 / Table S9 reconciliation.

Outputs written to Documentation/data/cohort/:
  cohort_reliability_field_year.csv    (one row per field-year, with cohort_id, cohort_n, reliability_class)
  cohort_reliability_summary_pooled.csv
  cohort_reliability_by_crop_pooled.csv
  cohort_reliability_by_county_pooled.csv
  cohort_reliability_by_year.csv
  cohort_size_bins_overall.csv
  cohort_size_bins_by_year.csv
  cohort_size_summary_by_year.csv
  cohort_p5_bootstrap_ci_by_year.csv
  cohort_p5_ci_summary_by_bin.csv
"""
import os
from pathlib import Path
import numpy as np
import pandas as pd
import geopandas as gpd

HERE = Path(__file__).resolve().parent
DOC  = HERE.parent
IMPL = DOC.parent
DATA = DOC / 'data'
OUT  = DATA / 'cohort'
OUT.mkdir(parents=True, exist_ok=True)

TEMP_DIR  = IMPL / 'GeoFiles' / 'Temperature_800m' / 'FarmWise'
PREC_DIR  = IMPL / 'GeoFiles' / 'Precipitation_800m' / 'FarmWise'
FV_DIR    = IMPL / 'Final_Vector'
YIELD_DIR = IMPL / 'GeoFiles' / 'Farm_Yield'
SOIL_PATH = IMPL / 'GeoFiles' / 'Soil' / 'FarmWise' / 'Farm_SoilTaxonomy_clean.shp'

YEARS = [2020, 2021, 2022, 2023, 2024]

SIZE_BINS = [('<5', 0, 5), ('5-9', 5, 10), ('10-19', 10, 20), ('20-29', 20, 30),
             ('30-49', 30, 50), ('50-99', 50, 100), ('100-199', 100, 200),
             ('200+', 200, float('inf'))]
BIN_ORDER = [b[0] for b in SIZE_BINS]

RELIABILITY = [
    ('Unreliable', 0, 10),
    ('Sparse',     10, 20),
    ('Very low',   20, 50),
    ('Low',        50, 100),
    ('Moderate',   100, 200),
    ('High',       200, float('inf')),
]
REL_ORDER = [r[0] for r in RELIABILITY]


def bin_size(n):
    for lbl, lo, hi in SIZE_BINS:
        if lo <= n < hi:
            return lbl
    return '200+'


def classify_reliability(n):
    for lbl, lo, hi in RELIABILITY:
        if lo <= n < hi:
            return lbl
    return 'High'


# ══════════════════════════════════════════════════════════════════════════
# Build field-year cohort table (G+A fields only)
# ══════════════════════════════════════════════════════════════════════════
print('Loading source shapefiles...')
soil = gpd.read_file(SOIL_PATH, ignore_geometry=True)[['CSBID','SoilClass']]

field_rows = []
for yr in YEARS:
    temp = gpd.read_file(TEMP_DIR / f'Farm_Temperature_{yr}.shp', ignore_geometry=True)
    prec = gpd.read_file(PREC_DIR / f'Farm_Precipitation_{yr}.shp', ignore_geometry=True)
    et   = gpd.read_file(FV_DIR  / f'AZ_AT_ETFullTable_{yr}_5.shp', ignore_geometry=True)
    yld  = gpd.read_file(YIELD_DIR / f'AZ_Yield_{yr}.shp', ignore_geometry=True)

    df = (temp[['CSBID', f'TempC_{yr}']]
          .merge(prec[['CSBID', f'PrecC_{yr}']], on='CSBID', how='inner')
          .merge(et[['CSBID', 'ETmm', 'CDL']], on='CSBID', how='inner')
          .merge(yld[['CSBID', 'CNTY', 'Crop', 'Category']], on='CSBID', how='inner')
          .merge(soil, on='CSBID', how='inner'))

    df['Category'] = df['Category'].astype(str).str.strip().str.title()
    df['Crop']     = df['Crop'].astype(str).str.strip().str.title()
    df['CNTY']     = df['CNTY'].astype(str).str.strip().str.title()
    df[f'TempC_{yr}'] = df[f'TempC_{yr}'].astype(str).str.strip().str.title()
    df[f'PrecC_{yr}'] = df[f'PrecC_{yr}'].astype(str).str.strip().str.title()
    df['SoilClass'] = df['SoilClass'].astype('Int64')

    # Good + Average only (benchmark peer pool)
    df = df[df['Category'].isin(['Good', 'Average'])].copy()
    df = df.dropna(subset=['CDL', 'Crop', f'TempC_{yr}', f'PrecC_{yr}',
                           'SoilClass', 'ETmm'])

    df = df.rename(columns={f'TempC_{yr}': 'TempC', f'PrecC_{yr}': 'PrecC',
                            'ETmm': 'et_mm'})
    df['Year'] = yr
    df['cohort_id'] = (df['CDL'].astype(str) + '|' + df['TempC'].astype(str) +
                       '|' + df['PrecC'].astype(str) + '|' +
                       df['SoilClass'].astype(str))

    cohort_sizes = df.groupby('cohort_id').size().rename('cohort_n')
    df = df.join(cohort_sizes, on='cohort_id')
    df['reliability_class'] = df['cohort_n'].apply(classify_reliability)
    field_rows.append(df)
    print(f'  {yr}: {len(df):,} G+A field-years, {df.cohort_id.nunique()} cohorts')

all_fields = pd.concat(field_rows, ignore_index=True)
print(f'  Total: {len(all_fields):,} field-years, {all_fields.groupby(["Year","cohort_id"]).ngroups} year-cohorts')

# ══════════════════════════════════════════════════════════════════════════
# 1) Field-level file (for Table S2, Fig 1, etc.)
# ══════════════════════════════════════════════════════════════════════════
out_field = all_fields[['Year','CSBID','CNTY','Crop','cohort_id','cohort_n','reliability_class']]
out_field.to_csv(OUT / 'cohort_reliability_field_year.csv', index=False)
print(f'\nSaved: cohort_reliability_field_year.csv ({len(out_field):,} rows)')

# ══════════════════════════════════════════════════════════════════════════
# 2) Reliability class summaries (pooled + by-year + by-crop + by-county)
# ══════════════════════════════════════════════════════════════════════════
sum_pool = (all_fields.groupby('reliability_class')
            .agg(fields=('CSBID','count'))
            .reset_index())
sum_pool['pct_fields'] = 100.0 * sum_pool['fields'] / sum_pool['fields'].sum()
sum_pool['reliability_class'] = pd.Categorical(sum_pool['reliability_class'],
                                                REL_ORDER, ordered=True)
sum_pool = sum_pool.sort_values('reliability_class')
sum_pool.to_csv(OUT / 'cohort_reliability_summary_pooled.csv', index=False)
print('Saved: cohort_reliability_summary_pooled.csv')

by_crop = (all_fields.groupby(['Crop','reliability_class'])
           .agg(fields=('CSBID','count')).reset_index())
crop_tot = all_fields.groupby('Crop').agg(total_fields=('CSBID','count')).reset_index()
by_crop = by_crop.merge(crop_tot, on='Crop', how='left')
by_crop['pct_fields'] = 100.0 * by_crop['fields'] / by_crop['total_fields']
by_crop.to_csv(OUT / 'cohort_reliability_by_crop_pooled.csv', index=False)
print('Saved: cohort_reliability_by_crop_pooled.csv')

by_cnty = (all_fields.groupby(['CNTY','reliability_class'])
           .agg(fields=('CSBID','count')).reset_index())
cnty_tot = all_fields.groupby('CNTY').agg(total_fields=('CSBID','count')).reset_index()
by_cnty = by_cnty.merge(cnty_tot, on='CNTY', how='left')
by_cnty['pct_fields'] = 100.0 * by_cnty['fields'] / by_cnty['total_fields']
by_cnty.to_csv(OUT / 'cohort_reliability_by_county_pooled.csv', index=False)
print('Saved: cohort_reliability_by_county_pooled.csv')

by_year = (all_fields.groupby(['Year','reliability_class'])
           .agg(fields=('CSBID','count')).reset_index())
yr_tot = all_fields.groupby('Year').agg(total_fields=('CSBID','count')).reset_index()
by_year = by_year.merge(yr_tot, on='Year', how='left')
by_year['pct_fields'] = 100.0 * by_year['fields'] / by_year['total_fields']
by_year.to_csv(OUT / 'cohort_reliability_by_year.csv', index=False)
print('Saved: cohort_reliability_by_year.csv')

# ══════════════════════════════════════════════════════════════════════════
# 3) Cohort-size bins (one row per cohort per year)
# ══════════════════════════════════════════════════════════════════════════
year_cohorts = (all_fields.groupby(['Year','cohort_id'])
                .agg(n_fields=('CSBID','count')).reset_index())
year_cohorts['size_bin'] = year_cohorts['n_fields'].apply(bin_size)

# by-year bins
bins_by_year = (year_cohorts.groupby(['Year','size_bin'])
                .agg(n_cohorts=('cohort_id','count'),
                     n_fields=('n_fields','sum')).reset_index())
yr_field_tot = year_cohorts.groupby('Year').agg(year_fields=('n_fields','sum')).reset_index()
bins_by_year = bins_by_year.merge(yr_field_tot, on='Year', how='left')
bins_by_year['pct_fields'] = 100.0 * bins_by_year['n_fields'] / bins_by_year['year_fields']
bins_by_year.to_csv(OUT / 'cohort_size_bins_by_year.csv', index=False)
print('Saved: cohort_size_bins_by_year.csv')

# overall bins (pooling all year-cohorts)
bins_overall = (year_cohorts.groupby('size_bin')
                .agg(n_cohorts=('cohort_id','count'),
                     n_fields=('n_fields','sum')).reset_index())
bins_overall['pct_fields'] = 100.0 * bins_overall['n_fields'] / bins_overall['n_fields'].sum()
bins_overall['size_bin'] = pd.Categorical(bins_overall['size_bin'], BIN_ORDER, ordered=True)
bins_overall = bins_overall.sort_values('size_bin')
bins_overall.to_csv(OUT / 'cohort_size_bins_overall.csv', index=False)
print('Saved: cohort_size_bins_overall.csv')

# per-year cohort-size summary statistics
summary_rows = []
for yr in YEARS:
    sub = year_cohorts[year_cohorts['Year'] == yr]
    n_cohorts = len(sub)
    if n_cohorts == 0:
        continue
    sizes = sub['n_fields']
    yr_field_total = sizes.sum()
    summary_rows.append({
        'Year': yr,
        'n_cohorts': n_cohorts,
        'median_n': sizes.median(),
        'p10':  sizes.quantile(0.10),
        'p25':  sizes.quantile(0.25),
        'p75':  sizes.quantile(0.75),
        'pct_cohorts_lt10': 100.0 * (sizes < 10).sum() / n_cohorts,
        'pct_cohorts_lt20': 100.0 * (sizes < 20).sum() / n_cohorts,
        'pct_cohorts_lt30': 100.0 * (sizes < 30).sum() / n_cohorts,
        'pct_fields_lt10':  100.0 * sub.loc[sub['n_fields'] < 10, 'n_fields'].sum() / yr_field_total,
        'pct_fields_lt20':  100.0 * sub.loc[sub['n_fields'] < 20, 'n_fields'].sum() / yr_field_total,
        'pct_fields_lt30':  100.0 * sub.loc[sub['n_fields'] < 30, 'n_fields'].sum() / yr_field_total,
    })
pd.DataFrame(summary_rows).to_csv(OUT / 'cohort_size_summary_by_year.csv', index=False)
print('Saved: cohort_size_summary_by_year.csv')

# ══════════════════════════════════════════════════════════════════════════
# 4) Bootstrap P5 CI per (year, cohort)
# ══════════════════════════════════════════════════════════════════════════
print('\nBootstrapping P5 CI (n_boot=2000, seed=42)...')
rng = np.random.default_rng(42)
N_BOOT = 2000

def boot_p5_ci(vals):
    n = len(vals)
    if n < 5:
        return (np.nan, np.nan)
    boots = np.empty(N_BOOT)
    for i in range(N_BOOT):
        s = rng.choice(vals, size=n, replace=True)
        boots[i] = np.percentile(s, 5)
    return (float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5)))

ci_rows = []
n_groups = all_fields.groupby(['Year','cohort_id']).ngroups
for i, ((yr, cid), grp) in enumerate(all_fields.groupby(['Year','cohort_id'])):
    vals = grp['et_mm'].dropna().values
    n = len(vals)
    p5 = float(np.percentile(vals, 5)) if n > 0 else np.nan
    ci_low, ci_high = boot_p5_ci(vals)
    ci_rows.append({
        'Year': int(yr),
        'cohort_id': cid,
        'Crop': grp['Crop'].iloc[0],
        'TempC': grp['TempC'].iloc[0],
        'PrecC': grp['PrecC'].iloc[0],
        'SoilClass': int(grp['SoilClass'].iloc[0]) if pd.notna(grp['SoilClass'].iloc[0]) else None,
        'n_fields': int(n),
        'p5_etmm': p5,
        'p5_ci_low': ci_low,
        'p5_ci_high': ci_high,
        'p5_ci_width': (ci_high - ci_low) if pd.notna(ci_low) else np.nan,
    })
    if (i + 1) % 200 == 0:
        print(f'  {i+1}/{n_groups} cohorts done')
ci_df = pd.DataFrame(ci_rows)
ci_df.to_csv(OUT / 'cohort_p5_bootstrap_ci_by_year.csv', index=False)
print(f'Saved: cohort_p5_bootstrap_ci_by_year.csv ({len(ci_df):,} year-cohorts)')

# ══════════════════════════════════════════════════════════════════════════
# 5) CI width summary by size bin
# ══════════════════════════════════════════════════════════════════════════
ci_df['size_bin'] = ci_df['n_fields'].apply(bin_size)
summary_ci = (ci_df.groupby(['Year','size_bin'])
              .agg(n_cohorts=('cohort_id','count'),
                   median_ci_width=('p5_ci_width','median'),
                   mean_ci_width=('p5_ci_width','mean'))
              .reset_index())
summary_ci.to_csv(OUT / 'cohort_p5_ci_summary_by_bin.csv', index=False)
print('Saved: cohort_p5_ci_summary_by_bin.csv')

print('\nDONE — all cohort/* CSVs regenerated.')
