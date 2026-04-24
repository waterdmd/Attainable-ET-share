"""Build analysis output tables from the final pipeline run.

Data source: Implementation/Final_Vector/
  (cleaned CSB shapefile, no duplicate polygons, no double-crop fields, 800m rasters)

Outputs go to: Documentation/data/
  sensitivity/attainable_et_sensitivity_all.csv
  sensitivity/attainable_et_sensitivity_county.csv
  gap/field_et_cohort_2020_2024.csv   (2020-2024 only -- primary analysis window)
  gap/field_et_cohort_2019_2024.csv   (includes 2019 for reference)

Run with:
  python 01_build_analysis_outputs.py
"""

from pathlib import Path
import pandas as pd
import geopandas as gpd

CLEAN_DIR = Path(__file__).resolve().parent.parent        # → Documentation/
BASE      = CLEAN_DIR.parent                               # → Implementation/
OUT_SENS  = CLEAN_DIR / "data" / "sensitivity"
OUT_GAP   = CLEAN_DIR / "data" / "gap"
OUT_SENS.mkdir(parents=True, exist_ok=True)
OUT_GAP.mkdir(parents=True, exist_ok=True)
# Alias used by downstream save calls
OUT_DIR = OUT_SENS

YEARS = [2019, 2020, 2021, 2022, 2023, 2024]

TEMP_DIR = BASE / "GeoFiles" / "Temperature_800m" / "FarmWise"
PREC_DIR = BASE / "GeoFiles" / "Precipitation_800m" / "FarmWise"
YIELD_DIR = BASE / "GeoFiles" / "Farm_Yield"
FIELDS_DIR = BASE / "Final_Vector"

M2_PER_ACRE = 4046.8564224
AF_PER_M3 = 1.0 / 1233.48183754752

SCENARIOS = {
    "5th percentile | cats: Average, Good": {"q": 0.05, "cats": ["Good", "Average"]},
    "10th percentile | cats: Average, Good": {"q": 0.10, "cats": ["Good", "Average"]},
    "5th percentile | cats: All": {"q": 0.05, "cats": ["Good", "Average", "Bad"]},
    "5th percentile | cats: Good": {"q": 0.05, "cats": ["Good"]},
}

# Cohort key uses raw CDL code (not Crop name) to match the primary
# Final_Vector benchmarking pipeline in Generating_AttainableET_new.ipynb.
# This keeps each dual-crop CDL (226, 228, 230, 232, 233, 236) as its own
# cohort rather than lumping it with the pure-crop bucket, so Table S9's
# default-scenario totals reconcile exactly with Table S5 / Final_Vector.
COHORT_COLS = ["Year", "CDL", "TempC", "PrecC", "SoilClass"]


def load_year(year: int) -> pd.DataFrame:
    fv = FIELDS_DIR / f"AZ_AT_ETFullTable_{year}_5.shp"
    yld = YIELD_DIR / f"AZ_Yield_{year}.shp"
    temp = TEMP_DIR / f"Farm_Temperature_{year}.shp"
    prec = PREC_DIR / f"Farm_Precipitation_{year}.shp"

    if not (fv.exists() and yld.exists() and temp.exists() and prec.exists()):
        return pd.DataFrame()

    fv_df = gpd.read_file(fv, ignore_geometry=True)[
        ["CSBID", "CNTY", "CSBACRES", "ETmm", "SoilClass", "CDL"]]
    yld_df = gpd.read_file(yld, ignore_geometry=True)[["CSBID", "Crop", "Category"]]
    temp_df = gpd.read_file(temp, ignore_geometry=True)[["CSBID", f"TempC_{year}"]]
    prec_df = gpd.read_file(prec, ignore_geometry=True)[["CSBID", f"PrecC_{year}"]]

    for df in (fv_df, yld_df, temp_df, prec_df):
        df["CSBID"] = df["CSBID"].astype(str)

    df = fv_df.merge(yld_df, on="CSBID", how="inner")
    df = df.merge(temp_df, on="CSBID", how="inner")
    df = df.merge(prec_df, on="CSBID", how="inner")

    df["Category"] = df["Category"].astype(str).str.strip().str.title()
    df["Crop"] = df["Crop"].astype(str).str.strip().str.title()
    df["CNTY"] = df["CNTY"].astype(str).str.strip().str.title()
    df[f"TempC_{year}"] = df[f"TempC_{year}"].astype(str).str.strip().str.title()
    df[f"PrecC_{year}"] = df[f"PrecC_{year}"].astype(str).str.strip().str.title()

    df = df.rename(columns={f"TempC_{year}": "TempC", f"PrecC_{year}": "PrecC"})
    df["Year"] = year

    # drop missing cohort keys or ET
    df = df.dropna(subset=["CDL", "Crop", "TempC", "PrecC", "SoilClass",
                           "ETmm", "CSBACRES"])
    return df


def main():
    all_years = []
    for year in YEARS:
        df_year = load_year(year)
        if df_year.empty:
            continue
        all_years.append(df_year)

    if not all_years:
        raise RuntimeError("No input data found. Check Updated Implementation paths.")

    base_df = pd.concat(all_years, ignore_index=True)

    # cohort ET data for bootstrap (Good+Average only)
    cohort_df = base_df[base_df["Category"].isin(["Good", "Average"])].copy()
    cohort_df = cohort_df[["Year", "Crop", "TempC", "PrecC", "SoilClass", "ETmm"]].rename(columns={"ETmm": "et_mm"})
    cohort_df.to_csv(OUT_GAP / "field_et_cohort_2019_2024.csv", index=False)
    cohort_df[cohort_df["Year"].between(2020, 2024)].to_csv(
        OUT_GAP / "field_et_cohort_2020_2024.csv", index=False
    )

    outputs = []
    for sc_name, sc in SCENARIOS.items():
        q = sc["q"]
        cats = sc["cats"]

        df_sc = base_df[base_df["Category"].isin(cats)].copy()
        cohort_p = (
            df_sc.groupby(COHORT_COLS)["ETmm"]
            .quantile(q)
            .reset_index()
            .rename(columns={"ETmm": "ATmm"})
        )

        merged = base_df.merge(cohort_p, on=COHORT_COLS, how="left")
        merged = merged.dropna(subset=["ATmm"])
        merged["Savings_mm"] = (merged["ETmm"] - merged["ATmm"]).clip(lower=0)
        merged["Savings_acre_feet"] = (
            (merged["Savings_mm"] / 1000.0) * merged["CSBACRES"] * M2_PER_ACRE * AF_PER_M3
        )

        out = merged[["CSBID", "CNTY", "Year", "CSBACRES", "Savings_mm", "Savings_acre_feet", "ATmm"]].copy()
        out["Scenario"] = sc_name
        outputs.append(out)

    sens_all = pd.concat(outputs, ignore_index=True)
    sens_all.to_csv(OUT_DIR / "attainable_et_sensitivity_all.csv", index=False)

    # pooled county totals (2020-2024)
    county = sens_all[sens_all["Year"].between(2020, 2024)].groupby(["Scenario", "CNTY"], as_index=False).agg(
        Total_Acre_Feet=("Savings_acre_feet", "sum")
    )
    county.to_csv(OUT_DIR / "attainable_et_sensitivity_county.csv", index=False)

    print("Wrote", OUT_DIR / "attainable_et_sensitivity_all.csv")
    print("Wrote", OUT_DIR / "attainable_et_sensitivity_county.csv")
    print("Wrote", OUT_GAP / "field_et_cohort_2019_2024.csv")
    print("Wrote", OUT_GAP / "field_et_cohort_2020_2024.csv")


if __name__ == "__main__":
    main()

