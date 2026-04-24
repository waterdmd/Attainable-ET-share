"""
Regenerate every orphan / stale CSV in Documentation/data/ from the
current Final_Vector, so downstream figures and the manuscript patcher
read consistent numbers.

This script does NOT touch the manuscript. It only rebuilds CSVs that
were never written (orphans) or were left stale from the Apr 7 pipeline
while Final_Vector was rebuilt Apr 9.

Outputs (re)written:
  sensitivity/sensitivity_by_year_5th_vs_10th_goodavg.csv
  sensitivity/sensitivity_by_year_peer_definition_5th.csv
  sensitivity/targeting_curve_summary_2020_2024.csv
  gap/crop_savings_pooled_2020_2024.csv
  gap/crop_savings_by_year_2020_2024.csv
  gap/attainable_et_by_crop_pooled_2020_2024.csv
  gap/attainable_et_by_crop_pooled_2020_2024_wide.csv
  gap/gap_summary_by_year_2020_2024_wide.csv
  gap/gap_summary_by_crop_pooled_2020_2024_wide.csv
  gap/gap_mm_pos_all_fields_2020_2024.csv
  gap/yield_category_counts_by_county_year.csv
  ama/ama_savings_by_year_2020_2024.csv
  ama/ama_savings_by_ama_year_wide_af_2020_2024.csv
  ama/ama_savings_by_ama_year_wide_mm_2020_2024.csv
  ama/ama_savings_by_ama_year_wide_area_2020_2024.csv
  ama/ama_savings_by_ama_year_wide_fields_2020_2024.csv
  tables/Table_4_crop_contrasts_2020_2024.csv
  tables/Table_Sxx_interannual_stability_2020_2024.csv
"""
import os
from pathlib import Path
import pandas as pd
import geopandas as gpd

HERE = Path(__file__).resolve().parent
DOC  = HERE.parent
IMPL = DOC.parent
FV   = IMPL / 'Final_Vector'
DATA = DOC / 'data'

YEARS = [2020, 2021, 2022, 2023, 2024]
CROP_ORDER = ['Alfalfa', 'Cotton', 'Corn', 'Wheat', 'Barley']
M2_PER_ACRE = 4046.8564224
AF_PER_M3   = 1.0 / 1233.48183754752

CDL_MAP = {
    1: 'Corn', 226: 'Corn', 228: 'Corn',
    2: 'Cotton', 232: 'Cotton',
    21: 'Barley', 233: 'Barley',
    22: 'Wheat', 23: 'Wheat', 24: 'Wheat', 230: 'Wheat', 236: 'Wheat',
    36: 'Alfalfa',
}

# ══════════════════════════════════════════════════════════════════════════
# Load Final_Vector once
# ══════════════════════════════════════════════════════════════════════════
print('Loading Final_Vector...')
frames = []
for yr in YEARS:
    g = gpd.read_file(FV / f'AZ_AT_ETFullTable_{yr}_5.shp', ignore_geometry=True)
    g['Year'] = yr
    g['Crop'] = g['CDL'].map(CDL_MAP)
    g['gap_mm'] = (g['ETmm'] - g['ATmm']).clip(lower=0)
    g['Area_m2'] = g['CSBACRES'] * M2_PER_ACRE
    g['Vol_m3']  = (g['gap_mm'] / 1000.0) * g['Area_m2']
    g['Vol_AF']  = g['Vol_m3'] * AF_PER_M3
    frames.append(g)
fv = pd.concat(frames, ignore_index=True)
fv = fv.dropna(subset=['Crop'])
print(f'  {len(fv):,} field-years')

# ══════════════════════════════════════════════════════════════════════════
# 1) Sensitivity summaries (from attainable_et_sensitivity_all.csv)
# ══════════════════════════════════════════════════════════════════════════
print('\nBuilding sensitivity summaries...')
sens_all = pd.read_csv(DATA / 'sensitivity' / 'attainable_et_sensitivity_all.csv')
sens_all = sens_all[sens_all['Year'].isin(YEARS)].copy()

SC_5G = '5th percentile | cats: Average, Good'
SC_10G = '10th percentile | cats: Average, Good'
SC_ALL = '5th percentile | cats: All'
SC_GOOD = '5th percentile | cats: Good'

def yr_stats(df, suffix=''):
    out = df.groupby('Year').agg(
        **{f'total_af{suffix}':       ('Savings_acre_feet', 'sum'),
           f'mean_mm{suffix}':        ('Savings_mm', 'mean'),
           f'median_mm{suffix}':      ('Savings_mm', 'median'),
           f'frac_nonzero{suffix}':   ('Savings_mm', lambda s: 100 * (s > 0).mean()),
           f'n_fields{suffix}':       ('Savings_mm', 'size')}
    ).round(6).reset_index()
    return out

# --- 5th vs 10th (both G+A) ------------------------------------------------
s5  = yr_stats(sens_all[sens_all['Scenario'] == SC_5G],  '_5th')
s10 = yr_stats(sens_all[sens_all['Scenario'] == SC_10G], '_10th')
merged = s5.merge(s10, on='Year')
merged['total_af_pct_change']   = 100 * (merged['total_af_10th'] - merged['total_af_5th']) / merged['total_af_5th']
merged['mean_mm_pct_change']    = 100 * (merged['mean_mm_10th']  - merged['mean_mm_5th'])  / merged['mean_mm_5th']
merged['median_mm_pct_change']  = 100 * (merged['median_mm_10th']- merged['median_mm_5th'])/ merged['median_mm_5th']
merged['frac_nonzero_diff']     = merged['frac_nonzero_10th'] - merged['frac_nonzero_5th']
# Round summary numeric columns for readability
for c in ['total_af_5th','total_af_10th','n_fields_5th','n_fields_10th']:
    merged[c] = merged[c].round(0)
for c in ['mean_mm_5th','mean_mm_10th','median_mm_5th','median_mm_10th',
          'frac_nonzero_5th','frac_nonzero_10th']:
    merged[c] = merged[c].round(1)
for c in ['total_af_pct_change','mean_mm_pct_change','median_mm_pct_change','frac_nonzero_diff']:
    merged[c] = merged[c].round(2)
merged = merged[['Year',
                 'total_af_10th','total_af_5th',
                 'mean_mm_10th','mean_mm_5th',
                 'median_mm_10th','median_mm_5th',
                 'frac_nonzero_10th','frac_nonzero_5th',
                 'n_fields_10th','n_fields_5th',
                 'total_af_pct_change','mean_mm_pct_change',
                 'median_mm_pct_change','frac_nonzero_diff']]
merged.to_csv(DATA / 'sensitivity' / 'sensitivity_by_year_5th_vs_10th_goodavg.csv',
              index=False)
print('  sensitivity_by_year_5th_vs_10th_goodavg.csv')

# --- peer definition (5th; All vs G+A vs Good) -----------------------------
sA = yr_stats(sens_all[sens_all['Scenario'] == SC_ALL],  '_5th_All')
sG = yr_stats(sens_all[sens_all['Scenario'] == SC_5G],   '_5th_Average_Good')
sO = yr_stats(sens_all[sens_all['Scenario'] == SC_GOOD], '_5th_Good')
peer = sA.merge(sG, on='Year').merge(sO, on='Year')
peer['total_af_pct_all_vs_default']  = round(100 * (peer['total_af_5th_All']  - peer['total_af_5th_Average_Good']) / peer['total_af_5th_Average_Good'])
peer['total_af_pct_good_vs_default'] = round(100 * (peer['total_af_5th_Good'] - peer['total_af_5th_Average_Good']) / peer['total_af_5th_Average_Good'])
for c in [col for col in peer.columns if 'total_af_5th' in col or 'n_fields' in col]:
    peer[c] = peer[c].round(0)
for c in [col for col in peer.columns if 'mean_mm' in col or 'median_mm' in col or 'frac_nonzero' in col]:
    peer[c] = peer[c].round(1)
peer = peer[['Year',
             'total_af_5th_All','total_af_5th_Average_Good','total_af_5th_Good',
             'mean_mm_5th_All','mean_mm_5th_Average_Good','mean_mm_5th_Good',
             'median_mm_5th_All','median_mm_5th_Average_Good','median_mm_5th_Good',
             'frac_nonzero_5th_All','frac_nonzero_5th_Average_Good','frac_nonzero_5th_Good',
             'n_fields_5th_All','n_fields_5th_Average_Good','n_fields_5th_Good',
             'total_af_pct_all_vs_default','total_af_pct_good_vs_default']]
peer.to_csv(DATA / 'sensitivity' / 'sensitivity_by_year_peer_definition_5th.csv',
            index=False)
print('  sensitivity_by_year_peer_definition_5th.csv')

# ══════════════════════════════════════════════════════════════════════════
# 2) Targeting curve summary (per year: field and area share reaching 50% of potential)
# ══════════════════════════════════════════════════════════════════════════
print('\nBuilding targeting curve summary...')
rows = []
for yr in YEARS:
    sub = fv[fv['Year'] == yr].copy()
    sub = sub[sub['Vol_AF'] > 0].sort_values('Vol_AF', ascending=False).reset_index(drop=True)
    total = sub['Vol_AF'].sum()
    if total <= 0:
        continue
    cum = sub['Vol_AF'].cumsum()
    idx50 = (cum >= 0.5 * total).idxmax()
    field_share = 100.0 * (idx50 + 1) / len(sub)
    area_share  = 100.0 * sub['CSBACRES'].iloc[: idx50 + 1].sum() / sub['CSBACRES'].sum()
    rows.append({
        'Year': yr,
        'Fields_n': len(sub),
        'Area_acres': round(sub['CSBACRES'].sum(), 6),
        'Total_reduction_AF': round(total, 6),
        'Field_share_for_50pct_%': round(field_share, 1),
        'Area_share_for_50pct_%':  round(area_share, 1),
    })
pd.DataFrame(rows).to_csv(
    DATA / 'sensitivity' / 'targeting_curve_summary_2020_2024.csv', index=False)
print('  targeting_curve_summary_2020_2024.csv')

# ══════════════════════════════════════════════════════════════════════════
# 3) Crop savings (pooled + by year)
# ══════════════════════════════════════════════════════════════════════════
print('\nBuilding crop savings tables...')
def crop_stats(df):
    total_vol = df['Vol_m3'].sum()
    area_ac = df['CSBACRES'].sum()
    return {
        'total_vol_m3':    total_vol,
        'total_area_acres': area_ac,
        'n_fields':        len(df),
        'total_savings_af': df['Vol_AF'].sum(),
        'savings_mm':      (total_vol / (area_ac * M2_PER_ACRE) * 1000.0
                            if area_ac > 0 else 0.0),
    }

pool_rows = []
for crop in CROP_ORDER:
    r = crop_stats(fv[fv['Crop'] == crop])
    r['Crop'] = crop
    pool_rows.append(r)
pd.DataFrame(pool_rows)[['Crop','total_vol_m3','total_area_acres','n_fields',
                         'total_savings_af','savings_mm']].to_csv(
    DATA / 'gap' / 'crop_savings_pooled_2020_2024.csv', index=False)
print('  crop_savings_pooled_2020_2024.csv')

yr_rows = []
for yr in YEARS:
    for crop in CROP_ORDER:
        sub = fv[(fv['Year'] == yr) & (fv['Crop'] == crop)]
        if len(sub) == 0:
            continue
        r = crop_stats(sub)
        r['Year'] = yr
        r['Crop'] = crop
        yr_rows.append(r)
pd.DataFrame(yr_rows)[['Year','Crop','total_vol_m3','total_area_acres','n_fields',
                       'total_savings_af','savings_mm']].to_csv(
    DATA / 'gap' / 'crop_savings_by_year_2020_2024.csv', index=False)
print('  crop_savings_by_year_2020_2024.csv')

# ══════════════════════════════════════════════════════════════════════════
# 4) Attainable ET by crop pooled (long + wide)
# ══════════════════════════════════════════════════════════════════════════
print('\nBuilding attainable_et_by_crop_pooled tables...')
def at_stats(df):
    s = df['ATmm'].astype(float)
    q1, q3 = s.quantile(0.25), s.quantile(0.75)
    return {
        'N': len(s), 'Median': s.median(), 'Mean': s.mean(),
        'Q1': q1, 'Q3': q3, 'IQR': q3 - q1,
        'P90': s.quantile(0.90), 'P95': s.quantile(0.95),
    }

long_rows = []
wide_rows = []
for crop in CROP_ORDER:
    stats = at_stats(fv[fv['Crop'] == crop])
    wide_row = {'Crop': crop, **stats}
    wide_rows.append(wide_row)
    for k, v in stats.items():
        long_rows.append({'Crop': crop, 'level_1': k, 'ATmm': v})
pd.DataFrame(long_rows).to_csv(
    DATA / 'gap' / 'attainable_et_by_crop_pooled_2020_2024.csv', index=False)
pd.DataFrame(wide_rows).to_csv(
    DATA / 'gap' / 'attainable_et_by_crop_pooled_2020_2024_wide.csv', index=False)
print('  attainable_et_by_crop_pooled_2020_2024.csv (+ _wide)')

# ══════════════════════════════════════════════════════════════════════════
# 5) Gap summary wide variants
# ══════════════════════════════════════════════════════════════════════════
print('\nBuilding gap summary wide variants...')
def summarize_gap(s):
    s = s.astype(float)
    q1, q3 = s.quantile(0.25), s.quantile(0.75)
    return {
        'N': len(s), 'Median': s.median(), 'Mean': s.mean(),
        'Q1': q1, 'Q3': q3, 'IQR': q3 - q1,
        'P90': s.quantile(0.90), 'P95': s.quantile(0.95),
        'Fraction_nonzero_%': (s > 0).mean() * 100.0,
    }
yr_wide = []
for yr in YEARS:
    row = {'Year': yr, **summarize_gap(fv[fv['Year']==yr]['gap_mm'])}
    yr_wide.append(row)
pd.DataFrame(yr_wide).to_csv(
    DATA / 'gap' / 'gap_summary_by_year_2020_2024_wide.csv', index=False)

crop_wide = []
for crop in CROP_ORDER:
    row = {'Crop': crop, **summarize_gap(fv[fv['Crop']==crop]['gap_mm'])}
    crop_wide.append(row)
pd.DataFrame(crop_wide).to_csv(
    DATA / 'gap' / 'gap_summary_by_crop_pooled_2020_2024_wide.csv', index=False)
print('  gap_summary_by_{year,crop_pooled}_2020_2024_wide.csv')

# ══════════════════════════════════════════════════════════════════════════
# 6) gap_mm_pos_all_fields (positive gaps only)
# ══════════════════════════════════════════════════════════════════════════
print('\nBuilding gap_mm_pos_all_fields...')
fv[fv['gap_mm'] > 0][['CSBID','Year','CNTY','Crop','gap_mm']].to_csv(
    DATA / 'gap' / 'gap_mm_pos_all_fields_2020_2024.csv', index=False)
print('  gap_mm_pos_all_fields_2020_2024.csv')

# ══════════════════════════════════════════════════════════════════════════
# 7) Yield category counts by county-year
# ══════════════════════════════════════════════════════════════════════════
print('\nBuilding yield_category_counts_by_county_year...')
yc = fv.groupby(['Year', 'CNTY', 'Category']).size().reset_index(name='n')
yc_wide = yc.pivot_table(index=['Year','CNTY'], columns='Category',
                         values='n', fill_value=0).reset_index()
yc_wide.columns.name = None
yc_wide.to_csv(DATA / 'gap' / 'yield_category_counts_by_county_year.csv',
               index=False)
print('  yield_category_counts_by_county_year.csv')

# ══════════════════════════════════════════════════════════════════════════
# 8) AMA wide tables with _2020_2024 suffix + ama_savings_by_year
# ══════════════════════════════════════════════════════════════════════════
print('\nBuilding AMA wide variants...')
ama_long = pd.read_csv(DATA / 'ama' / 'ama_savings_2020_2024.csv')

for key, suffix in [('total_savings_af','af'),
                    ('savings_mm','mm'),
                    ('total_area_acres','area'),
                    ('n_fields','fields')]:
    wide = ama_long.pivot_table(index='BASIN_NAME', columns='Year',
                                values=key, fill_value=0).reset_index()
    wide.columns = ['BASIN_NAME'] + [str(c) for c in wide.columns[1:]]
    wide.to_csv(DATA / 'ama' / f'ama_savings_by_ama_year_wide_{suffix}_2020_2024.csv',
                index=False)
print('  ama_savings_by_ama_year_wide_{af,mm,area,fields}_2020_2024.csv')

# AMA+Non-AMA yearly statewide totals
yr_rows = []
out_yr = pd.read_csv(DATA / 'ama' / 'outside_ama_savings_by_year_2020_2024.csv')
for yr in YEARS:
    af_in  = ama_long[ama_long['Year'] == yr]['total_savings_af'].sum()
    vol_in = ama_long[ama_long['Year'] == yr]['total_vol_m3'].sum()
    area_in = ama_long[ama_long['Year'] == yr]['total_area_acres'].sum()
    n_in   = ama_long[ama_long['Year'] == yr]['n_fields'].sum()
    o_row = out_yr[out_yr['Year'] == yr].iloc[0] if len(out_yr[out_yr['Year'] == yr]) else None
    af_out  = o_row['total_savings_af'] if o_row is not None else 0
    vol_out = o_row['total_vol_m3']     if o_row is not None else 0
    area_out = o_row['total_area_acres'] if o_row is not None else 0
    n_out   = o_row['n_fields']         if o_row is not None else 0
    total_af = af_in + af_out
    total_vol = vol_in + vol_out
    total_area = area_in + area_out
    total_n = int(n_in + n_out)
    mm = (total_vol / (total_area * M2_PER_ACRE) * 1000.0 if total_area > 0 else 0.0)
    yr_rows.append({
        'Year': yr,
        'total_savings_af': total_af,
        'total_vol_m3': total_vol,
        'total_area_acres': total_area,
        'n_fields': total_n,
        'savings_mm': mm,
    })
pd.DataFrame(yr_rows).to_csv(DATA / 'ama' / 'ama_savings_by_year_2020_2024.csv',
                             index=False)
print('  ama_savings_by_year_2020_2024.csv')

# ══════════════════════════════════════════════════════════════════════════
# 9) Table_4_crop_contrasts (same schema as prior file)
# ══════════════════════════════════════════════════════════════════════════
print('\nBuilding Table_4_crop_contrasts...')
tbl4 = []
for crop in CROP_ORDER:
    sub = fv[fv['Crop'] == crop]
    s = sub['gap_mm'].astype(float)
    q1, q3 = s.quantile(0.25), s.quantile(0.75)
    tbl4.append({
        'Crop': crop,
        'Fields': len(sub),
        'Area_acres': round(sub['CSBACRES'].sum(), 0),
        'Gap_Median_mm': round(s.median(), 1),
        'Gap_Q1_mm': round(q1, 1),
        'Gap_Q3_mm': round(q3, 1),
        'Gap_IQR_mm': round(q3 - q1, 1),
        'Gap_P90_mm': round(s.quantile(0.90), 1),
        'Gap_P95_mm': round(s.quantile(0.95), 1),
        'Gap_nonzero_%': round(100 * (s > 0).mean(), 1),
        'Total_savings_af': round(sub['Vol_AF'].sum(), 0),
        'Savings_mm': round(sub['Vol_m3'].sum() / (sub['CSBACRES'].sum() * M2_PER_ACRE) * 1000.0, 1)
                       if sub['CSBACRES'].sum() > 0 else 0.0,
    })
pd.DataFrame(tbl4).to_csv(
    DATA / 'tables' / 'Table_4_crop_contrasts_2020_2024.csv', index=False)
print('  Table_4_crop_contrasts_2020_2024.csv')

# ══════════════════════════════════════════════════════════════════════════
# 10) Table_Sxx interannual stability
# ══════════════════════════════════════════════════════════════════════════
print('\nBuilding Table_Sxx_interannual_stability...')
stab = []
for yr in YEARS:
    sub = fv[fv['Year'] == yr]
    s = sub['gap_mm'].astype(float)
    q1, q3 = s.quantile(0.25), s.quantile(0.75)
    stab.append({
        'Year': yr,
        'Benchmarked_fields': len(sub),
        'Area_acres': round(sub['CSBACRES'].sum(), 0),
        'Median_gap_mm': round(s.median(), 1),
        'Q1_mm': round(q1, 1),
        'Q3_mm': round(q3, 1),
        'IQR_mm': round(q3 - q1, 1),
        'P90_mm': round(s.quantile(0.90), 1),
        'P95_mm': round(s.quantile(0.95), 1),
        'Nonzero_gap_%': round(100 * (s > 0).mean(), 1),
    })
pd.DataFrame(stab).to_csv(
    DATA / 'tables' / 'Table_Sxx_interannual_stability_2020_2024.csv', index=False)
print('  Table_Sxx_interannual_stability_2020_2024.csv')

print('\nDONE — all stale / orphan CSVs regenerated from current Final_Vector.')
