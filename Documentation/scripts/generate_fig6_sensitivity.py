"""
Generate Fig6a (county) and Fig6b (crop) sensitivity scatter figures.

Style based on plot_fig_sensitivity_rankings.py, polished for journal.

Outputs:
  .../figures/png/Fig6a_sensitivity_county.png
  .../figures/png/Fig6b_sensitivity_crop.png
  .../figures/pdf/Fig6a_sensitivity_county.pdf
  .../figures/pdf/Fig6b_sensitivity_crop.pdf
"""

import os
import pathlib
import pandas as pd
import geopandas as gpd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.stats import spearmanr
from matplotlib.ticker import LogFormatterMathtext

# ── Paths ──────────────────────────────────────────────────────────────────
_SCRIPTS = pathlib.Path(__file__).resolve().parent
_DOC     = _SCRIPTS.parent                            # Documentation/
_IMPL    = _DOC.parent                                # Implementation/
FV_DIR   = str(_IMPL / 'Final_Vector')
DATA_DIR = str(_DOC / 'data')
PNG_DIR  = str(_DOC / 'figures' / 'png')
PDF_DIR  = str(_DOC / 'figures' / 'pdf')
os.makedirs(PNG_DIR, exist_ok=True)
os.makedirs(PDF_DIR, exist_ok=True)

# ── CDL → crop name mapping ────────────────────────────────────────────────
CDL_MAP = {
    1: 'Corn',   2: 'Cotton', 21: 'Barley', 22: 'Wheat',  23: 'Wheat',
    24: 'Wheat', 36: 'Alfalfa', 226: 'Corn', 228: 'Corn', 230: 'Wheat',
    232: 'Cotton', 233: 'Barley', 236: 'Wheat',
}

# ── Scenario keys (must match values in the CSV) ───────────────────────────
SC_DEF  = '5th percentile | cats: Average, Good'
SC_10   = '10th percentile | cats: Average, Good'
SC_ALL  = '5th percentile | cats: All'
SC_GOOD = '5th percentile | cats: Good'

LABEL_MAP = {
    SC_DEF:  '5th pct (G+A)',
    SC_10:   '10th pct (G+A)',
    SC_ALL:  '5th pct (All)',
    SC_GOOD: '5th pct (Good)',
}

PAIRS = [
    (SC_DEF, SC_10,   '5th vs 10th (Good+Average)'),
    (SC_DEF, SC_ALL,  '5th: Good+Average vs All'),
    (SC_DEF, SC_GOOD, '5th: Good+Average vs Good-only'),
]

AZ_COUNTIES = [
    'Apache', 'Cochise', 'Coconino', 'Gila', 'Graham', 'Greenlee', 'La Paz',
    'Maricopa', 'Mohave', 'Navajo', 'Pima', 'Pinal', 'Santa Cruz',
    'Yavapai', 'Yuma',
]

# ── Load county-level pooled totals ───────────────────────────────────────
print("Loading county sensitivity data...")
county = pd.read_csv(
    os.path.join(DATA_DIR, 'sensitivity', 'attainable_et_sensitivity_county.csv')
)
county['CNTY'] = county['CNTY'].str.title()
county = county[county['CNTY'].isin(AZ_COUNTIES)].copy()

# ── Load field-level data + CSBID→Crop mapping for crop totals ────────────
print("Loading field-level sensitivity + shapefile crop mapping...")
sens = pd.read_csv(
    os.path.join(DATA_DIR, 'sensitivity', 'attainable_et_sensitivity_all.csv')
)
sens['CSBID'] = pd.to_numeric(sens['CSBID'], errors='coerce').astype('Int64')

# Build CSBID→Crop from Final_Vector shapefiles (CDL column)
csbid_crop = {}
for yr in range(2020, 2025):
    fp = os.path.join(FV_DIR, f'AZ_AT_ETFullTable_{yr}_5.shp')
    if not os.path.exists(fp):
        continue
    gdf = gpd.read_file(fp, columns=['CSBID', 'CDL'])
    for csbid, cdl in zip(gdf['CSBID'], gdf['CDL']):
        if csbid not in csbid_crop and cdl in CDL_MAP:
            csbid_crop[csbid] = CDL_MAP[cdl]

crop_df = pd.DataFrame(list(csbid_crop.items()), columns=['CSBID', 'Crop'])
crop_df['CSBID'] = crop_df['CSBID'].astype('Int64')

sens_c = sens.merge(crop_df, on='CSBID', how='left').dropna(subset=['Crop'])

crop_totals = (
    sens_c.groupby(['Scenario', 'Crop'], as_index=False)
          .agg(Total_Acre_Feet=('Savings_acre_feet', 'sum'))
)

# ── Colors ─────────────────────────────────────────────────────────────────
# Match supplementary figure color scheme (03_generate_supplementary_figures.py)
cnty_color_map = {
    'Maricopa': '#e41a1c', 'Pinal':   '#377eb8',
    'La Paz':   '#4daf4a', 'Yuma':    '#984ea3',
    'Cochise':  '#ff7f00', 'Graham':  '#a65628',
}
top_counties = list(cnty_color_map.keys())

crop_color_map = {
    'Alfalfa': '#0072B2', 'Wheat':  '#E69F00',
    'Corn':    '#009E73', 'Cotton': '#CC79A7',
    'Barley':  '#D55E00',
}
crops = sorted(crop_color_map.keys())

# ── Journal-quality rcParams ──────────────────────────────────────────────
plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams.update({
    'font.size': 9,
    'axes.titlesize': 9,
    'axes.labelsize': 9,
    'xtick.labelsize': 8,
    'ytick.labelsize': 8,
    'figure.dpi': 300,
    'pdf.fonttype': 42,      # TrueType — keeps text editable in Illustrator
    'ps.fonttype': 42,
})
try:
    plt.rcParams['font.family'] = 'Arial'
    import matplotlib.font_manager as fm
    fm.findfont('Arial', fallback_to_default=False)
except Exception:
    plt.rcParams['font.family'] = 'DejaVu Sans'


# ── Inset-size constant ───────────────────────────────────────────────────
# With aspect='equal' and xlim/ylim=(1e5,1e7), 10^6 is at axes fraction 0.5.
# Top-left box center = (0.25, 0.75); bottom-right = (0.75, 0.25).
# 38%×38% inset centred in each box:
SZ = 0.38
_OFF = (0.50 - SZ) / 2.0     # = 0.06  offset from box edge to centre


def _style_inset_box(inset_ax):
    """Give an inset an opaque white background with a thin frame."""
    inset_ax.set_facecolor('white')
    inset_ax.patch.set_alpha(1.0)
    inset_ax.patch.set_zorder(4)
    for sp in inset_ax.spines.values():
        sp.set_linewidth(0.5)
        sp.set_color('#888888')
        sp.set_zorder(5)


def _draw_full_range_inset(ax, x_vals, y_vals, a, b, entities, color_map,
                           s_gray=8, s_color=12):
    """Full-range inset (top-left box, centred)."""
    ins = ax.inset_axes([_OFF, 0.50 + _OFF, SZ, SZ])
    ins.scatter(x_vals, y_vals, s=s_gray, color='#C7C7C7', alpha=0.7,
                linewidth=0, zorder=2)
    for ent in entities:
        if ent in a.index and ent in b.index:
            ins.scatter(max(a.loc[ent], 1), max(b.loc[ent], 1),
                        s=s_color, color=color_map[ent], zorder=3)
    ins.plot([1e1, 1e7], [1e1, 1e7],
             '--', color='#BBBBBB', linewidth=0.5)
    ins.set_xscale('log'); ins.set_yscale('log')
    ins.set_xlim(1e1, 1e7); ins.set_ylim(1e1, 1e7)
    ins.set_xticks([1e1, 1e3, 1e5, 1e7])
    ins.set_yticks([1e1, 1e3, 1e5, 1e7])
    ins.xaxis.set_major_formatter(LogFormatterMathtext())
    ins.yaxis.set_major_formatter(LogFormatterMathtext())
    ins.tick_params(labelsize=4, length=2, pad=1)
    ins.tick_params(top=False, right=False, labeltop=False, labelright=False)
    ins.tick_params(direction='in')
    ins.spines['top'].set_visible(False)
    ins.spines['right'].set_visible(False)
    ins.set_facecolor('white')
    ins.patch.set_alpha(1.0)
    ins.text(0.04, 0.96, 'Full range', transform=ins.transAxes,
             ha='left', va='top', fontsize=5.5, style='italic',
             color='#444444')
    return ins


def _draw_pct_change_inset(ax, pct_series, color_map, label='% change'):
    """% change bar inset (bottom-right box, centred).

    Label is placed INSIDE the inset at the top to avoid overlapping
    the parent 10^6 gridline that runs through axes fraction 0.5.
    """
    ins = ax.inset_axes([0.50 + _OFF, _OFF, SZ, SZ])
    ins.bar(range(len(pct_series)), pct_series.values,
            color=[color_map[c] for c in pct_series.index],
            width=0.65, zorder=2, linewidth=0)
    ins.axhline(0, color='#555555', linewidth=0.6, zorder=3)
    vmin, vmax = pct_series.min(), pct_series.max()
    margin = max(abs(vmin), abs(vmax)) * 0.15
    ins.set_ylim(vmin - margin, vmax + margin)
    ins.set_yticks([round(vmin, 1), 0, round(vmax, 1)])
    ins.tick_params(axis='y', labelsize=5, length=2, pad=1)
    ins.set_xticks([])
    _style_inset_box(ins)
    # Label just ABOVE the inset box (outside), centred
    ins.set_title(label, fontsize=5.5, style='italic', color='#444444',
                  pad=2)
    return ins


# ══════════════════════════════════════════════════════════════════════════
# Fig 6a — County sensitivity scatter
# ══════════════════════════════════════════════════════════════════════════
print("Generating Fig 6a (county)...")

fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.6), dpi=300)

for ax, (s1, s2, title) in zip(axes, PAIRS):
    a = county[county['Scenario'] == s1].set_index('CNTY')['Total_Acre_Feet']
    b = county[county['Scenario'] == s2].set_index('CNTY')['Total_Acre_Feet']
    common = a.index.intersection(b.index)
    x_vals = a.loc[common].clip(lower=1)
    y_vals = b.loc[common].clip(lower=1)
    rho = spearmanr(x_vals, y_vals).correlation

    # Scatter
    for cnty in common:
        xv = max(a.loc[cnty], 1)
        yv = max(b.loc[cnty], 1)
        # Nudge points sitting exactly on the lower boundary slightly inward
        if xv <= 1e5:
            xv = 1.08e5
        if yv <= 1e5:
            yv = 1.08e5
        if cnty in top_counties:
            ax.scatter(xv, yv, s=70, color=cnty_color_map[cnty],
                       edgecolor='white', linewidth=0.4, zorder=3)
        else:
            ax.scatter(xv, yv, s=30, color='#C7C7C7',
                       edgecolor='none', alpha=0.7, zorder=2)

    # 1:1 line
    ax.plot([1e5, 1e7], [1e5, 1e7], '--', color='#AAAAAA', linewidth=0.6, zorder=1)

    # Axes formatting
    ax.set_title(f'{title},  $\\rho$\u2009=\u2009{rho:.2f}', fontsize=9, pad=4)
    ax.set_xlabel(LABEL_MAP[s1] + ' [acre-ft]', fontsize=8)
    ax.set_ylabel(LABEL_MAP[s2] + ' [acre-ft]', fontsize=8)
    ax.set_xscale('log');  ax.set_yscale('log')
    ax.set_xlim(1e5, 1e7); ax.set_ylim(1e5, 1e7)
    ax.set_aspect('equal', adjustable='box')
    ax.set_axisbelow(True)
    ax.grid(True, axis='both', alpha=0.18, linewidth=0.4, color='#bbbbbb')
    ax.tick_params(labelsize=7.5, length=3, width=0.5)
    for sp in ax.spines.values():
        sp.set_linewidth(0.5)

    # Insets
    pct = ((y_vals - x_vals) / x_vals) * 100
    top_pct = pct.reindex(top_counties).dropna()
    _draw_pct_change_inset(ax, top_pct, cnty_color_map, label='% change')
    _draw_full_range_inset(ax, x_vals, y_vals, a, b, top_counties,
                           cnty_color_map, s_gray=8, s_color=12)

# Legend
handles, labels = [], []
for c in top_counties:
    handles.append(plt.Line2D([0], [0], marker='o', color='w',
                               markerfacecolor=cnty_color_map[c],
                               markeredgecolor='white', markersize=6))
    labels.append(c)
handles.append(plt.Line2D([0], [0], marker='o', color='w',
                            markerfacecolor='#C7C7C7', markersize=5))
labels.append('Other counties')
fig.legend(handles, labels, loc='lower center', bbox_to_anchor=(0.5, 0.01),
           frameon=False, fontsize=7.5, ncol=len(handles),
           handletextpad=0.3, columnspacing=1.0)
fig.subplots_adjust(left=0.06, right=0.98, top=0.91, bottom=0.20, wspace=0.32)

fig.savefig(os.path.join(PNG_DIR, 'Fig6a_sensitivity_county.png'), dpi=300)
fig.savefig(os.path.join(PDF_DIR, 'Fig6a_sensitivity_county.pdf'))
plt.close(fig)
print("  saved Fig6a_sensitivity_county")

# ══════════════════════════════════════════════════════════════════════════
# Fig 6b — Crop sensitivity scatter
# ══════════════════════════════════════════════════════════════════════════
print("Generating Fig 6b (crop)...")

fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.6), dpi=300)

for ax, (s1, s2, title) in zip(axes, PAIRS):
    a = crop_totals[crop_totals['Scenario'] == s1].set_index('Crop')['Total_Acre_Feet']
    b = crop_totals[crop_totals['Scenario'] == s2].set_index('Crop')['Total_Acre_Feet']
    common = a.index.intersection(b.index)
    x_vals = a.loc[common].clip(lower=1)
    y_vals = b.loc[common].clip(lower=1)
    rho = spearmanr(x_vals, y_vals).correlation

    # Scatter
    for crop in common:
        xv = max(a.loc[crop], 1)
        yv = max(b.loc[crop], 1)
        if xv <= 1e5:
            xv = 1.08e5
        if yv <= 1e5:
            yv = 1.08e5
        ax.scatter(xv, yv, s=110, color=crop_color_map[crop],
                   edgecolor='white', linewidth=0.4, zorder=3)

    # 1:1 line
    ax.plot([1e5, 1e7], [1e5, 1e7], '--', color='#AAAAAA', linewidth=0.6)

    # Axes formatting
    ax.set_title(f'{title},  $\\rho$\u2009=\u2009{rho:.2f}', fontsize=9, pad=4)
    ax.set_xlabel(LABEL_MAP[s1] + ' [acre-ft]', fontsize=8)
    ax.set_ylabel(LABEL_MAP[s2] + ' [acre-ft]', fontsize=8)
    ax.set_xscale('log');  ax.set_yscale('log')
    ax.set_xlim(1e5, 1e7); ax.set_ylim(1e5, 1e7)
    ax.set_aspect('equal', adjustable='box')
    ax.set_axisbelow(True)
    ax.grid(True, axis='both', alpha=0.18, linewidth=0.4, color='#bbbbbb')
    ax.tick_params(labelsize=7.5, length=3, width=0.5)
    for sp in ax.spines.values():
        sp.set_linewidth(0.5)

    # Insets
    pct = ((y_vals - x_vals) / x_vals) * 100
    _draw_pct_change_inset(ax, pct, crop_color_map, label='% change')
    _draw_full_range_inset(ax, x_vals, y_vals, a, b, list(common),
                           crop_color_map, s_gray=18, s_color=22)

# Legend
handles, labels = [], []
for c in crops:
    handles.append(plt.Line2D([0], [0], marker='o', color='w',
                               markerfacecolor=crop_color_map[c],
                               markeredgecolor='white', markersize=7))
    labels.append(c)
fig.legend(handles, labels, loc='lower center', bbox_to_anchor=(0.5, 0.01),
           frameon=False, fontsize=7.5, ncol=len(handles),
           handletextpad=0.3, columnspacing=1.0)
fig.subplots_adjust(left=0.06, right=0.98, top=0.91, bottom=0.20, wspace=0.32)

fig.savefig(os.path.join(PNG_DIR, 'Fig6b_sensitivity_crop.png'), dpi=300)
fig.savefig(os.path.join(PDF_DIR, 'Fig6b_sensitivity_crop.pdf'))
plt.close(fig)
print("  saved Fig6b_sensitivity_crop")

print(f"\nSaved to:\n  {PNG_DIR}\n  {PDF_DIR}")
