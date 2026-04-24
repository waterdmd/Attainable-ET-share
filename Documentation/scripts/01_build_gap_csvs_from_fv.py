"""
01_build_gap_csvs_from_fv.py
============================
Build ALL gap / coverage / AMA CSVs directly from the Final_Vector shapefiles.

Gap is computed as:
    gap_mm = (ETmm - ATmm).clip(lower=0)

where ATmm is the value ALREADY STORED in the shapefile (the authoritative
pipeline output).  No cohort re-derivation is performed here.

Data source:  Implementation/Final_Vector/
              AZ_AT_ETFullTable_{year}_5.shp   (years 2020-2024)

Outputs (Documentation/data/):
  gap/gap_mm_all_fields_2020_2024.csv          all field-years, col gap_mm (includes zeros)
  gap/pooled_gap_summary_2020_2024.csv         headline pooled stats
  gap/gap_summary_by_year_2020_2024.csv        stats per year (long)
  gap/gap_summary_by_crop_pooled_2020_2024.csv stats per crop (long)
  gap/gap_fraction_nonzero_by_year_2020_2024.csv % fields with gap>0 by year
  gap/benchmarked_fields_area_2020_2024.csv    field count + area by year
  gap/crop_area_shares_2020_2024.csv           crop area / volumetric shares
  ama/ama_savings_2020_2024.csv                long  (AMA x year, mm + AF)
  ama/ama_savings_by_ama_pooled_2020_2024.csv  pooled by AMA
  ama/ama_savings_by_ama_year_wide_af.csv      wide (AF)
  ama/ama_savings_by_ama_year_wide_mm.csv      wide (mm)
  ama/outside_ama_savings_by_year_2020_2024.csv
  ama/outside_ama_savings_pooled_2020_2024.csv
  ama/ama_statewide_totals_by_year_2020_2024.csv

Run with:
  python 01_build_gap_csvs_from_fv.py
"""

import os
import warnings
warnings.filterwarnings('ignore')
import pandas as pd
import geopandas as gpd

# ── Paths ──────────────────────────────────────────────────────────────────
import pathlib as _pl
_CLEAN  = _pl.Path(__file__).resolve().parent.parent   # → Documentation/
_IMPL   = _CLEAN.parent                                 # → Implementation/
FV_DIR  = str(_IMPL / 'Final_Vector')
AMA_SHP = str(_IMPL / 'GeoFiles' / 'AZ_Boundary' / 'AMA_boundaries.shp')
CLEAN   = str(_CLEAN / 'data')
YEARS    = [2020, 2021, 2022, 2023, 2024]

M2_PER_ACRE  = 4046.8564224
AF_PER_M3    = 1.0 / 1233.48183754752

CDL_MAP = {
    1: 'Corn', 2: 'Cotton', 21: 'Barley', 22: 'Wheat', 23: 'Wheat', 24: 'Wheat',
    36: 'Alfalfa', 226: 'Corn', 228: 'Corn', 230: 'Wheat', 232: 'Cotton',
    233: 'Barley', 236: 'Wheat',
}

os.makedirs(f'{CLEAN}/gap', exist_ok=True)
os.makedirs(f'{CLEAN}/ama', exist_ok=True)


# ══════════════════════════════════════════════════════════════════════════
# Step 1 — Load all field-years from Final_Vector
# ══════════════════════════════════════════════════════════════════════════
print('Loading Final_Vector shapefiles...')
frames = []
for yr in YEARS:
    f = f'{FV_DIR}/AZ_AT_ETFullTable_{yr}_5.shp'
    cols = ['CSBID', 'CNTY', 'CSBACRES', 'ETmm', 'ATmm', 'CDL']
    gdf = gpd.read_file(f)
    # Keep geometry for AMA spatial join, then drop
    gdf['Year'] = yr
    gdf['gap_mm'] = (gdf['ETmm'] - gdf['ATmm']).clip(lower=0)
    gdf['Area_m2'] = gdf['CSBACRES'] * M2_PER_ACRE
    gdf['Vol_m3']  = (gdf['gap_mm'] / 1000.0) * gdf['Area_m2']
    gdf['Vol_AF']  = gdf['Vol_m3'] * AF_PER_M3
    gdf['Crop']    = gdf['CDL'].map(CDL_MAP)
    frames.append(gdf)
    print(f'  {yr}: {len(gdf):,} fields  median_gap={gdf["gap_mm"].median():.3f} mm')

df_all = pd.concat(frames, ignore_index=True)
print(f'  Total field-years: {len(df_all):,}\n')


# ══════════════════════════════════════════════════════════════════════════
# Step 2 — Gap summary tables
# ══════════════════════════════════════════════════════════════════════════
def summarize(s):
    s = s.astype(float)
    q1, q3 = s.quantile(0.25), s.quantile(0.75)
    return {
        'N': len(s), 'Median': s.median(), 'Mean': s.mean(),
        'Q1': q1, 'Q3': q3, 'IQR': q3 - q1,
        'P90': s.quantile(0.90), 'P95': s.quantile(0.95),
    }

# Pooled summary (all field-years, gap includes zeros)
pooled = summarize(df_all['gap_mm'])
pooled_df = pd.DataFrame.from_dict(pooled, orient='index', columns=['value'])
pooled_df.to_csv(f'{CLEAN}/gap/pooled_gap_summary_2020_2024.csv')
print('pooled_gap_summary: median={:.3f}  Q1={:.3f}  Q3={:.3f}'.format(
    pooled['Median'], pooled['Q1'], pooled['Q3']))

# Save raw field-year gaps (for bootstrap / detailed analysis)
df_all[['CSBID', 'Year', 'CNTY', 'Crop', 'gap_mm']].to_csv(
    f'{CLEAN}/gap/gap_mm_all_fields_2020_2024.csv', index=False)

# By year (long format)
year_rows = []
for yr in YEARS:
    s = df_all[df_all.Year == yr]['gap_mm']
    stats = summarize(s)
    for k, v in stats.items():
        year_rows.append({'Year': yr, 'stat': k, 'gap_mm': v})
    # nonzero fraction
    year_rows.append({'Year': yr, 'stat': 'Fraction_nonzero_%',
                      'gap_mm': (s > 0).mean() * 100.0})
pd.DataFrame(year_rows).to_csv(
    f'{CLEAN}/gap/gap_summary_by_year_2020_2024.csv', index=False)

# Nonzero fraction by year (separate clean table)
nz_rows = [{'Year': yr,
             'Fraction_nonzero_%': (df_all[df_all.Year == yr]['gap_mm'] > 0).mean() * 100.0}
           for yr in YEARS]
pd.DataFrame(nz_rows).to_csv(
    f'{CLEAN}/gap/gap_fraction_nonzero_by_year_2020_2024.csv', index=False)

# By crop (pooled)
crop_rows = []
for crop in sorted(df_all['Crop'].dropna().unique()):
    s = df_all[df_all.Crop == crop]['gap_mm']
    stats = summarize(s)
    for k, v in stats.items():
        crop_rows.append({'Crop': crop, 'stat': k, 'gap_mm': v})
    crop_rows.append({'Crop': crop, 'stat': 'Fraction_nonzero_%',
                      'gap_mm': (s > 0).mean() * 100.0})
pd.DataFrame(crop_rows).to_csv(
    f'{CLEAN}/gap/gap_summary_by_crop_pooled_2020_2024.csv', index=False)

# Benchmarked fields and area by year
ba_rows = []
for yr in YEARS:
    sub = df_all[df_all.Year == yr]
    ba_rows.append({
        'Year': yr,
        'n_fields': len(sub),
        'area_acres': sub['CSBACRES'].sum(),
        'area_ha': sub['CSBACRES'].sum() * 0.404686,
    })
pd.DataFrame(ba_rows).to_csv(
    f'{CLEAN}/gap/benchmarked_fields_area_2020_2024.csv', index=False)

# Crop area / volumetric shares (pooled 2020-2024)
crop_shares = (df_all.dropna(subset=['Crop'])
               .groupby('Crop', as_index=False)
               .agg(n_field_years=('CSBID', 'count'),
                    total_area_acres=('CSBACRES', 'sum'),
                    total_vol_AF=('Vol_AF', 'sum')))
crop_shares['area_share_%'] = (crop_shares['total_area_acres'] /
                               crop_shares['total_area_acres'].sum() * 100)
crop_shares['vol_share_%']  = (crop_shares['total_vol_AF'] /
                               crop_shares['total_vol_AF'].sum() * 100)
crop_shares.sort_values('vol_share_%', ascending=False).to_csv(
    f'{CLEAN}/gap/crop_area_shares_2020_2024.csv', index=False)

print('Gap tables written.\n')


# ══════════════════════════════════════════════════════════════════════════
# Step 3 — AMA spatial join
# ══════════════════════════════════════════════════════════════════════════
print('AMA spatial join...')
ama_poly = gpd.read_file(AMA_SHP).to_crs(epsg=4326)
if 'BASIN_NAME' not in ama_poly.columns:
    # Try alternate column name
    for col in ama_poly.columns:
        if 'name' in col.lower() or 'basin' in col.lower():
            ama_poly = ama_poly.rename(columns={col: 'BASIN_NAME'})
            break

# Centroid join (faster than polygon intersection)
gdf_centroids = df_all[['CSBID', 'Year', 'CNTY', 'CSBACRES', 'gap_mm',
                         'Area_m2', 'Vol_m3', 'Vol_AF', 'geometry']].copy()
gdf_centroids = gdf_centroids.to_crs(epsg=4326)
gdf_centroids['geometry'] = gdf_centroids.geometry.centroid

joined = gpd.sjoin(gdf_centroids, ama_poly[['BASIN_NAME', 'geometry']],
                   how='left', predicate='within')

inside  = joined[joined['BASIN_NAME'].notna()].copy()
outside = joined[joined['BASIN_NAME'].isna()].copy()

print(f'  Inside AMA: {len(inside):,}  Outside: {len(outside):,}')

# ── AMA long table ────────────────────────────────────────────────────────
def ama_stats(sub):
    total_vol_m3  = sub['Vol_m3'].sum()
    total_area_ac = sub['CSBACRES'].sum()
    return {
        'total_vol_m3':    total_vol_m3,
        'total_area_acres': total_area_ac,
        'n_fields':        len(sub),
        'total_savings_af': sub['Vol_AF'].sum(),
        'savings_mm':      (total_vol_m3 / (total_area_ac * M2_PER_ACRE) * 1000.0
                           if total_area_ac > 0 else 0.0),
    }

ama_rows = []
for (basin, yr), grp in inside.groupby(['BASIN_NAME', 'Year']):
    row = ama_stats(grp)
    row.update({'BASIN_NAME': basin, 'Year': yr})
    ama_rows.append(row)
ama_long = pd.DataFrame(ama_rows)
ama_long.to_csv(f'{CLEAN}/ama/ama_savings_2020_2024.csv', index=False)

# Pooled by AMA
ama_pooled = []
for basin, grp in inside.groupby('BASIN_NAME'):
    row = ama_stats(grp)
    row['BASIN_NAME'] = basin
    ama_pooled.append(row)
pd.DataFrame(ama_pooled).to_csv(
    f'{CLEAN}/ama/ama_savings_by_ama_pooled_2020_2024.csv', index=False)

# Wide AF
ama_wide_af = ama_long.pivot_table(index='BASIN_NAME', columns='Year',
                                   values='total_savings_af').reset_index()
ama_wide_af.columns = ['BASIN_NAME'] + [str(c) for c in ama_wide_af.columns[1:]]
ama_wide_af.to_csv(f'{CLEAN}/ama/ama_savings_by_ama_year_wide_af.csv', index=False)

# Wide mm
ama_wide_mm = ama_long.pivot_table(index='BASIN_NAME', columns='Year',
                                   values='savings_mm').reset_index()
ama_wide_mm.columns = ['BASIN_NAME'] + [str(c) for c in ama_wide_mm.columns[1:]]
ama_wide_mm.to_csv(f'{CLEAN}/ama/ama_savings_by_ama_year_wide_mm.csv', index=False)

# Statewide totals by year (inside AMA only)
sw_rows = inside.groupby('Year').apply(
    lambda g: pd.Series({'total_savings_af': g['Vol_AF'].sum()})
).reset_index()
sw_rows.to_csv(f'{CLEAN}/ama/ama_statewide_totals_by_year_2020_2024.csv', index=False)

# Outside AMA by year
out_rows = []
for yr, grp in outside.groupby('Year'):
    row = ama_stats(grp)
    row['Year'] = yr
    out_rows.append(row)
out_df = pd.DataFrame(out_rows)
out_df.to_csv(f'{CLEAN}/ama/outside_ama_savings_by_year_2020_2024.csv', index=False)

# Outside AMA pooled
out_pooled = ama_stats(outside)
pd.DataFrame([out_pooled]).to_csv(
    f'{CLEAN}/ama/outside_ama_savings_pooled_2020_2024.csv', index=False)

print('AMA tables written.\n')


# ══════════════════════════════════════════════════════════════════════════
# Step 4 — Summary
# ══════════════════════════════════════════════════════════════════════════
print('='*60)
print('Summary (from Final_Vector shapefiles)')
print('='*60)
p = pd.read_csv(f'{CLEAN}/gap/pooled_gap_summary_2020_2024.csv', index_col=0)
print(f"Pooled median : {p.loc['Median','value']:.2f} mm")
print(f"Pooled Q1     : {p.loc['Q1','value']:.2f} mm")
print(f"Pooled Q3     : {p.loc['Q3','value']:.2f} mm")
print(f"Pooled P90    : {p.loc['P90','value']:.2f} mm")
print(f"Pooled P95    : {p.loc['P95','value']:.2f} mm")
print(f"Pooled N      : {int(p.loc['N','value']):,}")

nz = pd.read_csv(f'{CLEAN}/gap/gap_fraction_nonzero_by_year_2020_2024.csv')
print(f"\nNon-zero gap % range (by year): "
      f"{nz['Fraction_nonzero_%'].min():.1f}%–{nz['Fraction_nonzero_%'].max():.1f}%")

ba = pd.read_csv(f'{CLEAN}/gap/benchmarked_fields_area_2020_2024.csv')
print(f"\nField counts by year: {ba['n_fields'].tolist()}")

print(f'\nAll gap + AMA CSVs written to {CLEAN}/gap/ and {CLEAN}/ama/')
