"""
Build Table S6 (AMA total reduction potential, pooled 2020-2024) and
Table S7 (AMA area-normalized reduction potential with yearly min/max).

Inputs:
  data/ama/ama_savings_by_ama_pooled_2020_2024.csv    (pooled per-AMA)
  data/ama/outside_ama_savings_pooled_2020_2024.csv   (pooled non-AMA)
  data/ama/ama_savings_2020_2024.csv                  (yearly AMA)
  data/ama/outside_ama_savings_by_year_2020_2024.csv  (yearly non-AMA)

Outputs:
  data/tables/Table_S6_AMA_total_reduction.csv
  data/tables/Table_S7_AMA_area_normalized.csv
"""
import os
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DOC  = os.path.abspath(os.path.join(HERE, '..'))
AMA  = os.path.join(DOC, 'data', 'ama')
OUT  = os.path.join(DOC, 'data', 'tables')
os.makedirs(OUT, exist_ok=True)

# Row order for the manuscript tables
AMA_ORDER = ['Phoenix', 'Pinal', 'Tucson', 'Santa Cruz', 'Douglas', 'Willcox']

def pretty(name):
    return name.replace(' AMA', '').title()

# ── Pooled (for totals and area-normalized) ───────────────────────────────
pooled = pd.read_csv(os.path.join(AMA, 'ama_savings_by_ama_pooled_2020_2024.csv'))
pooled['AMA'] = pooled['BASIN_NAME'].map(pretty)
# Prescott has effectively zero fields; drop from the manuscript table but
# keep in the full CSV for transparency.
pooled_main = pooled[pooled['AMA'] != 'Prescott'].copy()

outside = pd.read_csv(os.path.join(AMA, 'outside_ama_savings_pooled_2020_2024.csv'))

# ── Yearly (for min/max mm/yr) ────────────────────────────────────────────
yearly = pd.read_csv(os.path.join(AMA, 'ama_savings_2020_2024.csv'))
yearly['AMA'] = yearly['BASIN_NAME'].map(pretty)
yearly_outside = pd.read_csv(os.path.join(AMA, 'outside_ama_savings_by_year_2020_2024.csv'))

# Statewide total for share calculation = all AMAs + Non-AMA
statewide_af = pooled_main['total_savings_af'].sum() + outside['total_savings_af'].sum()

# ── Table S6 ──────────────────────────────────────────────────────────────
rows = []
for name in AMA_ORDER:
    r = pooled_main[pooled_main['AMA'] == name].iloc[0]
    rows.append({
        'AMA': name,
        'Benchmarked fields': int(r['n_fields']),
        'Benchmarked area (acres)': round(r['total_area_acres'], 0),
        'Total reduction potential (acre-feet)': round(r['total_savings_af'], 0),
        'Share of statewide total (%)': round(100 * r['total_savings_af'] / statewide_af, 1),
    })
out_r = outside.iloc[0]
rows.append({
    'AMA': 'Non-AMA',
    'Benchmarked fields': int(out_r['n_fields']),
    'Benchmarked area (acres)': round(out_r['total_area_acres'], 0),
    'Total reduction potential (acre-feet)': round(out_r['total_savings_af'], 0),
    'Share of statewide total (%)': round(100 * out_r['total_savings_af'] / statewide_af, 1),
})
rows.append({
    'AMA': 'Total',
    'Benchmarked fields': sum(r['Benchmarked fields'] for r in rows),
    'Benchmarked area (acres)': round(sum(r['Benchmarked area (acres)'] for r in rows), 0),
    'Total reduction potential (acre-feet)': round(sum(r['Total reduction potential (acre-feet)'] for r in rows), 0),
    'Share of statewide total (%)': 100.0,
})

s6 = pd.DataFrame(rows)
s6_path = os.path.join(OUT, 'Table_S6_AMA_total_reduction.csv')
s6.to_csv(s6_path, index=False)
print(f'Saved: {s6_path}')
print(s6.to_string(index=False))

# ── Table S7 ──────────────────────────────────────────────────────────────
rows7 = []
for name in AMA_ORDER:
    r = pooled_main[pooled_main['AMA'] == name].iloc[0]
    yr_sub = yearly[yearly['AMA'] == name]
    # Only count years where the AMA has non-negligible area (>1 acre)
    yr_valid = yr_sub[yr_sub['total_area_acres'] > 1]
    rows7.append({
        'AMA': name,
        'Benchmarked area (acres)': round(r['total_area_acres'], 0),
        'Total reduction potential (acre-feet)': round(r['total_savings_af'], 0),
        'Area-normalized (mm/yr)': round(r['savings_mm'], 1),
        'Yearly min (mm/yr)': round(yr_valid['savings_mm'].min(), 1) if len(yr_valid) else None,
        'Yearly max (mm/yr)': round(yr_valid['savings_mm'].max(), 1) if len(yr_valid) else None,
    })
out_r = outside.iloc[0]
rows7.append({
    'AMA': 'Non-AMA',
    'Benchmarked area (acres)': round(out_r['total_area_acres'], 0),
    'Total reduction potential (acre-feet)': round(out_r['total_savings_af'], 0),
    'Area-normalized (mm/yr)': round(out_r['savings_mm'], 1),
    'Yearly min (mm/yr)': round(yearly_outside['savings_mm'].min(), 1),
    'Yearly max (mm/yr)': round(yearly_outside['savings_mm'].max(), 1),
})

s7 = pd.DataFrame(rows7)
s7_path = os.path.join(OUT, 'Table_S7_AMA_area_normalized.csv')
s7.to_csv(s7_path, index=False)
print()
print(f'Saved: {s7_path}')
print(s7.to_string(index=False))
