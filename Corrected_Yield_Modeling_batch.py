"""
Corrected_Yield_Modeling_batch.py
==================================
Batch version of Corrected_Yield_Modeling.ipynb.

Produces identical outputs to running the notebook manually 5 times
(once per crop), but in a single unattended run.

Outputs (same as notebook):
  Data/Alfalfa_Yield_Predictions_new.csv
  Data/Wheat_Yield_Predictions_new.csv
  Data/Cotton_Yield_Predictions_new.csv
  Data/Barley_Yield_Predictions_new.csv
  Data/Corn_Yield_Predictions_new.csv

  Data/LOYO_raw_results.csv
      Per-(crop, county, year) MAE rows from leave-one-county-year-out CV.
      Used by Documentation/scripts/00_build_loyo_table.py

Run from the Implementation directory:
  cd <path-to-Implementation>
  python Corrected_Yield_Modeling_batch.py

Flags:
  --skip-loyo   Skip cross-validation (faster; no LOYO_raw_results.csv)
"""

import os
import sys
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
SKIP_LOYO = "--skip-loyo" in sys.argv
LOYO_RAW_OUT = "Data/LOYO_raw_results.csv"

# ── Crop configurations ────────────────────────────────────────────────────
CROP_CONFIGS = [
    {
        "crop":   "alfalfa",
        "cdl":    {36},
        "truth":  "Data/YIELD_ALFALFA.csv",
        "out":    "Data/Alfalfa_Yield_Predictions_new.csv",
    },
    {
        "crop":   "wheat",
        "cdl":    {238, 22, 24, 23, 236, 225, 230},
        "truth":  "Data/YIELD_WHEAT.csv",
        "out":    "Data/Wheat_Yield_Predictions_new.csv",
    },
    {
        "crop":   "cotton",
        "cdl":    {2, 238, 232},
        "truth":  "Data/YIELD_COTTON.csv",
        "out":    "Data/Cotton_Yield_Predictions_new.csv",
    },
    {
        "crop":   "barley",
        "cdl":    {21, 233, 235, 237, 254},
        "truth":  "Data/YIELD_BARLEY.csv",
        "out":    "Data/Barley_Yield_Predictions_new.csv",
    },
    {
        "crop":   "corn",
        "cdl":    {228, 1, 225, 226, 237},
        "truth":  "Data/YIELD_CORN.csv",
        "out":    "Data/Corn_Yield_Predictions_new.csv",
    },
]

# Crop → NDVI month windows (AZ growing seasons)
CROP_WINDOWS = {
    "wheat":   {"prev": [12],          "curr": [1, 2, 3, 4, 5, 6]},
    "barley":  {"prev": [11, 12],      "curr": [1, 2, 3, 4, 5, 6]},
    "alfalfa": {"prev": [9, 10, 11, 12], "curr": [1, 2, 3, 4, 5, 6, 7, 8]},
    "cotton":  {"prev": [],            "curr": [4, 5, 6, 7, 8, 9]},
    "corn":    {"prev": [],            "curr": [6, 7, 8]},
}

# Adam training hyperparameters (match notebook)
EPOCHS = 10000
LR = 0.02
L2 = 1e-3
MAX_GRAD_NORM = 100.0

# Categorization thresholds (match Cell 23)
RYI_BAD = 0.85
RYI_GOOD = 1.00
Q_BAD = 0.25
Q_GOOD = 0.75
USE_MAD = False
K_MAD = 0.0
MIN_N = 25


# ══════════════════════════════════════════════════════════════════════════
# Helper functions (from notebook cells 1, 14, 20, 21)
# ══════════════════════════════════════════════════════════════════════════

def build_calendar_wide(ndvi_long: pd.DataFrame) -> pd.DataFrame:
    """Long NDVI table → one row per CSBID×Year with Month1..Month12_NDVI."""
    df = ndvi_long.copy()
    df["Year"] = pd.to_numeric(df["Year"], errors="coerce").astype("Int64")
    df["Month"] = pd.to_numeric(df["Month"], errors="coerce").astype("Int64")

    id_cols = ["CSBID", "Year"]
    for c in ["County", "Shape_area", "CDL", "Shape_acers"]:
        if c in df.columns:
            id_cols.append(c)

    grouped = (
        df.dropna(subset=["NDVI", "Year", "Month"])
          .groupby(id_cols + ["Month"], as_index=False)
          .agg(NDVI=("NDVI", "mean"))
    )
    months = list(range(1, 13))
    wide = (
        grouped.pivot(index=id_cols, columns="Month", values="NDVI")
               .reindex(columns=months)
               .rename(columns={m: f"Month{m}_NDVI" for m in months})
               .reset_index()
    )
    return wide[id_cols + [f"Month{m}_NDVI" for m in months]]


def build_season(ndvi_wide: pd.DataFrame, crop: str,
                 crop_codes: set) -> tuple:
    """Calendar-wide → season-wide for one crop. Returns (df, month_feats)."""
    prev_months = CROP_WINDOWS[crop]["prev"]
    curr_months = CROP_WINDOWS[crop]["curr"]
    month_feats = [f"Month{m}_NDVI"
                   for m in sorted(prev_months) + sorted(curr_months)]

    cal_all = ndvi_wide.sort_values(["CSBID", "Year"]).copy()
    for m in set(prev_months + curr_months):
        col = f"Month{m}_NDVI"
        if col not in cal_all.columns:
            cal_all[col] = np.nan

    # Filter to this crop's CDL codes
    if crop_codes and "CDL" in cal_all.columns:
        cal_crop = cal_all[cal_all["CDL"].isin(crop_codes)].copy()
    else:
        cal_crop = cal_all.copy()

    # Bring in previous-year months (Year-1 → Year)
    if prev_months:
        prev_cols = [f"Month{m}_NDVI" for m in prev_months]
        prev_df = cal_all[["CSBID", "Year"] + prev_cols].copy()
        prev_df["Year"] = prev_df["Year"] + 1
        prev_df = prev_df.rename(
            columns={c: f"__prev__{c}" for c in prev_cols})
        cal_crop = cal_crop.drop(columns=prev_cols, errors="ignore")
        season = cal_crop.merge(prev_df, on=["CSBID", "Year"], how="left")
        for m in prev_months:
            season[f"Month{m}_NDVI"] = season[f"__prev__Month{m}_NDVI"]
            season = season.drop(columns=[f"__prev__Month{m}_NDVI"])
    else:
        season = cal_crop.copy()

    season = season.rename(columns={"Year": "Season_year"})
    meta = ["CSBID", "Season_year", "County", "Shape_area", "CDL",
            "Shape_acers"]
    meta_cols = [c for c in meta if c in season.columns]
    keep = meta_cols + month_feats
    for c in keep:
        if c not in season.columns:
            season[c] = np.nan
    season = season[keep]

    # Drop rows with any missing month feature
    miss = season[month_feats].isna().sum(axis=1)
    season = season[miss == 0].reset_index(drop=True)
    return season, month_feats


def softplus(z):
    return np.log1p(np.exp(np.clip(z, -20, 20)))


def sigmoid(z):
    return 1.0 / (1.0 + np.exp(-np.clip(z, -20, 20)))


def make_dataset(df_in, truth_df, month_feats):
    df = df_in.reset_index(drop=True).copy()
    scaler = StandardScaler().fit(df[month_feats].to_numpy())
    X = scaler.transform(df[month_feats].to_numpy())
    X = np.c_[X, np.ones(X.shape[0])]
    A = df["Shape_acers"].to_numpy().astype(float)
    grp_idx = {
        k: np.array(list(v), dtype=int)
        for k, v in df.groupby(["County", "Season_year"]).groups.items()
    }
    keys = df[["County", "Season_year"]].drop_duplicates()
    truth_subset = (
        keys.merge(truth_df[["County", "Season_year", "Yield/acre"]],
                   on=["County", "Season_year"], how="left")
            .dropna(subset=["Yield/acre"])
    )
    y_true_map = (truth_subset
                  .set_index(["County", "Season_year"])["Yield/acre"]
                  .to_dict())
    y_scale = (max(50.0, float(np.median(list(y_true_map.values()))))
               if y_true_map else 50.0)
    return X, A, grp_idx, y_true_map, scaler, y_scale


def train_adam(X, A, grp_idx, y_true_map, y_scale):
    y_true_scaled = {k: v / y_scale for k, v in y_true_map.items()}

    def fwd_grad(w):
        z = X @ w
        yh = softplus(z)
        sg = sigmoid(z)
        mse = 0.0
        g = np.zeros_like(w)
        n = 0
        for k, idx in grp_idx.items():
            if k not in y_true_scaled:
                continue
            idx = np.asarray(idx, dtype=int)
            Ak = A[idx]
            Sk = Ak.sum() + 1e-12
            Y_hat = (Ak * yh[idx]).sum() / Sk
            T = y_true_scaled[k]
            err = Y_hat - T
            mse += err * err
            dYdw = (Ak[:, None] * sg[idx, None] * X[idx]).sum(0) / Sk
            g += 2.0 * err * dYdw
            n += 1
        if n > 0:
            mse /= n
            g /= n
        return mse, g

    w = np.zeros(X.shape[1])
    m = v = np.zeros_like(w)
    b1, b2, eps = 0.9, 0.999, 1e-8
    for t in range(1, EPOCHS + 1):
        mse_s, g = fwd_grad(w)
        g = g + 2.0 * L2 * w
        gn = np.linalg.norm(g)
        if gn > MAX_GRAD_NORM:
            g *= MAX_GRAD_NORM / (gn + 1e-12)
        m = b1 * m + (1 - b1) * g
        v = b2 * v + (1 - b2) * (g * g)
        mh = m / (1 - b1**t)
        vh = v / (1 - b2**t)
        w -= LR * mh / (np.sqrt(vh) + eps)
    return w


def predict_per_acre(df_in, scaler, w, y_scale, month_feats):
    X_std = scaler.transform(df_in[month_feats].to_numpy())
    Xb = np.c_[X_std, np.ones(X_std.shape[0])]
    return softplus(Xb @ w) * y_scale


def county_aggregate(df):
    out = (
        df.assign(_wy=df["Pred_Yield/acre"] * df["Shape_acers"])
        .groupby(["County", "Season_year"], as_index=False)
        .agg(_wy=("_wy", "sum"), area=("Shape_acers", "sum"))
    )
    out["Pred_Yield/acre"] = np.where(
        out["area"] > 0, out["_wy"] / out["area"], np.nan)
    return out[["County", "Season_year", "Pred_Yield/acre"]]


def categorize(result_df, true_yield):
    """Apply RYI categorization with quantile fallback (Cell 23 logic)."""
    df = result_df.copy()
    g = df.groupby(["County", "Season_year"])["Pred_Yield/acre"]

    truth_lut = (
        true_yield[["County", "Season_year", "Yield/acre"]]
        .dropna()
        .set_index(["County", "Season_year"])["Yield/acre"]
        .to_dict()
    )
    qtab = (
        g.quantile([Q_BAD, Q_GOOD])
        .unstack()
        .rename(columns={Q_BAD: "q_bad", Q_GOOD: "q_good"})
        .reset_index()
    )

    def _mad(x):
        med = np.median(x)
        return 1.4826 * np.median(np.abs(x - med))

    stats = g.agg(n="size", median="median").reset_index()
    stats["mad"] = g.apply(_mad).values
    thr = stats.merge(qtab, on=["County", "Season_year"], how="left")
    thr["use_q"] = (thr["n"] < MIN_N) | (not USE_MAD)
    thr["fb_bad"] = np.where(
        thr["use_q"], thr["q_bad"],
        thr["median"] - K_MAD * thr["mad"])
    thr["fb_good"] = np.where(
        thr["use_q"], thr["q_good"],
        thr["median"] + K_MAD * thr["mad"])
    thr["target"] = [
        truth_lut.get((r.County, r.Season_year))
        for r in thr.itertuples()
    ]

    df = df.merge(
        thr[["County", "Season_year", "fb_bad", "fb_good", "target"]],
        on=["County", "Season_year"], how="left")

    def _label(row):
        y, tgt = row["Pred_Yield/acre"], row["target"]
        if pd.notna(tgt) and tgt > 0:
            ryi = y / tgt
            if ryi < RYI_BAD:
                return "Bad"
            if ryi >= RYI_GOOD:
                return "Good"
            return "Average"
        if y <= row["fb_bad"]:
            return "Bad"
        if y >= row["fb_good"]:
            return "Good"
        return "Average"

    df["Category"] = df.apply(_label, axis=1)
    return df


def clean_keys(df):
    """Normalize County and Season_year types (notebook Cell 14 hygiene)."""
    df = df.copy()
    df["County"] = df["County"].astype(str).str.strip()
    df["Season_year"] = (
        pd.to_numeric(df["Season_year"], errors="coerce")
          .astype("Int64")
    )
    return df.dropna(subset=["Season_year"])


# ══════════════════════════════════════════════════════════════════════════
# Main: build calendar-wide once, then loop over crops
# ══════════════════════════════════════════════════════════════════════════

def main():
    print("Loading NDVI long table...")
    ndvi_long = pd.read_csv("Data/NDVI_ALL.csv")
    print(f"  {len(ndvi_long):,} rows loaded")

    print("Building calendar-wide pivot (shared across all crops)...")
    ndvi_wide = build_calendar_wide(ndvi_long)
    print(f"  {len(ndvi_wide):,} CSBID×Year rows\n")

    summary_rows = []
    loyo_raw_rows = []   # per-(crop, holdout_year, county) for LOYO table

    for cfg in CROP_CONFIGS:
        crop = cfg["crop"]
        print(f"{'='*60}")
        print(f"CROP: {crop.upper()}")
        print(f"{'='*60}")

        # --- load ground truth ---
        true_yield = pd.read_csv(cfg["truth"])
        true_yield = clean_keys(true_yield)
        true_yield = true_yield.dropna(subset=["Yield/acre"])

        # --- build season features ---
        ndvi_df, month_feats = build_season(
            ndvi_wide, crop=crop, crop_codes=cfg["cdl"])
        ndvi_df = clean_keys(ndvi_df)
        ndvi_df = ndvi_df.dropna(subset=month_feats)
        print(f"  Season rows: {len(ndvi_df):,}  |  "
              f"Month features: {month_feats}")

        # --- train on all data ---
        print("  Training (full model)...")
        X, A, grp_idx, y_true_map, scaler, y_scale = make_dataset(
            ndvi_df, true_yield, month_feats)
        w = train_adam(X, A, grp_idx, y_true_map, y_scale)

        # --- predict ---
        ndvi_df["Pred_Yield/acre"] = predict_per_acre(
            ndvi_df, scaler, w, y_scale, month_feats)
        ndvi_df["Pred_Yield_total"] = (
            ndvi_df["Pred_Yield/acre"] * ndvi_df["Shape_acers"])

        # --- Leave-one-county-year-out (LOCYO) cross-validation ---
        # Each (county, year) pair is one independent observation.
        # For each fold: hold out all farms from (county C, year Y),
        # remove that county-year from truth targets, retrain, predict,
        # compare area-weighted county aggregate to held-out truth.
        # Consistent across all crops regardless of year coverage.
        truth_pairs = (
            true_yield[["County", "Season_year"]]
            .dropna()
            .drop_duplicates()
            .values.tolist()
        )
        n_folds = len(truth_pairs)

        if SKIP_LOYO:
            print("  CV skipped (--skip-loyo)")
            mean_loyo = float("nan")
        else:
            print(f"  Running LOCYO: {n_folds} folds "
                  f"({n_folds} county-year pairs)")
            cv_fold_maes = []
            for cty, yr in truth_pairs:
                # farms to hold out: this county in this year
                hold_mask = ((ndvi_df["Season_year"] == yr)
                             & (ndvi_df["County"] == cty))
                tr_df = ndvi_df[~hold_mask].reset_index(drop=True)
                te_df = ndvi_df[hold_mask].reset_index(drop=True)
                if tr_df.empty or te_df.empty:
                    continue
                # truth for training: all pairs except held-out
                truth_tr = true_yield[
                    ~((true_yield["Season_year"] == yr)
                      & (true_yield["County"] == cty))].copy()
                Xtr, Atr, gtr, ymap_tr, sc_tr, ys_tr = make_dataset(
                    tr_df, truth_tr, month_feats)
                if not ymap_tr:
                    continue
                w_lo = train_adam(Xtr, Atr, gtr, ymap_tr, ys_tr)
                te_df["Pred_Yield/acre"] = predict_per_acre(
                    te_df, sc_tr, w_lo, ys_tr, month_feats)
                cnty_pred = county_aggregate(te_df)
                # truth for this held-out pair only
                truth_te = true_yield[
                    (true_yield["Season_year"] == yr)
                    & (true_yield["County"] == cty)]
                merged = cnty_pred.merge(
                    truth_te[["County", "Season_year", "Yield/acre"]],
                    on=["County", "Season_year"], how="inner").dropna()
                if merged.empty:
                    continue
                row = merged.iloc[0]
                err = row["Pred_Yield/acre"] - row["Yield/acre"]
                loyo_raw_rows.append({
                    "crop":         crop,
                    "holdout_year": int(yr),
                    "County":       cty,
                    "mae":          abs(err),
                    "error":        err,
                    "yield_acre":   row["Yield/acre"],
                    "pred_acre":    row["Pred_Yield/acre"],
                    "method":       "locyo",
                })
                cv_fold_maes.append(abs(err))
                print(f"    fold ({cty}, {yr}): "
                      f"MAE={abs(err):.3f}  "
                      f"pred={row['Pred_Yield/acre']:.3f}  "
                      f"truth={row['Yield/acre']:.3f}")
            mean_loyo = (float(np.mean(cv_fold_maes))
                         if cv_fold_maes else float("nan"))
            print(f"  Mean LOCYO MAE ({crop}): {mean_loyo:.3f}  "
                  f"({len(cv_fold_maes)}/{n_folds} folds evaluated)")

        # --- categorize (full-model predictions) ---
        result_df = categorize(ndvi_df, true_yield)
        print("  Category counts:")
        print("   ", result_df["Category"].value_counts().to_dict())

        # --- save ---
        result_df.to_csv(cfg["out"], index=False)
        print(f"  Saved → {cfg['out']}")

        summary_rows.append({
            "crop":      crop,
            "n_fields":  len(result_df),
            "loyo_mae":  round(mean_loyo, 3),
            "out":       cfg["out"],
        })

    # --- save LOYO raw results ---
    if not SKIP_LOYO and loyo_raw_rows:
        loyo_raw_df = pd.DataFrame(loyo_raw_rows)
        loyo_raw_df.to_csv(LOYO_RAW_OUT, index=False)
        print(f"\nLOYO raw results saved → {LOYO_RAW_OUT}")
        print(f"  ({len(loyo_raw_df)} county×year rows across all crops)")
        print("  Pass this file to 00_build_loyo_table.py with --load-loyo "
              "to skip retraining.")

    print(f"\n{'='*60}")
    print("BATCH COMPLETE — Summary:")
    print(f"{'='*60}")
    for row in summary_rows:
        print(f"  {row['crop']:10s}  "
              f"n={row['n_fields']:,}  "
              f"LOYO_MAE={row['loyo_mae']}  "
              f"→ {row['out']}")


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    main()
