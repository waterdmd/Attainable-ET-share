"""
Build Table S5: Crop-specific attainable-ET gap statistics (pooled 2020-2024).

Uses the same authoritative Final_Vector source as Table S6 so the two tables
sum to identical totals. Previously, Table S5 in supplementary_material.md was
populated from a stale pipeline (147,527 fields) that does not match current
Final_Vector (142,809 fields) or Table S6.

Input:
  data/gap/gap_mm_all_fields_2020_2024.csv       (field-year gaps; authoritative)
  Final_Vector/AZ_AT_ETFullTable_{year}_5.shp    (for area and gap volumes)

Output:
  data/tables/Table_S5_crop_contrasts.csv
"""
import os
import pandas as pd
import geopandas as gpd

HERE = os.path.dirname(os.path.abspath(__file__))
DOC  = os.path.abspath(os.path.join(HERE, '..'))
IMPL = os.path.abspath(os.path.join(DOC, '..'))
FV   = os.path.join(IMPL, 'Final_Vector')
OUT  = os.path.join(DOC, 'data', 'tables')
os.makedirs(OUT, exist_ok=True)

YEARS = [2020, 2021, 2022, 2023, 2024]
CROP_ORDER = ['Alfalfa', 'Cotton', 'Corn', 'Wheat', 'Barley']

# CDL -> crop mapping (matches 01_build_gap_csvs_from_fv.py logic)
CDL_MAP = {
    1: 'Corn', 226: 'Corn', 228: 'Corn',
    2: 'Cotton', 232: 'Cotton',
    21: 'Barley', 233: 'Barley',
    22: 'Wheat', 23: 'Wheat', 24: 'Wheat', 230: 'Wheat', 236: 'Wheat',
    36: 'Alfalfa',
}

M2_PER_ACRE = 4046.8564224
AF_PER_M3   = 1.0 / 1233.48183754752

frames = []
for yr in YEARS:
    g = gpd.read_file(os.path.join(FV, f'AZ_AT_ETFullTable_{yr}_5.shp'),
                      ignore_geometry=True)
    g['Year'] = yr
    g['Crop'] = g['CDL'].map(CDL_MAP)
    g['gap_mm'] = (g['ETmm'] - g['ATmm']).clip(lower=0)
    g['Vol_AF'] = (g['gap_mm'] / 1000.0) * (g['CSBACRES'] * M2_PER_ACRE) * AF_PER_M3
    frames.append(g[['CSBID', 'Year', 'Crop', 'CSBACRES', 'gap_mm', 'Vol_AF']])
df = pd.concat(frames, ignore_index=True)
df = df.dropna(subset=['Crop'])

rows = []
for crop in CROP_ORDER:
    sub = df[df.Crop == crop]
    s = sub['gap_mm']
    q1, q3 = s.quantile(0.25), s.quantile(0.75)
    rows.append({
        'Crop': crop,
        'Fields': len(sub),
        'Area (acres)': round(sub['CSBACRES'].sum(), 0),
        'Median gap (mm)': round(s.median(), 1),
        'Q1 (mm)': round(q1, 1),
        'Q3 (mm)': round(q3, 1),
        'IQR (mm)': round(q3 - q1, 1),
        'P90 (mm)': round(s.quantile(0.90), 1),
        'P95 (mm)': round(s.quantile(0.95), 1),
        'Non-zero gap (%)': round(100 * (s > 0).mean(), 1),
        'Total (af)': round(sub['Vol_AF'].sum(), 0),
        'Mean gap (mm)': round(s.mean(), 1),
    })

s5 = pd.DataFrame(rows)
s5_path = os.path.join(OUT, 'Table_S5_crop_contrasts.csv')
s5.to_csv(s5_path, index=False)
print(f'Saved: {s5_path}')
print(s5.to_string(index=False))
print()
print(f'Totals: {s5["Fields"].sum():,} fields, '
      f'{s5["Area (acres)"].sum():,.0f} acres, '
      f'{s5["Total (af)"].sum():,.0f} AF')
