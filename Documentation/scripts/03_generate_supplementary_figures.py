"""
Generate all supplementary + spatial figures in PNG (300 dpi) and PDF (vector).

Produces:
  Fig3          — Spatial hotspot map, pooled 2020-2024 (statewide + 6 insets)
  FigS1–FigS5  — Per-year spatial hotspot maps (2020-2024)
  FigS6–FigS10 — Per-year county sensitivity scatter (2020-2024)
  FigS11–FigS15 — Per-year crop sensitivity scatter (2020-2024)

Outputs:
  PNG → Documentation/figures/png/
  PDF → Documentation/figures/pdf/

Run with:
  python 03_generate_supplementary_figures.py
(Requires a Python env with geopandas + matplotlib + GDAL; on Windows,
ensure the conda-provided GDAL Library/bin is on PATH before running.)
"""

import os, warnings
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
from matplotlib.patches import Circle, Ellipse
from matplotlib.patches import ConnectionPatch as ConnPatch
from matplotlib.colors import PowerNorm
warnings.filterwarnings('ignore')

# ── paths ─────────────────────────────────────────────────────────────────
import pathlib as _pl
_CLEAN     = _pl.Path(__file__).resolve().parent.parent   # → Documentation/
_IMPL      = _CLEAN.parent                                 # → Implementation/
FV_DIR     = str(_IMPL / 'Final_Vector')
COUNTY_SHP = str(_IMPL / 'GeoFiles' / 'AZ_Boundary' / 'az_counties_2024.shp')
AMA_SHP    = str(_IMPL / 'GeoFiles' / 'AZ_Boundary' / 'AMA_boundaries.shp')
SENS_CSV   = str(_CLEAN / 'data' / 'sensitivity' / 'attainable_et_sensitivity_all.csv')
PNG_DIR    = str(_CLEAN / 'figures' / 'png')
PDF_DIR    = str(_CLEAN / 'figures' / 'pdf')
os.makedirs(PNG_DIR, exist_ok=True)
os.makedirs(PDF_DIR, exist_ok=True)

# ── shared style ──────────────────────────────────────────────────────────
plt.rcParams.update({
    'font.family':    'Arial',
    'font.size':      11,
    'axes.labelsize': 11,
    'axes.titlesize': 12,
    'xtick.labelsize':10,
    'ytick.labelsize':10,
    'legend.fontsize': 9.5,
    'axes.linewidth': 0.8,
    'figure.dpi':     300,
    'pdf.fonttype':   42,        # TrueType — editable text in Illustrator
    'ps.fonttype':    42,
})

CDL_MAP = {1:'Corn',2:'Cotton',21:'Barley',22:'Wheat',23:'Wheat',24:'Wheat',
           36:'Alfalfa',226:'Corn',228:'Corn',230:'Wheat',232:'Cotton',
           233:'Barley',236:'Wheat'}

CROP_COLORS = {
    'Alfalfa':'#0072B2','Wheat':'#E69F00','Corn':'#009E73',
    'Cotton':'#CC79A7','Barley':'#D55E00',
}

def savefig_both(fig, stem):
    fig.savefig(os.path.join(PNG_DIR, stem+'.png'), dpi=300, bbox_inches='tight',
                facecolor='white')
    fig.savefig(os.path.join(PDF_DIR, stem+'.pdf'), bbox_inches='tight',
                facecolor='white')
    print(f"  saved {stem}")

# ── load basemaps ──────────────────────────────────────────────────────────
print("Loading basemaps...")
az  = gpd.read_file(COUNTY_SHP).to_crs(epsg=4326)
ama = gpd.read_file(AMA_SHP).to_crs(epsg=4326)

# county centroids for labels
az['cx'] = az.geometry.centroid.x
az['cy'] = az.geometry.centroid.y
county_labels = {
    'Maricopa':   (-112.0, 33.4),
    'Pinal':      (-111.3, 32.8),
    'La Paz':     (-114.0, 33.7),
    'Yuma':       (-114.2, 32.5),
    'Cochise':    (-109.8, 31.9),
    'Graham':     (-109.9, 32.8),
    'Mohave':     (-113.8, 35.2),
    'Pima':       (-111.4, 32.1),
}

# ── elliptical inset positions (figure coords: x0, y0, w, h) ─────────────
# Figure is 16×10.  Main map ~[0.24, 0.10, 0.36, 0.80].
# All insets placed fully outside the main map rectangle — no overlap.
INSET_POSITIONS = {
    'La Paz':   (0.02, 0.52, 0.16, 0.36),   # tall ellipse, left upper
    'Yuma':     (0.01, 0.06, 0.22, 0.22),   # circle, left lower
    'Pinal':    (0.25, 0.00, 0.26, 0.16),   # wide ellipse, bottom center
    'Maricopa': (0.62, 0.70, 0.32, 0.20),   # wide ellipse, right upper
    'Graham':   (0.68, 0.38, 0.22, 0.22),   # circle, right mid
    'Cochise':  (0.68, 0.04, 0.22, 0.22),   # circle, right lower
}
TOP_COUNTIES = ['Maricopa', 'Pinal', 'La Paz', 'Yuma', 'Cochise', 'Graham']
NORM_SPATIAL = PowerNorm(gamma=0.7, vmin=0, vmax=100)

# ── load + pool farm data ─────────────────────────────────────────────────
print("Loading farm shapefiles...")
year_gdfs = {}
for yr in range(2020, 2025):
    f = FV_DIR + f'/AZ_AT_ETFullTable_{yr}_5.shp'
    gdf = gpd.read_file(f)
    gdf['Gap_mm'] = (gdf['ETmm'] - gdf['ATmm']).clip(lower=0)
    gdf = gdf.to_crs(epsg=4326)
    year_gdfs[yr] = gdf
    print(f"  {yr}: {len(gdf):,} fields")

# Pooled: compute percentile rank within the pooled dataset
import pandas as pd
all_frames = pd.concat(
    [year_gdfs[yr][['CSBID','Gap_mm','geometry','CNTY']].assign(Year=yr)
     for yr in range(2020, 2025)],
    ignore_index=True
)
# Farm-average gap across years
farm_avg = (all_frames.groupby('CSBID')
            .agg(Gap_mm=('Gap_mm','mean'), CNTY=('CNTY','first'))
            .reset_index())
# Merge geometry from any year (use 2023 as reference)
geom_ref = year_gdfs[2023][['CSBID','geometry']].drop_duplicates('CSBID')
farm_avg = farm_avg.merge(geom_ref, on='CSBID', how='left')
farm_avg = gpd.GeoDataFrame(farm_avg, geometry='geometry', crs='EPSG:4326')
farm_avg = farm_avg[farm_avg.geometry.notna()]
farm_avg['Pct_rank'] = farm_avg['Gap_mm'].rank(pct=True) * 100

print(f"Pooled: {len(farm_avg):,} unique farms")

# ─────────────────────────────────────────────────────────────────────────
# Helper: find the densest zoom window within a county
# ─────────────────────────────────────────────────────────────────────────
def densest_window(centroids, bounds, bins=35, zoom_frac=0.22, aspect=1.0):
    """Return (xmin,xmax,ymin,ymax) centred on the densest bin, and its center.

    The window is sized as zoom_frac of the county extent, scaled by aspect
    so the zoom shape matches the inset shape.
    """
    xmin_b, ymin_b, xmax_b, ymax_b = bounds
    xs = centroids.x.values
    ys = centroids.y.values
    H, xe, ye = np.histogram2d(xs, ys, bins=bins,
                               range=[[xmin_b, xmax_b], [ymin_b, ymax_b]])
    idx = np.unravel_index(np.argmax(H), H.shape)
    cx = (xe[idx[0]] + xe[idx[0]+1]) / 2
    cy = (ye[idx[1]] + ye[idx[1]+1]) / 2
    # Scale window to match inset aspect ratio
    w = (xmax_b - xmin_b) * zoom_frac
    h = (ymax_b - ymin_b) * zoom_frac
    # For non-square insets, expand one dimension to match aspect
    if aspect > 1.0:
        w = max(w, h * aspect)
    elif aspect < 1.0:
        h = max(h, w / aspect)
    else:
        # Square/circle — use same span in both dimensions
        s = min(w, h)
        w = h = s
    span_x, span_y = w, h
    return (cx - span_x/2, cx + span_x/2, cy - span_y/2, cy + span_y/2), (cx, cy)


# ─────────────────────────────────────────────────────────────────────────
# Helper: statewide map with 6 circular zoomed insets (one per top county)
# ─────────────────────────────────────────────────────────────────────────
def make_spatial_fig(gdf, title_str, stem):
    """
    gdf must have 'Pct_rank' and 'CNTY' columns + polygon geometry in EPSG:4326.
    Produces elliptical zoomed insets for TOP_COUNTIES connected to main map.
    """
    fig = plt.figure(figsize=(16, 10), dpi=300, facecolor='white')
    fig.patch.set_facecolor('white')
    # Main statewide axis — centred, with wide margins for insets on all sides
    ax_main = fig.add_axes([0.24, 0.12, 0.36, 0.78])
    az.boundary.plot(ax=ax_main, color='#B0B0B0', linewidth=0.4)
    ax_main.set_axis_off()
    # No title — colorbar label carries the description

    # Plot all fields — visible polygon edges for definition
    gdf.plot(ax=ax_main, column='Pct_rank', cmap='viridis', norm=NORM_SPATIAL,
             linewidth=0.1, edgecolor='#666666', alpha=0.95, rasterized=True)

    for county in TOP_COUNTIES:
        if county not in INSET_POSITIONS:
            continue
        sub = gdf[gdf['CNTY'] == county]
        if len(sub) == 0:
            continue

        x0, y0, w, h = INSET_POSITIONS[county]
        aspect = w / h  # width/height ratio for zoom window

        centroids = sub.geometry.centroid
        bounds = sub.total_bounds
        (xmin, xmax, ymin, ymax), (cx, cy) = densest_window(
            centroids, bounds, bins=40, zoom_frac=0.18, aspect=aspect)

        # Circle on main map marking the zoomed area
        r_circ = min(xmax - xmin, ymax - ymin) / 2 * 0.35
        ax_main.add_patch(Circle((cx, cy), r_circ,
                                 edgecolor='#222222', facecolor='none',
                                 linewidth=0.7, zorder=5))

        # Inset panel
        inset = fig.add_axes([x0, y0, w, h])

        # Fields clipped to zoom window — visible polygon edges
        sub_zoom = sub.cx[xmin:xmax, ymin:ymax]
        if len(sub_zoom) == 0:
            sub_zoom = sub
        sub_zoom.plot(ax=inset, column='Pct_rank', cmap='viridis',
                      norm=NORM_SPATIAL, linewidth=0.15,
                      edgecolor='#555555', alpha=0.95)

        # Farm union boundary for definition
        outline = gpd.GeoSeries([sub_zoom.unary_union], crs=sub.crs)
        outline.boundary.plot(ax=inset, color='#444444', linewidth=0.5)

        inset.set_xlim(xmin, xmax)
        inset.set_ylim(ymin, ymax)
        inset.set_axis_off()

        # Elliptical clip path
        clip_el = Ellipse((0.5, 0.5), 1.0, 1.0, transform=inset.transAxes,
                          facecolor='none')
        inset.add_patch(clip_el)
        for coll in inset.collections:
            coll.set_clip_path(clip_el)
        # Visible ellipse border — dark, well-defined
        inset.add_patch(Ellipse((0.5, 0.5), 1.0, 1.0,
                                transform=inset.transAxes,
                                edgecolor='#222222', facecolor='none',
                                linewidth=0.9))

        # County label inside the inset
        inset.text(0.5, 0.93, county, transform=inset.transAxes,
                   fontsize=9, fontweight='bold', ha='center', va='top',
                   color='#333333',
                   path_effects=[pe.withStroke(linewidth=2.5,
                                               foreground='white')])

        # Leader line: inset center → zoom circle on main map
        con = ConnPatch(xyA=(0.5, 0.5), coordsA=inset.transAxes,
                        xyB=(cx, cy), coordsB=ax_main.transData,
                        color='#222222', linewidth=0.6, zorder=1)
        fig.add_artist(con)

    # Colorbar
    cax = fig.add_axes([0.95, 0.30, 0.012, 0.35])
    cb = fig.colorbar(
        plt.cm.ScalarMappable(norm=NORM_SPATIAL, cmap='viridis'), cax=cax)
    cb.set_label(title_str, fontsize=8, rotation=90, labelpad=8)
    cb.ax.tick_params(labelsize=7)

    savefig_both(fig, stem)
    plt.close()


# ══════════════════════════════════════════════════════════════════════════
# FIG 3 — Pooled spatial hotspot map (always regenerate with new inset design)
# ══════════════════════════════════════════════════════════════════════════
print("\nFig 3 (pooled spatial map)...")
make_spatial_fig(farm_avg, 'Attainable-ET gap percentile (pooled 2020\u20132024)',
                 'Fig3_spatial_hotspot_pooled')

# ══════════════════════════════════════════════════════════════════════════
# FigS1-FigS5 — Per-year spatial hotspot maps (always regenerate)
# ══════════════════════════════════════════════════════════════════════════
for i, yr in enumerate(range(2020, 2025), start=1):
    print(f"\nFigS{i} (spatial {yr})...")
    gdf_yr = year_gdfs[yr].copy()
    gdf_yr['Pct_rank'] = gdf_yr['Gap_mm'].rank(pct=True) * 100
    make_spatial_fig(gdf_yr, f'Attainable-ET gap percentile rank ({yr})',
                     f'FigS{i}_spatial_{yr}')

# ══════════════════════════════════════════════════════════════════════════
# FigS6–S15 — Per-year county + crop sensitivity scatter (3-panel each)
# ══════════════════════════════════════════════════════════════════════════
print("\nLoading sensitivity data...")
sens = pd.read_csv(SENS_CSV)

DEFAULT_SC = '5th percentile | cats: Average, Good'
PCT10_SC   = '10th percentile | cats: Average, Good'
GOOD_SC    = '5th percentile | cats: Good'

# County colors
CNTY_COLORS = {
    'Maricopa': '#e41a1c', 'Pinal':   '#377eb8',
    'La Paz':   '#4daf4a', 'Yuma':    '#984ea3',
    'Cochise':  '#ff7f00', 'Graham':  '#a65628',
}

def make_sensitivity_scatter(df_yr, yr, unit, groupcol, label_map, color_map, title, stem):
    """
    Two-panel sensitivity scatter: (a) 5th vs 10th pct, (b) G+A vs Good-only.
    Removes the 'All' panel since that data is unavailable.
    """
    def agg_scenario(sc):
        return (df_yr[df_yr.Scenario == sc]
                .groupby(groupcol)['Savings_acre_feet'].sum()
                .rename(sc))

    def_s   = agg_scenario(DEFAULT_SC)
    p10_s   = agg_scenario(PCT10_SC)
    good_s  = agg_scenario(GOOD_SC)
    all_cats = def_s.index.tolist()

    fig, axes = plt.subplots(1, 2, figsize=(10, 5))
    fig.suptitle(f'{title} ({yr})', fontsize=12, y=1.01)

    for ax, (alt_s, alt_label) in zip(axes, [
            (p10_s,   '10th pct (G+A)'),
            (good_s,  '5th pct (Good-only)'),
    ]):
        combined = pd.DataFrame({'default': def_s, 'alt': alt_s}).dropna()
        if combined.empty:
            ax.text(0.5, 0.5, 'No data', ha='center', va='center',
                    transform=ax.transAxes)
            continue

        vmin = min(combined.min().min(), 1)
        vmax = combined.max().max()

        # 1:1 line
        ax.plot([vmin, vmax], [vmin, vmax], 'k--', linewidth=0.8, zorder=1)

        for cat in combined.index:
            x, y = combined.loc[cat, 'default'], combined.loc[cat, 'alt']
            col  = color_map.get(cat, '#aaaaaa')
            ms   = 80 if cat in color_map else 30
            ax.scatter(x, y, c=col, s=ms, zorder=3,
                       edgecolors='white', linewidths=0.5)

        ax.set_xscale('log'); ax.set_yscale('log')
        ax.set_xlabel(f'5th pct (G+A)  [{unit}]', fontsize=9.5)
        ax.set_ylabel(f'{alt_label}  [{unit}]', fontsize=9.5)

        # Spearman rho
        from scipy.stats import spearmanr
        rho, _ = spearmanr(combined['default'], combined['alt'])
        ax.set_title(f'5th vs {alt_label}\n\u03c1={rho:.2f}', fontsize=10)

        ax.set_xlim(vmin*0.8, vmax*1.3)
        ax.set_ylim(vmin*0.8, vmax*1.3)
        ax.set_aspect('equal', adjustable='datalim')
        ax.grid(True, linewidth=0.4, color='#dddddd', which='major')

    # Shared legend for named categories
    handles = [mpatches.Patch(color=v, label=k) for k, v in color_map.items()
               if k in all_cats]
    if handles:
        fig.legend(handles=handles, loc='lower center',
                   ncol=min(len(handles), 4), fontsize=9,
                   bbox_to_anchor=(0.5, -0.08), framealpha=0.9)

    plt.tight_layout()
    savefig_both(fig, stem)
    plt.close()


fig_num = 6
for yr in range(2020, 2025):
    df_yr = sens[sens.Year == yr].copy()
    stem  = f'FigS{fig_num}_county_sensitivity_{yr}'
    print(f"\nFigS{fig_num} (county sensitivity {yr})...")
    make_sensitivity_scatter(
        df_yr, yr, 'acre-feet', 'CNTY',
        label_map=CNTY_COLORS, color_map=CNTY_COLORS,
        title='County-level sensitivity',
        stem=f'FigS{fig_num}_county_sensitivity_{yr}'
    )
    fig_num += 1

for yr in range(2020, 2025):
    df_yr_crop = sens[sens.Year == yr].copy()
    print(f"\nFigS{fig_num} (crop sensitivity {yr})...")

    # Build CSBID→Crop mapping from already-loaded year_gdfs (avoids re-read / dtype issues)
    csbid_crop = (year_gdfs[yr][['CSBID', 'CDL']]
                  .drop_duplicates('CSBID')
                  .copy())
    csbid_crop['Crop'] = csbid_crop['CDL'].map(CDL_MAP)
    # Align CSBID types: sens CSV is object, shapefile is int64
    df_yr_crop['CSBID'] = pd.to_numeric(df_yr_crop['CSBID'], errors='coerce').astype('Int64')
    csbid_crop['CSBID'] = csbid_crop['CSBID'].astype('Int64')
    df_yr_c = df_yr_crop.merge(csbid_crop[['CSBID', 'Crop']], on='CSBID', how='left')

    make_sensitivity_scatter(
        df_yr_c, yr, 'acre-feet', 'Crop',
        label_map=CROP_COLORS, color_map=CROP_COLORS,
        title='Crop-level sensitivity',
        stem=f'FigS{fig_num}_crop_sensitivity_{yr}'
    )
    fig_num += 1

print("\nAll supplementary figures done.")
print(f"PNG: {PNG_DIR}")
print(f"PDF: {PDF_DIR}")
