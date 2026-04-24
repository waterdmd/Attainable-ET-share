"""
00_build_loyo_table.py
======================
Generate the yield model LOYO (leave-one-year-out) performance table
used in the manuscript (Table 1 / Table S).

Two modes
---------
actual (default)
    For each crop, for each holdout year: retrain the model on the
    remaining years, predict on the holdout year for all counties,
    compute area-weighted county-level MAE.  This is the proper LOYO.

posthoc
    Load the existing *_Yield_Predictions_new.csv (trained on ALL years)
    and compute county-level MAE against truth.  This is in-sample
    evaluation — not true LOYO — but matches how the original table was
    produced.  Use as a fallback if actual LOYO numbers are unreliable.

Usage
-----
# Full actual LOYO (slow — retrains model 5×6 = 30 times):
python 00_build_loyo_table.py

# Use pre-computed LOYO rows saved by Corrected_Yield_Modeling_batch.py:
python 00_build_loyo_table.py --load-loyo Data/LOYO_raw_results.csv

# Post-hoc (fast, in-sample) using existing prediction CSVs:
python 00_build_loyo_table.py --mode posthoc

# Compare both modes side by side (no file saved):
python 00_build_loyo_table.py --compare

Run from the Implementation directory OR this scripts directory.
Output: Documentation/data/tables/LOYO_MAE_stats_with_yield_range.csv
"""

import os
import sys
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

# ── paths ─────────────────────────────────────────────────────────────────
from pathlib import Path as _Path
CLEAN_DIR = str(_Path(__file__).resolve().parent.parent)   # → Documentation/
IMPL_DIR  = str(_Path(__file__).resolve().parent.parent.parent)  # → Implementation/
OUT_CSV = f"{CLEAN_DIR}/data/tables/LOYO_MAE_stats_with_yield_range.csv"
OUT_S1_CSV = f"{CLEAN_DIR}/data/tables/fullmodel_eval_by_crop.csv"

# ── parse args ────────────────────────────────────────────────────────────
MODE = "actual"
LOAD_LOYO = None
COMPARE = "--compare" in sys.argv

for i, arg in enumerate(sys.argv[1:], 1):
    if arg == "--mode" and i < len(sys.argv) - 1:
        MODE = sys.argv[i + 1]
    if arg == "--load-loyo" and i < len(sys.argv) - 1:
        LOAD_LOYO = sys.argv[i + 1]

if COMPARE:
    MODE = "actual"   # run actual; posthoc computed separately for diff

# ── crop configs ──────────────────────────────────────────────────────────
CROP_CONFIGS = [
    {
        "crop":  "alfalfa",
        "cdl":   {36},
        "truth": f"{IMPL_DIR}/Data/YIELD_ALFALFA.csv",
        "preds": f"{IMPL_DIR}/Data/Alfalfa_Yield_Predictions_new.csv",
    },
    {
        "crop":  "wheat",
        "cdl":   {238, 22, 24, 23, 236, 225, 230},
        "truth": f"{IMPL_DIR}/Data/YIELD_WHEAT.csv",
        "preds": f"{IMPL_DIR}/Data/Wheat_Yield_Predictions_new.csv",
    },
    {
        "crop":  "cotton",
        "cdl":   {2, 238, 232},
        "truth": f"{IMPL_DIR}/Data/YIELD_COTTON.csv",
        "preds": f"{IMPL_DIR}/Data/Cotton_Yield_Predictions_new.csv",
    },
    {
        "crop":  "barley",
        "cdl":   {21, 233, 235, 237, 254},
        "truth": f"{IMPL_DIR}/Data/YIELD_BARLEY.csv",
        "preds": f"{IMPL_DIR}/Data/Barley_Yield_Predictions_new.csv",
    },
    {
        "crop":  "corn",
        "cdl":   {228, 1, 225, 226, 237},
        "truth": f"{IMPL_DIR}/Data/YIELD_CORN.csv",
        "preds": f"{IMPL_DIR}/Data/Corn_Yield_Predictions_new.csv",
    },
]

CROP_WINDOWS = {
    "wheat":   {"prev": [12],           "curr": [1, 2, 3, 4, 5, 6]},
    "barley":  {"prev": [11, 12],       "curr": [1, 2, 3, 4, 5, 6]},
    "alfalfa": {"prev": [9, 10, 11, 12], "curr": [1, 2, 3, 4, 5, 6, 7, 8]},
    "cotton":  {"prev": [],             "curr": [4, 5, 6, 7, 8, 9]},
    "corn":    {"prev": [],             "curr": [6, 7, 8]},
}

EPOCHS = 10000
LR = 0.02
L2 = 1e-3
MAX_GRAD_NORM = 100.0


# ══════════════════════════════════════════════════════════════════════════
# Model helpers (identical to Corrected_Yield_Modeling_batch.py)
# ══════════════════════════════════════════════════════════════════════════

def build_calendar_wide(ndvi_long):
    df = ndvi_long.copy()
    df["Year"] = pd.to_numeric(df["Year"], errors="coerce").astype("Int64")
    df["Month"] = pd.to_numeric(df["Month"], errors="coerce").astype("Int64")
    id_cols = ["CSBID", "Year"]
    for c in ["County", "Shape_area", "CDL", "Shape_acers"]:
        if c in df.columns:
            id_cols.append(c)
    grouped = (df.dropna(subset=["NDVI", "Year", "Month"])
                 .groupby(id_cols + ["Month"], as_index=False)
                 .agg(NDVI=("NDVI", "mean")))
    months = list(range(1, 13))
    wide = (grouped.pivot(index=id_cols, columns="Month", values="NDVI")
                   .reindex(columns=months)
                   .rename(columns={m: f"Month{m}_NDVI" for m in months})
                   .reset_index())
    return wide[id_cols + [f"Month{m}_NDVI" for m in months]]


def build_season(ndvi_wide, crop, crop_codes):
    prev_months = CROP_WINDOWS[crop]["prev"]
    curr_months = CROP_WINDOWS[crop]["curr"]
    month_feats = [f"Month{m}_NDVI"
                   for m in sorted(prev_months) + sorted(curr_months)]
    cal_all = ndvi_wide.sort_values(["CSBID", "Year"]).copy()
    for m in set(prev_months + curr_months):
        col = f"Month{m}_NDVI"
        if col not in cal_all.columns:
            cal_all[col] = np.nan
    if crop_codes and "CDL" in cal_all.columns:
        cal_crop = cal_all[cal_all["CDL"].isin(crop_codes)].copy()
    else:
        cal_crop = cal_all.copy()
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
    truth_sub = (
        keys.merge(
            truth_df[["County", "Season_year", "Yield/acre"]],
            on=["County", "Season_year"], how="left")
        .dropna(subset=["Yield/acre"])
    )
    y_true_map = (truth_sub
                  .set_index(["County", "Season_year"])["Yield/acre"]
                  .to_dict())
    y_scale = (max(50.0, float(np.median(list(y_true_map.values()))))
               if y_true_map else 50.0)
    return X, A, grp_idx, y_true_map, scaler, y_scale


def train_adam(X, A, grp_idx, y_true_map, y_scale):
    y_ts = {k: v / y_scale for k, v in y_true_map.items()}

    def fwd_grad(w):
        z = X @ w
        yh = softplus(z)
        sg = sigmoid(z)
        g = np.zeros_like(w)
        n = 0
        for k, idx in grp_idx.items():
            if k not in y_ts:
                continue
            idx = np.asarray(idx, dtype=int)
            Ak = A[idx]
            Sk = Ak.sum() + 1e-12
            Y_hat = (Ak * yh[idx]).sum() / Sk
            err = Y_hat - y_ts[k]
            dYdw = (Ak[:, None] * sg[idx, None] * X[idx]).sum(0) / Sk
            g += 2.0 * err * dYdw
            n += 1
        if n > 0:
            g /= n
        return g

    w = np.zeros(X.shape[1])
    m = np.zeros_like(w)
    v = np.zeros_like(w)
    b1, b2, eps = 0.9, 0.999, 1e-8
    for t in range(1, EPOCHS + 1):
        g = fwd_grad(w)
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
    out = (df.assign(_wy=df["Pred_Yield/acre"] * df["Shape_acers"])
             .groupby(["County", "Season_year"], as_index=False)
             .agg(_wy=("_wy", "sum"), area=("Shape_acers", "sum")))
    out["Pred_Yield/acre"] = np.where(
        out["area"] > 0, out["_wy"] / out["area"], np.nan)
    return out[["County", "Season_year", "Pred_Yield/acre"]]


def clean_keys(df):
    df = df.copy()
    df["County"] = df["County"].astype(str).str.strip()
    df["Season_year"] = (pd.to_numeric(df["Season_year"], errors="coerce")
                           .astype("Int64"))
    return df.dropna(subset=["Season_year"])


# ══════════════════════════════════════════════════════════════════════════
# LOYO computation
# ══════════════════════════════════════════════════════════════════════════

def run_actual_loyo(ndvi_wide):
    """
    Proper leave-one-year-out: retrain without year Y, predict on year Y
    for all counties that have truth.  Returns raw rows DataFrame.

    If a crop has only 1 truth year, LOYO is degenerate (training fold
    has no targets). Those crops fall back to post-hoc in-sample
    evaluation automatically, flagged with method='posthoc'.
    """
    rows = []
    for cfg in CROP_CONFIGS:
        crop = cfg["crop"]
        print(f"  {crop.upper()}")
        true_yield = clean_keys(pd.read_csv(cfg["truth"]))
        true_yield = true_yield.dropna(subset=["Yield/acre"])
        truth_years = sorted(true_yield["Season_year"].dropna().unique())

        ndvi_df, month_feats = build_season(
            ndvi_wide, crop=crop, crop_codes=cfg["cdl"])
        ndvi_df = clean_keys(ndvi_df).dropna(subset=month_feats)

        # ── fallback: only 1 truth year → post-hoc ───────────────────────
        if len(truth_years) <= 1:
            print(f"    Only {len(truth_years)} truth year(s) — "
                  f"LOYO not viable, using post-hoc in-sample evaluation")
            X, A, grp, ymap, sc, ys = make_dataset(
                ndvi_df, true_yield, month_feats)
            if not ymap:
                print(f"    No truth overlap — skipping {crop}")
                continue
            w = train_adam(X, A, grp, ymap, ys)
            ndvi_df["Pred_Yield/acre"] = predict_per_acre(
                ndvi_df, sc, w, ys, month_feats)
            cnty = county_aggregate(ndvi_df)
            merged = cnty.merge(
                true_yield[["County", "Season_year", "Yield/acre"]],
                on=["County", "Season_year"], how="inner").dropna()
            for _, r in merged.iterrows():
                rows.append({
                    "crop":         crop,
                    "holdout_year": int(r["Season_year"]),
                    "County":       r["County"],
                    "mae": abs(r["Pred_Yield/acre"] - r["Yield/acre"]),
                    "error": r["Pred_Yield/acre"] - r["Yield/acre"],
                    "yield_acre": r["Yield/acre"],
                    "pred_acre": r["Pred_Yield/acre"],
                    "method": "posthoc",
                })
            ph_mae = (merged["Pred_Yield/acre"]
                      .sub(merged["Yield/acre"]).abs().mean())
            print(f"    Post-hoc MAE: {ph_mae:.3f}  "
                  f"n={len(merged)} county-years")
            continue

        # ── actual LOYO ───────────────────────────────────────────────────
        for yr in truth_years:
            hold_mask = ndvi_df["Season_year"] == yr
            tr_df = ndvi_df[~hold_mask].reset_index(drop=True)
            te_df = ndvi_df[hold_mask].reset_index(drop=True)
            if tr_df.empty or te_df.empty:
                continue
            X, A, grp, ymap, sc, ys = make_dataset(
                tr_df, true_yield, month_feats)
            if not ymap:
                print(f"    LOYO {yr}: no truth in training fold, skip")
                continue
            w = train_adam(X, A, grp, ymap, ys)
            te_df["Pred_Yield/acre"] = predict_per_acre(
                te_df, sc, w, ys, month_feats)
            cnty = county_aggregate(te_df)
            merged = cnty.merge(
                true_yield[["County", "Season_year", "Yield/acre"]],
                on=["County", "Season_year"], how="inner").dropna()
            for _, r in merged.iterrows():
                rows.append({
                    "crop":         crop,
                    "holdout_year": int(yr),
                    "County":       r["County"],
                    "mae": abs(r["Pred_Yield/acre"] - r["Yield/acre"]),
                    "error": r["Pred_Yield/acre"] - r["Yield/acre"],
                    "yield_acre": r["Yield/acre"],
                    "pred_acre": r["Pred_Yield/acre"],
                    "method": "actual_loyo",
                })
            yr_mae = merged["Pred_Yield/acre"].sub(
                merged["Yield/acre"]).abs().mean()
            print(f"    hold-out {yr}: MAE={yr_mae:.3f}  "
                  f"n={len(merged)} county-years")
    return pd.DataFrame(rows)


def run_posthoc(cfg_list):
    """
    In-sample county MAE using existing *_Yield_Predictions_new.csv
    (model was trained on ALL years — not true LOYO).
    """
    rows = []
    for cfg in cfg_list:
        crop = cfg["crop"]
        if not os.path.exists(cfg["preds"]):
            print(f"  {crop}: predictions CSV not found, skipping")
            continue
        pred = clean_keys(pd.read_csv(cfg["preds"]))
        truth = clean_keys(pd.read_csv(cfg["truth"]))
        truth = truth.dropna(subset=["Yield/acre"])

        pred["_wy"] = pred["Pred_Yield/acre"] * pred["Shape_acers"]
        cnty = (pred.groupby(["County", "Season_year"], as_index=False)
                    .agg(wy=("_wy", "sum"), area=("Shape_acers", "sum")))
        cnty["pred_acre"] = cnty["wy"] / cnty["area"]
        merged = cnty.merge(
            truth[["County", "Season_year", "Yield/acre"]],
            on=["County", "Season_year"], how="inner").dropna()
        for _, r in merged.iterrows():
            rows.append({
                "crop":         crop,
                "holdout_year": int(r["Season_year"]),
                "County":       r["County"],
                "mae":          abs(r["pred_acre"] - r["Yield/acre"]),
                "yield_acre":   r["Yield/acre"],
                "pred_acre":    r["pred_acre"],
            })
    return pd.DataFrame(rows)


def aggregate_loyo_table(raw_df):
    """
    Aggregate LOCYO fold results → one row per crop (Table 1).

    Each fold is one county-year holdout (n=1 prediction), so R² is not
    meaningful per fold. Metrics reported:
      MAE       — mean of per-fold absolute errors
      RMSE      — sqrt of mean squared per-fold errors
      CI_95     — 95% bootstrap CI on MAE (2000 resamples)
      mae_%med  — MAE as % of median truth yield
    """
    rng = np.random.default_rng(42)
    out = []
    for crop, grp in raw_df.groupby("crop"):
        maes = grp["mae"].to_numpy()
        yields = grp["yield_acre"].to_numpy()

        if "error" in grp.columns:
            errors = grp["error"].to_numpy()
        else:
            errors = grp["pred_acre"].to_numpy() - yields

        mae = float(np.mean(maes))
        rmse = float(np.sqrt(np.mean(errors ** 2)))

        # 95% bootstrap CI on MAE across folds
        n = len(maes)
        boot_maes = np.mean(
            rng.choice(maes, size=(2000, n), replace=True), axis=1)
        ci_lo = float(np.percentile(boot_maes, 2.5))
        ci_hi = float(np.percentile(boot_maes, 97.5))

        row = {
            "crop": crop,
            "count": n,
            "mean": round(mae, 3),
            "median": round(float(np.median(maes)), 3),
            "min": round(float(np.min(maes)), 3),
            "max": round(float(np.max(maes)), 3),
            "rmse": round(rmse, 3),
            "ci_95_lo": round(ci_lo, 3),
            "ci_95_hi": round(ci_hi, 3),
            "yield_min": round(float(np.min(yields)), 3),
            "yield_max": round(float(np.max(yields)), 3),
            "yield_median": round(float(np.median(yields)), 3),
            "yield_mean": round(float(np.mean(yields)), 3),
            "mae_pct_of_median": round(
                mae / float(np.median(yields)) * 100, 3),
        }
        out.append(row)
    return pd.DataFrame(out, columns=[
        "crop", "count", "mean", "median", "min", "max",
        "rmse", "ci_95_lo", "ci_95_hi",
        "yield_min", "yield_max", "yield_median", "yield_mean",
        "mae_pct_of_median",
    ])


def build_fullmodel_table(cfg_list, n_boot=2000, seed=42):
    """
    Full in-sample evaluation across all county-years (Table S1).

    Trains on all data, aggregates to county-year level, computes
    R², RMSE, MAE against truth. This is where R² is meaningful
    because we have multiple (pred, truth) pairs per crop.
    Bootstrap CIs (2000 resamples) on R², RMSE, MAE match the
    description in manuscript P068.
    """
    rng = np.random.default_rng(seed)
    out = []
    print("\nBuilding full-model evaluation table (Table S1)...")
    for cfg in cfg_list:
        crop = cfg["crop"]
        if not os.path.exists(cfg["preds"]):
            print(f"  {crop}: predictions CSV not found, skipping")
            continue
        pred = clean_keys(pd.read_csv(cfg["preds"]))
        truth = clean_keys(pd.read_csv(cfg["truth"]))
        truth = truth.dropna(subset=["Yield/acre"])

        pred["_wy"] = pred["Pred_Yield/acre"] * pred["Shape_acers"]
        cnty = (pred.groupby(["County", "Season_year"], as_index=False)
                .agg(wy=("_wy", "sum"), area=("Shape_acers", "sum")))
        cnty["pred_acre"] = cnty["wy"] / cnty["area"]
        merged = cnty.merge(
            truth[["County", "Season_year", "Yield/acre"]],
            on=["County", "Season_year"], how="inner").dropna()

        if merged.empty:
            continue

        y_true = merged["Yield/acre"].to_numpy(float)
        y_pred = merged["pred_acre"].to_numpy(float)
        n = len(y_true)

        def _metrics(yt, yp):
            err = yp - yt
            mae_ = float(np.mean(np.abs(err)))
            rmse_ = float(np.sqrt(np.mean(err ** 2)))
            ss_res = float(np.sum(err ** 2))
            ss_tot = float(np.sum((yt - yt.mean()) ** 2))
            r2_ = float(1 - ss_res / ss_tot) if ss_tot > 0 else float("nan")
            return r2_, rmse_, mae_

        r2, rmse, mae = _metrics(y_true, y_pred)

        # Bootstrap CIs (resample county-year pairs)
        idx_boot = rng.integers(0, n, size=(n_boot, n))
        boot_r2   = np.array([_metrics(y_true[i], y_pred[i])[0] for i in idx_boot])
        boot_rmse = np.array([_metrics(y_true[i], y_pred[i])[1] for i in idx_boot])
        boot_mae  = np.array([_metrics(y_true[i], y_pred[i])[2] for i in idx_boot])

        print("  %s: n=%d  R2=%.4f [%.2f,%.2f]  RMSE=%.3f  MAE=%.3f" % (
              crop, n, r2, np.percentile(boot_r2, 2.5),
              np.percentile(boot_r2, 97.5), rmse, mae))
        out.append({
            "crop":            crop,
            "n_county_years":  n,
            "r2":              round(r2, 4),
            "r2_ci_lo":        round(float(np.percentile(boot_r2,  2.5)), 4),
            "r2_ci_hi":        round(float(np.percentile(boot_r2, 97.5)), 4),
            "rmse":            round(rmse, 3),
            "rmse_ci_lo":      round(float(np.percentile(boot_rmse,  2.5)), 3),
            "rmse_ci_hi":      round(float(np.percentile(boot_rmse, 97.5)), 3),
            "mae":             round(mae, 3),
            "mae_ci_lo":       round(float(np.percentile(boot_mae,  2.5)), 3),
            "mae_ci_hi":       round(float(np.percentile(boot_mae, 97.5)), 3),
            "mae_pct_of_median": round(
                mae / float(np.median(y_true)) * 100, 3),
        })
    return pd.DataFrame(out, columns=[
        "crop", "n_county_years",
        "r2", "r2_ci_lo", "r2_ci_hi",
        "rmse", "rmse_ci_lo", "rmse_ci_hi",
        "mae", "mae_ci_lo", "mae_ci_hi",
        "mae_pct_of_median",
    ])


def print_comparison(actual_tbl, posthoc_tbl, existing_tbl=None):
    print(f"\n{'─'*70}")
    print(f"{'CROP':<10} {'MODE':<10} "
          f"{'count':>6} {'mean MAE':>9} {'median MAE':>10} "
          f"{'mae_%med':>9}")
    print(f"{'─'*70}")
    for crop in [c["crop"] for c in CROP_CONFIGS]:
        for label, tbl in [("actual", actual_tbl), ("posthoc", posthoc_tbl)]:
            if tbl is None:
                continue
            row = tbl[tbl["crop"] == crop]
            if row.empty:
                continue
            r = row.iloc[0]
            print(f"{crop:<10} {label:<10} "
                  f"{r['count']:>6} {r['mean']:>9.3f} "
                  f"{r['median']:>10.3f} {r['mae_pct_of_median']:>9.1f}%")
        if existing_tbl is not None:
            row = existing_tbl[existing_tbl["crop"] == crop]
            if not row.empty:
                r = row.iloc[0]
                print(f"{crop:<10} {'(stored)':<10} "
                      f"{r['count']:>6} {r['mean']:>9.3f} "
                      f"{r['median']:>10.3f} {r['mae_pct_of_median']:>9.1f}%")
        print()
    print(f"{'─'*70}")


# ══════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════

def main():
    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)

    # Load stored table for comparison
    existing_tbl = None
    if os.path.exists(OUT_CSV):
        existing_tbl = pd.read_csv(OUT_CSV)
        print(f"Existing table found: {OUT_CSV}")

    # ── actual LOYO ──────────────────────────────────────────────────────
    actual_raw = None
    actual_tbl = None

    if MODE == "actual" or COMPARE:
        if LOAD_LOYO:
            print(f"\nLoading pre-computed LOYO results: {LOAD_LOYO}")
            actual_raw = pd.read_csv(LOAD_LOYO)
            print(f"  {len(actual_raw)} rows loaded")
        else:
            print("\nRunning actual LOYO (retraining per year)...")
            print("Loading NDVI long table...")
            ndvi_long = pd.read_csv(f"{IMPL_DIR}/Data/NDVI_ALL.csv")
            ndvi_wide = build_calendar_wide(ndvi_long)
            print(f"Calendar-wide: {len(ndvi_wide):,} rows\n")
            actual_raw = run_actual_loyo(ndvi_wide)

        actual_tbl = aggregate_loyo_table(actual_raw)

    # ── post-hoc ─────────────────────────────────────────────────────────
    posthoc_raw = None
    posthoc_tbl = None

    if MODE == "posthoc" or COMPARE:
        print("\nRunning post-hoc (in-sample, existing CSVs)...")
        posthoc_raw = run_posthoc(CROP_CONFIGS)
        posthoc_tbl = aggregate_loyo_table(posthoc_raw)

    # ── comparison print ─────────────────────────────────────────────────
    if COMPARE:
        print_comparison(actual_tbl, posthoc_tbl, existing_tbl)
        answer = input(
            "\nSave which table? [actual / posthoc / keep / skip]: "
        ).strip().lower()
        if answer == "actual":
            save_tbl = actual_tbl
        elif answer == "posthoc":
            save_tbl = posthoc_tbl
        elif answer == "keep":
            print("Keeping existing table unchanged.")
            return
        else:
            print("Nothing saved.")
            return
    elif MODE == "actual":
        save_tbl = actual_tbl
    else:
        save_tbl = posthoc_tbl

    # ── save ─────────────────────────────────────────────────────────────
    save_tbl.to_csv(OUT_CSV, index=False)
    print(f"\nSaved -> {OUT_CSV}")
    print(save_tbl.to_string(index=False))

    # ── flag big differences vs existing ─────────────────────────────────
    if existing_tbl is not None and save_tbl is not None:
        merged = save_tbl.merge(existing_tbl, on="crop",
                                suffixes=("_new", "_old"))
        print("\nChange vs stored table (new - old):")
        for _, r in merged.iterrows():
            delta = r["mean_new"] - r["mean_old"]
            pct = abs(delta) / (r["mean_old"] + 1e-9) * 100
            flag = " !" if pct > 20 else ""
            print(f"  {r['crop']:<10}  mean MAE: "
                  f"{r['mean_old']:.3f} -> {r['mean_new']:.3f}  "
                  f"({delta:+.3f}, {pct:.1f}%){flag}")

    # ── Table S1: full-model in-sample evaluation (R2 valid here) ────────
    s1_tbl = build_fullmodel_table(CROP_CONFIGS)
    if not s1_tbl.empty:
        s1_tbl.to_csv(OUT_S1_CSV, index=False)
        print(f"\nSaved Table S1 -> {OUT_S1_CSV}")
        print(s1_tbl.to_string(index=False))


if __name__ == "__main__":
    main()
