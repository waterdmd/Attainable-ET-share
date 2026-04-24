"""
Build Table S2: Peer cohort summary by crop (pooled 2020-2024).

Reads the field-year cohort reliability table and computes, per crop:
  - Active cohorts (counting each year-cohort instance separately, which
    matches the per-year benchmark-assignment logic used in the paper)
  - Median / min / max cohort size (fields per year-cohort)
  - Fraction of benchmarked fields sitting in cohorts with N >= 50, 100, 200
    so reviewers see how conditioning scales across thresholds
  - Companion cohort-weighted view: fraction of cohorts at N<20, N<50,
    N>=100, N>=200 (the field-weighted view is the operative one for
    diagnostics; the cohort-weighted view answers the "how many cohorts
    are small" question)

Inputs:
  data/cohort/cohort_reliability_field_year.csv

Outputs:
  data/tables/Table_S2_peer_cohort_summary.csv         (field-weighted, main table)
  data/tables/Table_S2b_cohort_size_distribution.csv   (cohort-weighted companion)
"""
import os
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DOC  = os.path.abspath(os.path.join(HERE, '..'))
IN   = os.path.join(DOC, 'data', 'cohort', 'cohort_reliability_field_year.csv')
OUT_DIR = os.path.join(DOC, 'data', 'tables')
os.makedirs(OUT_DIR, exist_ok=True)

CROP_ORDER = ['Alfalfa', 'Cotton', 'Corn', 'Wheat', 'Barley']

df = pd.read_csv(IN)

# Each (Year, cohort_id) is a distinct cohort instance because benchmarks
# are computed per year. cohort_id encodes Crop|Precip|Temp|Soil.
yc = df.groupby(['Year', 'Crop', 'cohort_id']).size().reset_index(name='n')

def summarize(sub_yc, sub_fy, label):
    total_fields = len(sub_fy)
    return {
        'Crop': label,
        'Active cohorts': len(sub_yc),
        'Median N': int(sub_yc['n'].median()),
        'Min N': int(sub_yc['n'].min()),
        'Max N': int(sub_yc['n'].max()),
        'Fields in N>=50 (%)':  round(100 * (sub_fy['cohort_n'] >= 50).sum()
                                      / total_fields, 1),
        'Fields in N>=100 (%)': round(100 * (sub_fy['cohort_n'] >= 100).sum()
                                      / total_fields, 1),
        'Fields in N>=200 (%)': round(100 * (sub_fy['cohort_n'] >= 200).sum()
                                      / total_fields, 1),
        'Total field-years': total_fields,
    }

rows = []
for crop in CROP_ORDER:
    rows.append(summarize(
        yc[yc['Crop'] == crop],
        df[df['Crop'] == crop],
        crop,
    ))
rows.append(summarize(yc, df, 'All crops'))

main = pd.DataFrame(rows)
main_out = os.path.join(OUT_DIR, 'Table_S2_peer_cohort_summary.csv')
main.to_csv(main_out, index=False)
print(f'Saved: {main_out}')
print(main.to_string(index=False))

# Companion: cohort-weighted size distribution
def size_row(sub_yc, label):
    n = len(sub_yc)
    return {
        'Crop': label,
        'Cohorts': n,
        '% cohorts N<20':   round(100 * (sub_yc['n'] < 20).sum()   / n, 1),
        '% cohorts N<50':   round(100 * (sub_yc['n'] < 50).sum()   / n, 1),
        '% cohorts N>=50':  round(100 * (sub_yc['n'] >= 50).sum()  / n, 1),
        '% cohorts N>=100': round(100 * (sub_yc['n'] >= 100).sum() / n, 1),
        '% cohorts N>=200': round(100 * (sub_yc['n'] >= 200).sum() / n, 1),
    }

size_rows = [size_row(yc[yc['Crop'] == c], c) for c in CROP_ORDER]
size_rows.append(size_row(yc, 'All crops'))
size = pd.DataFrame(size_rows)
size_out = os.path.join(OUT_DIR, 'Table_S2b_cohort_size_distribution.csv')
size.to_csv(size_out, index=False)
print()
print(f'Saved: {size_out}')
print(size.to_string(index=False))
