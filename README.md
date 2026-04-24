# AT_ET — Peer-based Attainable Evapotranspiration Benchmarking for Arizona

Reproducible code + data repo accompanying:

> Bokati, L., Shah, N., and Kumar, S. *A Peer-Conditioned Attainable
> Evapotranspiration Framework for Diagnosing Field-Scale Water-Use
> Efficiency.*

The pipeline quantifies **field-scale attainable-ET (AtET) gaps** across
Arizona irrigated agriculture (2020–2024) by benchmarking each field's actual
ET against the 5th-percentile ET among yield-similar peers in the same
climate/soil context.

---

## What's in this repo (~405 MB)

The repo ships the **code**, the **small ground-truth CSVs**, the **cleaned
boundaries**, and the **authoritative `Final_Vector/` output**. With these
alone you can **reproduce every table and figure in the paper locally**,
without downloading any external rasters. Raw raster inputs and the full
NDVI long table are kept out of the repo because they are multi-GB external
products — download scripts and a reproduction path are provided below.

```
Implementation/                          ← repo root (run everything from here)
├── README.md                            ← this file
│
├── CSB_Shape_file_processing.py         ← clean CSB polygons (drop invalid/<1 m²/dup)
├── Corrected_Yield_Modeling_batch.py    ← softplus yield model (all 5 crops, LOCYO CV)
├── download_monthly_30m.ipynb           ← Sentinel-2 monthly NDVI GeoTIFFs via GEE+XEE (needs GCP, ~144 GB output)
├── ExtractNDVI.ipynb                    ← Sentinel-2 NDVI → field-level long table (SOL/GEE)
├── NDVI_EXT.ipynb                       ← reshape NDVI long table → NDVI_ALL.csv + per-crop
├── Preprocessing_County_GrdTruth.ipynb  ← USDA NASS raw → county yield CSVs
├── Farm_Wise_ET.ipynb                   ← zonal ET per field
├── Farm_Wise_Temperature.ipynb          ← zonal temp + climate class
├── Farm_Wise_Precipitation.ipynb        ← zonal precip + climate class
├── Farm_Wise_SoilTaxonomy.ipynb         ← dominant soil order per field
├── Farm_Wise_Yield.ipynb                ← merge yield predictions onto CSB
├── Soil_Fixing_code.ipynb               ← SSURGO raster preprocessing
├── Generating_AttainableET_new.ipynb    ← MAIN integration → Final_Vector/
│
├── Data/                                ← 19 CSVs, ~48 MB
│   ├── Raw_[CROP].csv                       USDA NASS raw exports (5 files)
│   ├── YIELD_[CROP].csv                     cleaned county-year yields (5 files)
│   ├── [CROP]_Yield_Predictions_new.csv     softplus model outputs (5 files, ~50 MB)
│   ├── CDL_mapping_csv.csv                  CDL code → crop name
│   ├── Corn_Yield_Overall.csv               corn bu/ac ↔ lb/ac conversion
│   ├── Corn_Yield_Subcategories.csv         corn sub-types for conversion
│   └── LOYO_raw_results.csv                 cached LOCYO fold results
│
├── GeoFiles/
│   ├── CSB/                                 ~115 MB
│   │   ├── CSB_AZ.shp + .dbf/.prj/.shx/.cpg     raw USDA CSB polygons (57,080)
│   │   └── CSB_AZ_cleaned.shp + siblings        cleaned (57,063 unique CSBIDs)
│   ├── Soil/
│   │   └── LU_soil.xlsx                         soil-taxonomy-code → soil-order lookup (needed by Soil_Fixing_code.ipynb)
│   └── AZ_Boundary/                         state + county polygons
│
├── Final_Vector/                        ← AUTHORITATIVE OUTPUT, 134 MB
│   ├── AZ_AT_ETFullTable_2020_5.shp + siblings
│   ├── AZ_AT_ETFullTable_2021_5.shp + siblings
│   ├── AZ_AT_ETFullTable_2022_5.shp + siblings
│   ├── AZ_AT_ETFullTable_2023_5.shp + siblings
│   └── AZ_AT_ETFullTable_2024_5.shp + siblings
│
├── AMA_per_boundary/                    ← 7 AMA boundary shapefiles
├── Download_Scripts/                    ← GEE JavaScript for raster downloads
│   ├── openET.js
│   ├── precip.js
│   ├── temp.js
│   └── soil_tax.js
│
└── Documentation/                       ← paper-specific analysis layer
    ├── scripts/                             11 Python scripts that build tables and figures
    └── data/                                derived CSVs used by paper tables
        ├── tables/                              Table 1, S1, S2, S5, S6, S7 sources (9 CSVs)
        ├── gap/                                 pooled / by-year / by-crop gap summaries (17 CSVs)
        ├── ama/                                 per-AMA aggregations (12 CSVs)
        ├── cohort/                              cohort-size + bootstrap CI summaries (10 CSVs)
        └── sensitivity/                         sensitivity scenario summaries (5 CSVs)
```

---

## What's NOT in this repo — how to regenerate each

The repo intentionally **excludes** large raw data and derived intermediates
that can be reproduced. Each exclusion is listed here with the **script that
regenerates it** and the **path where it will appear**.

### Source rasters (download from external services; GB-scale)

| What's missing | Size | Script | Output directory (creates if absent) |
|---|---|---|---|
| OpenET ENSEMBLE annual ET rasters | ~5 GB | `Download_Scripts/openET.js` (run in GEE Code Editor; downloads to Google Drive; move to repo) | `GeoFiles/ET/Reprojected/Reprojected_ET_{YYYY}.tif` |
| PRISM 800 m annual mean temperature (paper's authoritative input) | ~1 GB | Direct download from https://prism.oregonstate.edu/ (`us_30s` = 30 arcsec ≈ 800 m, annual or monthly BIL). **Not** downloadable at 800 m via GEE — the GEE convenience script `Download_Scripts/temp.js` exports the 4 km `OREGONSTATE/PRISM/AN81m` asset instead, which is a **coarser** alternative, not the paper's input | `GeoFiles/Temperature_800m/Reprojected/prism_tmean_us_30s_{YYYY}.tif` |
| PRISM 800 m annual total precipitation (paper's authoritative input) | ~1 GB | Direct download from https://prism.oregonstate.edu/ (`us_30s` ≈ 800 m). GEE convenience script `Download_Scripts/precip.js` exports the 4 km `OREGONSTATE/PRISM/AN81m` product — a coarser alternative, not the paper's input | `GeoFiles/Precipitation_800m/Reprojected/prism_ppt_us_30s_{YYYY}.tif` |
| OpenLandMap USDA Soil Taxonomy Great Group raster (v01, 250 m) | ~500 MB | `Download_Scripts/soil_tax.js` exports `OpenLandMap/SOL/SOL_GRTGROUP_USDA-SOILTAX_C/v01` as `AZ_Soil_OpenLandMap_Great_Group.tif` → reproject to EPSG:5070 and rename to `Reprojected_Soil_Taxonomy.tif`, then pre-process with `Soil_Fixing_code.ipynb` (reads `GeoFiles/Soil/LU_soil.xlsx`, shipped) | `GeoFiles/Soil/AZ_Soil_Taxonomy_Preprocessed.tif` |
| Sentinel-2 monthly NDVI GeoTIFFs (30 m, 2019–2024) | ~144 GB | `download_monthly_30m.ipynb` (GEE+XEE; requires a Google Cloud project with Earth Engine API enabled, `gee_xarray_env` conda env, and an output directory with ≥144 GB free — user must edit `gcloud_project_id` and `OUTPUT_DIR` before running) | `{OUTPUT_DIR}/Arizona_NDVI_median_Sentinel2_{YYYY}_{MM}.tif` |
| Sentinel-2 NDVI → field-level long table | — | `ExtractNDVI.ipynb` (consumes the NDVI rasters above; GEE / SOL cluster — not runnable locally) | writes `Data/AT_ET_farm_data.csv` |

> **PRISM resolution caveat.** The paper's temperature and precipitation
> analysis uses PRISM's **800 m** (`_us_30s`) product downloaded directly
> from prism.oregonstate.edu. PRISM's 800 m asset is not exposed on
> Google Earth Engine — the `OREGONSTATE/PRISM/AN81m` asset is the 4 km
> monthly product. The included `temp.js` / `precip.js` export that 4 km
> asset as a convenience (same source, coarser resolution). To match the
> paper exactly, download the 800 m BIL files from PRISM directly.

### Raw NDVI long table + derivatives (regenerable after NDVI rasters)

| What's missing | Size | Script | Output path |
|---|---|---|---|
| `Data/AT_ET_farm_data.csv` (raw NDVI per field per month) | ~4 GB | `ExtractNDVI.ipynb` (GEE-side) | `Data/AT_ET_farm_data.csv` |
| `Data/NDVI_ALL.csv` (consolidated long table) | ~330 MB | `NDVI_EXT.ipynb` | `Data/NDVI_ALL.csv` |
| `Data/NDVI_[CROP].csv` (per-crop subsets, 5 files) | ~40 MB total | `NDVI_EXT.ipynb` | `Data/NDVI_[CROP].csv` |

### Field-level zonal products (FarmWise shapefiles) — regenerable from rasters + CSB

| What's missing | Script | Output path |
|---|---|---|
| `Farm_ETmm_{YYYY}.shp` (yearly) | `Farm_Wise_ET.ipynb` | `GeoFiles/ET/FarmWise/Farm_ETmm_{YYYY}.shp` |
| `Farm_Temperature_{YYYY}.shp` | `Farm_Wise_Temperature.ipynb` | `GeoFiles/Temperature_800m/FarmWise/Farm_Temperature_{YYYY}.shp` |
| `Farm_Precipitation_{YYYY}.shp` | `Farm_Wise_Precipitation.ipynb` | `GeoFiles/Precipitation_800m/FarmWise/Farm_Precipitation_{YYYY}.shp` |
| `Farm_SoilTaxonomy_clean.shp` (static) | `Farm_Wise_SoilTaxonomy.ipynb` | `GeoFiles/Soil/FarmWise/Farm_SoilTaxonomy_clean.shp` |
| `AZ_Yield_{YYYY}.shp` (CDL + yield category) | `Farm_Wise_Yield.ipynb` | `GeoFiles/Farm_Yield/AZ_Yield_{YYYY}.shp` |

### Final_Vector itself — already shipped, but regenerable if you want to verify

| What's missing | Script | Output path |
|---|---|---|
| `AZ_AT_ETFullTable_{YYYY}_5.shp` (5 years) — **already present** in `Final_Vector/` | `Generating_AttainableET_new.ipynb` (re-runs from FarmWise shapefiles + AZ_Yield) | `Final_Vector/AZ_AT_ETFullTable_{YYYY}_5.shp` |

### Paper tables / figures — **not shipped**, regenerate from `Final_Vector/`

None of the `Documentation/figures/` PNG/PDF files or the manuscript itself is
in the repo. Every table and figure can be regenerated from the shipped
`Final_Vector/` by running scripts under `Documentation/scripts/`:

| Paper artifact | Script (run from any location) | Output path |
|---|---|---|
| Main-text Fig 1, 2a, 2b, 4, 5 + supplementary S6, S7, S8 | `Documentation/scripts/02_generate_figures.py` | `Documentation/figures/png/{Fig1,Fig2a,Fig2b,Fig4,Fig5,FigS6,FigS7,FigS8}_*.png` (+ pdf) |
| Main-text Fig 6a, 6b (sensitivity scatters) | `Documentation/scripts/generate_fig6_sensitivity.py` | `Documentation/figures/png/Fig6a_sensitivity_county.png`, `Fig6b_sensitivity_crop.png` (+ pdf) |
| Main-text Fig 3 + supplementary S1–S5 (spatial maps) | `Documentation/scripts/03_generate_supplementary_figures.py` | `Documentation/figures/png/Fig3_spatial_*.png`, `FigS1_spatial_2020.png` … `FigS5_spatial_2024.png` (+ pdf) |
| Supplementary Figs S1–S18 | `Documentation/scripts/03_generate_supplementary_figures.py` | `Documentation/figures/png/FigS*.png` |
| Table S5 / S6 / S7 source CSVs | `Documentation/scripts/build_table_s5_crop_contrasts.py`, `build_table_s6_s7_ama.py` | `Documentation/data/tables/Table_S*.csv` |
| Table S2 (peer cohort summary) | `Documentation/scripts/build_table_s2_cohort_summary.py` | `Documentation/data/tables/Table_S2*.csv` |
| Table S9 (sensitivity) | `Documentation/scripts/01_build_analysis_outputs.py` + `regenerate_stale_csvs.py` | `Documentation/data/sensitivity/sensitivity_by_year_*.csv` |
| All cohort reliability + bootstrap CI | `Documentation/scripts/regenerate_cohort_csvs.py` | `Documentation/data/cohort/*.csv` |

### Intermediate CSVs — shipped where small, regenerable when large

| File | Status | Created by | Needed by |
|---|---|---|---|
| `Documentation/data/gap/gap_mm_all_fields_2020_2024.csv` (7 MB) | ✅ **shipped** | `01_build_gap_csvs_from_fv.py` | figure and table scripts |
| `Documentation/data/gap/gap_mm_pos_all_fields_2020_2024.csv` (7 MB) | ✅ **shipped** | `01_build_gap_csvs_from_fv.py` | figure and table scripts |
| `Documentation/data/gap/field_et_cohort_{2019,2020}_2024.csv` (5 MB each) | ✅ **shipped** | `01_build_analysis_outputs.py` | `regenerate_cohort_csvs.py`, bootstrap |
| `Documentation/data/cohort/cohort_reliability_field_year.csv` (7 MB) | ✅ **shipped** | `regenerate_cohort_csvs.py` | `build_table_s2_cohort_summary.py` |
| `Documentation/data/sensitivity/attainable_et_sensitivity_all.csv` (75 MB) | ✅ **shipped** | `01_build_analysis_outputs.py` | `generate_fig6_sensitivity.py`, `regenerate_stale_csvs.py` |

Only the large field-level sensitivity file is excluded. To produce it, run
`python Documentation/scripts/01_build_analysis_outputs.py` first — it reads
the shipped `Final_Vector/` + FarmWise shapefiles. Note that this requires
the FarmWise shapefiles (not shipped); use the scripts that read only from
`Final_Vector/` (e.g., `01_build_gap_csvs_from_fv.py`,
`regenerate_stale_csvs.py`, `regenerate_cohort_csvs.py`) if you don't want
to download rasters.

---

## Pipeline workflow and dependencies

The diagram below shows what produces what. Non-obvious but strict
dependencies worth calling out:

- **`NDVI_EXT.ipynb` must run before `Corrected_Yield_Modeling_batch.py`** —
  the yield model reads `Data/NDVI_ALL.csv` at script start.
- **`CSB_Shape_file_processing.py` must run before all `Farm_Wise_*` notebooks** —
  they all zonally extract onto `CSB_AZ_cleaned.shp`.
- **`Corrected_Yield_Modeling_batch.py` must run before `Farm_Wise_Yield.ipynb`** —
  `AZ_Yield_{YYYY}.shp` carries the Good/Average/Bad category derived from
  `[CROP]_Yield_Predictions_new.csv`.
- **All five `Farm_Wise_*` outputs must exist before `Generating_AttainableET_new.ipynb`** —
  it integrates FarmWise ET, Temperature, Precipitation, SoilTaxonomy, and Yield.

```
Phase 1 — Sentinel-2 NDVI chain (GEE, ~144 GB, not runnable locally)
────────────────────────────────────────────────────────────────────
  COPERNICUS/S2_SR_HARMONIZED
      │ download_monthly_30m.ipynb   (needs GCP project + gee_xarray_env conda env)
      ▼
  Arizona_NDVI_median_Sentinel2_{YYYY}_{MM}.tif   (monthly 30 m GeoTIFFs)
      │ ExtractNDVI.ipynb            (also reads CSB_AZ_cleaned.shp from Phase 3)
      ▼
  Data/AT_ET_farm_data.csv           (raw field-level NDVI long table, ~4 GB)
      │ NDVI_EXT.ipynb
      ▼
  Data/NDVI_ALL.csv  +  Data/NDVI_[CROP].csv × 5


Phase 2 — County yields + softplus yield model (local)
──────────────────────────────────────────────────────
  USDA NASS Quick Stats                 Data/NDVI_ALL.csv
           │                                     │    (from Phase 1)
  Data/Raw_[CROP].csv                            │
           │ Preprocessing_County_GrdTruth.ipynb │
           ▼                                     │
  Data/YIELD_[CROP].csv  ──────────┐             │
                                   ▼             ▼
                    Corrected_Yield_Modeling_batch.py  (softplus, Adam, LOCYO CV)
                                   │
                                   ▼
  Data/[CROP]_Yield_Predictions_new.csv × 5  +  Data/LOYO_raw_results.csv


Phase 3 — CSB cleaning + zonal extractions (mostly parallelizable)
──────────────────────────────────────────────────────────────────
  GeoFiles/CSB/CSB_AZ.shp
      │ CSB_Shape_file_processing.py
      ▼
  GeoFiles/CSB/CSB_AZ_cleaned.shp
      │
      ├── OpenET rasters       →  Farm_Wise_ET.ipynb            →  Farm_ETmm_{YYYY}.shp
      ├── PRISM 800 m temp     →  Farm_Wise_Temperature.ipynb   →  Farm_Temperature_{YYYY}.shp
      ├── PRISM 800 m precip   →  Farm_Wise_Precipitation.ipynb →  Farm_Precipitation_{YYYY}.shp
      ├── OpenLandMap USDA-SOILTAX Great Group raster           (preprocess once: Soil_Fixing_code.ipynb + LU_soil.xlsx)
      │       │
      │       ▼
      │   Farm_Wise_SoilTaxonomy.ipynb  →  Farm_SoilTaxonomy_clean.shp
      │
      └── [CROP]_Yield_Predictions_new  →  Farm_Wise_Yield.ipynb  →  AZ_Yield_{YYYY}.shp
                (from Phase 2)


Phase 4 — Integration → authoritative output  ✱ SHIPPED ✱
──────────────────────────────────────────────────────────
  All Farm_* shapefiles from Phase 3
      │ Generating_AttainableET_new.ipynb
      ▼
  Final_Vector/AZ_AT_ETFullTable_{YYYY}_5.shp    (5 files, 2020–2024)


Phase 5 — Paper tables and figures (needs only Final_Vector/)
─────────────────────────────────────────────────────────────
  Final_Vector/
      │ Documentation/scripts/{01_build_gap_csvs_from_fv,
      │                        build_table_s2_cohort_summary,
      │                        build_table_s5_crop_contrasts,
      │                        build_table_s6_s7_ama,
      │                        regenerate_stale_csvs,
      │                        02_generate_figures,
      │                        03_generate_supplementary_figures,
      │                        generate_fig6_sensitivity}.py
      ▼
  Documentation/data/*.csv  +  Documentation/figures/{png,pdf}/*
```

---

## Reproducing the paper — three entry points

### A. Reproduce paper tables and figures from the shipped `Final_Vector/`

No external downloads. Regenerates every paper table CSV and figure from the
shipped authoritative output and the shipped intermediate CSVs:

```bash
# from repo root
python Documentation/scripts/01_build_gap_csvs_from_fv.py
python Documentation/scripts/regenerate_stale_csvs.py
python Documentation/scripts/build_table_s2_cohort_summary.py
python Documentation/scripts/build_table_s5_crop_contrasts.py
python Documentation/scripts/build_table_s6_s7_ama.py
python Documentation/scripts/02_generate_figures.py
python Documentation/scripts/03_generate_supplementary_figures.py
python Documentation/scripts/generate_fig6_sensitivity.py
```

No raster downloads, no GEE, no SOL cluster access required.

**Note:** `01_build_analysis_outputs.py`, `regenerate_cohort_csvs.py`, and
`00_build_loyo_table.py` are *not* in the Option A list — they re-derive
intermediate products that are already shipped (`attainable_et_sensitivity_all.csv`,
`cohort_reliability_field_year.csv`, LOCYO results). They require raster /
NDVI inputs (not shipped) to run. Use Option B or C below if you need to
regenerate those intermediates yourself.

### B. Regenerate `Final_Vector/` from source

To rebuild the authoritative output from raster sources:

1. Download rasters via `Download_Scripts/*.js` (run in Google Earth Engine)
2. Move the downloads into the expected paths listed above
3. Run notebooks in order:
   - `Soil_Fixing_code.ipynb` (once, for SSURGO preprocessing)
   - `Farm_Wise_Temperature.ipynb`, `Farm_Wise_Precipitation.ipynb`,
     `Farm_Wise_ET.ipynb`, `Farm_Wise_SoilTaxonomy.ipynb` (parallelizable)
   - `Preprocessing_County_GrdTruth.ipynb` → `Data/YIELD_[CROP].csv` (not
     needed if you use the shipped ones)
   - `Corrected_Yield_Modeling_batch.py` → `Data/[CROP]_Yield_Predictions_new.csv`
     (requires `Data/NDVI_ALL.csv` — see option C for that)
   - `Farm_Wise_Yield.ipynb` → `GeoFiles/Farm_Yield/AZ_Yield_{YYYY}.shp`
   - `Generating_AttainableET_new.ipynb` → `Final_Vector/AZ_AT_ETFullTable_{YYYY}_5.shp`

### C. Full fresh pipeline including NDVI generation

Requires a Google Cloud project with Earth Engine API enabled, the
`gee_xarray_env` conda environment, and an output directory with ≥144 GB
free. Adds two steps at the start of option B:

0. Edit `download_monthly_30m.ipynb` to set `gcloud_project_id` and
   `OUTPUT_DIR`, then run on a machine (SOL cluster or similar) to produce
   monthly Sentinel-2 NDVI GeoTIFFs (`Arizona_NDVI_median_Sentinel2_{YYYY}_{MM}.tif`).
   Expect ~144 GB and many hours; the notebook logs successes to
   `download_log.jsonl` and resumes from the log on re-runs.
0a. Run `ExtractNDVI.ipynb` on GEE/SOL (pointing at the GeoTIFFs from step 0)
    to generate `Data/AT_ET_farm_data.csv`.
0b. Run `NDVI_EXT.ipynb` locally to reshape into `Data/NDVI_ALL.csv` +
    `Data/NDVI_[CROP].csv`.

Then continue with option B.

---

## System requirements

- **Python:** 3.10 tested; should work on 3.9–3.12.
- **Key libraries:** `geopandas`, `pandas`, `numpy`, `rasterio`, `shapely ≥ 2.0`,
  `scikit-learn`, `matplotlib`, `python-docx`, `pyarrow`
- **Disk space:** ~500 MB for repo + shipped data; +~10 GB if downloading
  rasters for full pipeline rebuild.
- **Memory:** 8 GB adequate; 16 GB preferred when running Sentinel-2 NDVI
  extraction and yield model training.
- **External accounts:** Google Earth Engine (free for non-commercial use) —
  required only for raster downloads / NDVI extraction.

Install environment:

```bash
conda create -n at_et python=3.10
conda activate at_et
conda install -c conda-forge geopandas rasterio shapely pyproj
pip install scikit-learn matplotlib python-docx pyarrow
```

---

## Model and method parameters

### Softplus yield regression (`Corrected_Yield_Modeling_batch.py`)

| Parameter | Value |
|---|---|
| Activation | softplus = log1p(exp(clip(z, −20, 20))) |
| Optimizer | Adam (β₁ = 0.9, β₂ = 0.999, ε = 1×10⁻⁸) |
| Learning rate | 0.02 |
| L2 regularization (λ) | 1×10⁻³ |
| Gradient clipping (max norm) | 100.0 |
| Epochs | 10,000 |
| Loss | Area-weighted county MSE between predicted field yield and county mean |
| Features | Monthly NDVI standardized (mean = 0, std = 1) |

### NDVI seasonal windows

| Crop | Prior-year months (Y−1) | Current-year months (Y) |
|---|---|---|
| Alfalfa | Sep–Dec | Jan–Aug |
| Wheat | Dec | Jan–Jun |
| Barley | Nov, Dec | Jan–Jun |
| Cotton | — | Apr–Sep |
| Corn | — | Jun–Aug |

### Yield classification (RYI thresholds)

When USDA Quick Stats county yield is available:

| Category | RYI threshold | Meaning |
|---|---|---|
| Good | RYI ≥ 1.00 | Field predicted yield ≥ county mean |
| Average | 0.85 ≤ RYI < 1.00 | Within 15% below county mean |
| Bad | RYI < 0.85 | More than 15% below county mean |

where `RYI = predicted_field_yield / county_mean_yield`. Fallback for counties
without Quick Stats data: Q25/Q75 quantiles of predicted yield within that
county-year.

### Climate binning

**Temperature** (PRISM annual mean, °C):
Very Low ≤ 17.5 · Low 17.5–19.5 · Medium 19.5–21.5 · High 21.5–22.5 · Very High > 22.5

**Precipitation** (PRISM annual total, mm):
Very Low ≤ 250 · Low 250–275 · Medium 275–300 · High 300–350 · Very High > 350

### Peer cohort definition

Cohort = unique combination of:

- **CDL** (USDA Cropland Data Layer code). Thirteen CDL levels appear in the
  Arizona data across the five target crops: Alfalfa (36); Cotton (2, 232);
  Corn (1, 226, 228); Wheat (22, 23, 24, 230, 236); Barley (21, 233). Dual-crop
  codes are kept as distinct peer groups so fields whose annual ET integrates
  over two crops are benchmarked only against fields with the same rotation.
- **TempC** — temperature class (5 levels)
- **PrecC** — precipitation class (5 levels)
- **SoilClass** — USDA soil order (up to 12 values; aggregated from OpenLandMap USDA-SOILTAX Great Group)

Max possible cohorts = 13 × 5 × 5 × 12 = 3,900. Populated year-cohorts in the
AZ data (2020–2024) = 1,110.

### Attainable-ET benchmark

For each cohort-year:

1. Restrict peer pool to fields with Category ∈ {Good, Average}
2. Benchmark = **5th percentile** of ET (mm) within peer pool
3. Field gap = max(0, ETmm − benchmark)
4. Volume (m³) = gap_mm × area_m² / 1000; convert to acre-feet via 1 AF = 1,233.48 m³

### Sensitivity scenarios

| Scenario | Percentile | Peer group |
|---|---|---|
| Default | 5th | Good + Average |
| Alt-percentile | 10th | Good + Average |
| Good-only | 5th | Good only |
| All-fields | 5th | Good + Average + Bad |

---

## Final_Vector column schema

One file per year: `Final_Vector/AZ_AT_ETFullTable_{YYYY}_5.shp`

| Column | Meaning | Units |
|---|---|---|
| `CSBID` | USDA CSB field ID | string |
| `CNTY` | County name | string |
| `CSBACRES` | Field area | acres |
| `ETmm` | Actual annual ET (OpenET ensemble) | mm |
| `ATmm` | Attainable-ET benchmark (5th pct of Good+Average peers in cohort) | mm |
| `CDL` | USDA CDL crop code | integer |
| `Category` | Yield-performance class | Good / Average / Bad |
| `SoilClass` | USDA soil order (aggregated from OpenLandMap Great Group) | integer 1–12 |
| `PredYld_ar` | Predicted yield per acre | crop-specific units |
| `ETVol` | ET volume = ETmm × area_m² / 1000 | m³ |
| `ATVol` | Attainable ET volume | m³ |
| `VolD` | Gap volume = ETVol − ATVol | m³ |
| `BT` | True if ETmm < ATmm | bool |
| `Year` | Calendar year | integer |
| `geometry` | Field polygon | shapefile geom |

---

## Data sources

| Layer | Source | Native resolution |
|---|---|---|
| ET | Google Earth Engine: `OpenET/ENSEMBLE/CONUS/GRIDMET/MONTHLY/v2_0` | 30 m monthly |
| Temperature | PRISM Climate Group, `prism_tmean_us_30s` | ~800 m annual |
| Precipitation | PRISM Climate Group, `prism_ppt_us_30s` | ~800 m annual |
| Soil | OpenLandMap USDA Soil Taxonomy Great Group (`OpenLandMap/SOL/SOL_GRTGROUP_USDA-SOILTAX_C/v01`, 250 m); aggregated to 12 USDA soil orders via suffix mapping in `Soil_Fixing_code.ipynb` (lookup: `GeoFiles/Soil/LU_soil.xlsx`) | raster |
| NDVI | Sentinel-2 Level-2A via Google Earth Engine | 10 m monthly |
| Farm boundaries | USDA Crop Sequence Boundaries (CSB), 2017–2024 | polygon |
| County yields | USDA NASS Quick Stats | county-year |
| Crop type | USDA Cropland Data Layer (CDL) | 30 m annual |
| AMA boundaries | Arizona Department of Water Resources | polygon |

---

## Troubleshooting

**CSB cleaning produces 57,063 polygons, not 57,080.**
Expected. The raw `CSB_AZ.shp` contains 57,080 polygons, 17 of which have
invalid geometry or area < 1 m². `CSB_Shape_file_processing.py` drops those.

**`Generating_AttainableET_new.ipynb` drops some fields with NaN `ATmm`.**
Occurs when a cohort has zero Good+Average peers (typically tiny dual-crop
cohorts in unusual soil/climate combinations). 10–97 fields per year, <0.3% of
total. These fields are excluded from the output because no benchmark can be
computed.

**`01_build_analysis_outputs.py` fails saying a FarmWise shapefile is missing.**
This script re-derives scenario benchmarks from the FarmWise shapefiles, which
are NOT shipped. Either (a) run the `Farm_Wise_*.ipynb` notebooks first to
create them, or (b) use only the scripts that read from `Final_Vector/` (most
of `Documentation/scripts/` does exactly that).

**Case sensitivity (Linux).**
All paths in scripts and notebooks use `GeoFiles/` (not `Geofiles`) and
`CSB_AZ_cleaned.shp` (not `CSB_AZ_Cleaned.shp`). If you clone the repo on
Linux and an import fails with a "file not found," check that your local
filesystem matches this case convention.

---

## Citing

If you use this code or data, please cite:

```
Bokati, L., Shah, N., and Kumar, S. A Peer-Conditioned Attainable
Evapotranspiration Framework for Diagnosing Field-Scale Water-Use
Efficiency.
```

And attribute the external data sources (OpenET, PRISM, OpenLandMap
USDA-SOILTAX, USDA NASS, USDA CSB/CDL, Sentinel-2 via Copernicus, ADWR)
as appropriate.

---

## License

Code: MIT License (see `LICENSE`).
Derived data files in `Data/`, `Final_Vector/`, `Documentation/data/`: CC-BY 4.0.
External data sources retain their original licenses.

---

## Contact

Laxman Bokati — <lbokati@asu.edu>
Saurav Kumar (corresponding) — <sk2@asu.edu>
School of Sustainable Engineering and Built Environment, Arizona State University
