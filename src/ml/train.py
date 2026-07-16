"""
Phase 9 — ML Experimentation & Feature Store.

Loads the Gold feature table from AWS S3 Data Lake, performs a chronological
train/val/test split, trains 5 models (Linear Regression, Random Forest,
XGBoost, LightGBM, PyTorch LSTM), evaluates each with financial metrics
(RMSE, Directional Accuracy, IC, Sharpe), and logs everything to MLflow
(Databricks-hosted, with local fallback). The best model is registered in
the MLflow Model Registry.
"""

import os
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore
    except Exception:
        pass

import numpy as np
import pandas as pd
from typing import Any, Optional, Tuple
from dotenv import load_dotenv
from deltalake import DeltaTable

from src.utils.s3_helper import get_s3_path, get_storage_options

load_dotenv()

# ─── Feature & Target Definitions ────────────────────────────────────────────

FEATURE_COLS = [
    "open", "high", "low", "close", "volume",
    "sma_20", "sma_50", "sma_200",
    "rsi_14", "macd", "macd_signal", "macd_hist",
    "bb_upper", "bb_lower", "bb_width",
    "return_1d", "return_5d", "return_20d",
    "volatility_20d",
    "rel_strength_sector",
    "volume_ratio",
    "price_position_52w",
    "vol_regime_ratio",
    "sentiment_pos", "sentiment_neg", "sentiment_neu", "sentiment_net",
]

TARGET_COL = "target_5d_return"

TRAIN_FRAC = 0.70
VAL_FRAC   = 0.15
# Test is the remaining 15%

SEQ_LEN    = 10       # LSTM look-back window
LSTM_EPOCHS = 10
LSTM_LR    = 1e-3
LSTM_HIDDEN = 64
LSTM_BATCH  = 64


# ─── Helper Utilities ─────────────────────────────────────────────────────────

def load_gold_features() -> pd.DataFrame:
    """Load Gold Delta table."""
    gold_path = get_s3_path("features", layer="gold")
    storage_options = get_storage_options()
    print(f" Loading Gold features from {gold_path}...")
    dt = DeltaTable(gold_path, storage_options=storage_options)
    df = dt.to_pandas()
    print(f"   Loaded {len(df):,} rows × {len(df.columns)} columns")
    return df


def preprocess(df: pd.DataFrame):
    """
    Clean features, impute missing values, perform chronological split,
    and return scaled numpy arrays for train+val combined (for TimeSeriesSplit CV)
    and the final held-out test set.
    """
    df = df.copy()

    # Ensure date is datetime and sort chronologically
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["date", "symbol"]).reset_index(drop=True)

    # Drop rows missing the target
    df = df.dropna(subset=[TARGET_COL])

    # Keep only feature columns that exist in the table
    available = [c for c in FEATURE_COLS if c in df.columns]
    X_df = df[available].copy()

    # Forward-fill then fill remaining NaNs with 0
    X_df = X_df.ffill().fillna(0)

    # Clip extreme values (Winsorise at 1st / 99th percentile)
    for col in X_df.columns:
        lo, hi = X_df[col].quantile(0.01), X_df[col].quantile(0.99)
        X_df[col] = X_df[col].clip(lo, hi)

    y = df[TARGET_COL].values

    # Chronological split: first 85% for CV, final 15% is held-out test
    n = len(X_df)
    n_trainval = int(n * (TRAIN_FRAC + VAL_FRAC))  # 85%

    X_trainval_raw = X_df.iloc[:n_trainval].values
    X_test_raw     = X_df.iloc[n_trainval:].values

    y_trainval = y[:n_trainval]
    y_test     = y[n_trainval:]

    # StandardScaler fitted on train+val only — prevent data leakage
    mean = X_trainval_raw.mean(axis=0)
    std  = X_trainval_raw.std(axis=0) + 1e-8

    X_trainval = (X_trainval_raw - mean) / std
    X_test     = (X_test_raw - mean) / std

    print(f"   TrainVal: {X_trainval.shape} | Test (held-out): {X_test.shape}")
    return X_trainval, X_test, y_trainval, y_test, available, mean, std


# ─── Financial Metrics ────────────────────────────────────────────────────────

def rmse(y_true, y_pred):
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


def directional_accuracy(y_true, y_pred):
    return float(np.mean(np.sign(y_true) == np.sign(y_pred)))


def information_coefficient(y_true, y_pred):
    """Rank-based IC using Spearman correlation."""
    from scipy.stats import spearmanr
    corr, _ = spearmanr(y_true, y_pred)
    return float(corr) if not np.isnan(corr) else 0.0


def simulated_sharpe(y_true, y_pred, top_n: int = 10):
    """
    Simple long/short portfolio Sharpe.
    Each period: go long the top_n predicted stocks, short the bottom_n.
    """
    pnl = []
    period = top_n * 2
    if len(y_true) < period:
        return 0.0
    for i in range(0, len(y_true) - period, period):
        pred_slice = y_pred[i : i + period]
        true_slice = y_true[i : i + period]
        rank = np.argsort(pred_slice)
        long_ret  = true_slice[rank[-top_n:]].mean()
        short_ret = true_slice[rank[:top_n]].mean()
        pnl.append(long_ret - short_ret)
    pnl = np.array(pnl)
    if pnl.std() < 1e-8:
        return 0.0
    return float(pnl.mean() / pnl.std() * np.sqrt(252 / period))


def evaluate(y_true, y_pred, model_name: str) -> dict:
    metrics = {
        "rmse":    rmse(y_true, y_pred),
        "dir_acc": directional_accuracy(y_true, y_pred),
        "ic":      information_coefficient(y_true, y_pred),
        "sharpe":  simulated_sharpe(y_true, y_pred),
    }
    print(f"\n    {model_name}")
    print(f"      RMSE:    {metrics['rmse']:.4f}")
    print(f"      Dir Acc: {metrics['dir_acc']:.2%}")
    print(f"      IC:      {metrics['ic']:.4f}")
    print(f"      Sharpe:  {metrics['sharpe']:.3f}")
    return metrics


# ─── Model Training Functions ─────────────────────────────────────────────────

def train_linear(
    X_tr: np.ndarray, y_tr: np.ndarray,
    X_val: np.ndarray, y_val: np.ndarray,
) -> Tuple[Any, np.ndarray]:
    from sklearn.linear_model import Ridge
    model = Ridge(alpha=1.0)
    model.fit(X_tr, y_tr)
    return model, model.predict(X_val)


def train_random_forest(
    X_tr: np.ndarray, y_tr: np.ndarray,
    X_val: np.ndarray, y_val: np.ndarray,
) -> Tuple[Any, np.ndarray]:
    from sklearn.ensemble import RandomForestRegressor
    model = RandomForestRegressor(n_estimators=100, max_depth=6, n_jobs=-1, random_state=42)
    model.fit(X_tr, y_tr)
    return model, model.predict(X_val)


def train_xgboost(
    X_tr: np.ndarray, y_tr: np.ndarray,
    X_val: np.ndarray, y_val: np.ndarray,
) -> Tuple[Any, np.ndarray]:
    from xgboost import XGBRegressor
    model = XGBRegressor(
        n_estimators=200, max_depth=4, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8, random_state=42,
        eval_metric="rmse", verbosity=0,
        early_stopping_rounds=20,
    )
    model.fit(X_tr, y_tr, eval_set=[(X_val, y_val)], verbose=False)
    return model, model.predict(X_val)


def train_lightgbm(
    X_tr: np.ndarray, y_tr: np.ndarray,
    X_val: np.ndarray, y_val: np.ndarray,
) -> Tuple[Any, np.ndarray]:
    import lightgbm as lgb
    params = {
        "objective": "regression",
        "metric": "rmse",
        "learning_rate": 0.05,
        "num_leaves": 31,
        "max_depth": 6,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "verbosity": -1,
        "random_state": 42,
    }
    train_data = lgb.Dataset(X_tr, label=y_tr)
    val_data   = lgb.Dataset(X_val, label=y_val, reference=train_data)
    callbacks = [lgb.early_stopping(20, verbose=False), lgb.log_evaluation(-1)]
    booster = lgb.train(params, train_data, num_boost_round=200,
                        valid_sets=[val_data], callbacks=callbacks)
    return booster, booster.predict(X_val)


def train_lstm(
    X_tr: np.ndarray,
    y_tr: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    input_size: int,
) -> Tuple[Optional[Any], np.ndarray, np.ndarray]:
    """Train a 2-layer LSTM regressor.

    Returns:
        (model, val_preds_padded, mask) — always a 3-tuple.
        ``model`` is ``None`` when there is insufficient data.
        ``mask`` is a boolean array indicating which positions have valid
        predictions (``True``) vs. padding (``False``).
    """
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader
    from src.ml.lstm_model import LSTMRegressor, SequenceDataset

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    train_ds = SequenceDataset(X_tr, y_tr, SEQ_LEN)
    val_ds   = SequenceDataset(X_val, y_val, SEQ_LEN)

    if len(train_ds) == 0 or len(val_ds) == 0:
        print("   [WARNING] Not enough data for LSTM sequences — skipping.")
        fallback_preds = np.full(len(y_val), float(np.mean(y_tr)))
        fallback_mask  = np.zeros(len(y_val), dtype=bool)
        return None, fallback_preds, fallback_mask

    train_loader = DataLoader(train_ds, batch_size=LSTM_BATCH, shuffle=False)
    val_loader   = DataLoader(val_ds,   batch_size=LSTM_BATCH, shuffle=False)

    model = LSTMRegressor(input_size=input_size, hidden_size=LSTM_HIDDEN).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=LSTM_LR)
    criterion = nn.MSELoss()

    for epoch in range(LSTM_EPOCHS):
        model.train()
        train_losses = []
        for X_batch, y_batch in train_loader:
            X_batch, y_batch = X_batch.to(device), y_batch.to(device)
            optimizer.zero_grad()
            preds = model(X_batch)
            loss  = criterion(preds, y_batch)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            train_losses.append(loss.item())
        if (epoch + 1) % 5 == 0:
            print(f"      Epoch {epoch+1}/{LSTM_EPOCHS}  train_loss={np.mean(train_losses):.5f}")

    model.eval()
    preds_list = []
    with torch.no_grad():
        for X_batch, _ in val_loader:
            preds_list.append(model(X_batch.to(device)).cpu().numpy())

    val_preds = np.concatenate(preds_list)
    # Pad to match y_val length (first SEQ_LEN entries have no prediction)
    val_preds_padded = np.full(len(y_val), np.nan)
    val_preds_padded[SEQ_LEN:] = val_preds[: len(y_val) - SEQ_LEN]
    mask: np.ndarray = ~np.isnan(val_preds_padded)
    return model, val_preds_padded, mask


# ─── MLflow Setup ─────────────────────────────────────────────────────────────

def setup_mlflow() -> str:
    """Configure MLflow tracking URI: Databricks if reachable, else local ./mlruns fallback."""
    import mlflow

    db_host  = os.getenv("DBT_DATABRICKS_HOST", "")
    db_token = os.getenv("DBT_DATABRICKS_TOKEN", "")

    if db_host and db_token:
        os.environ["DATABRICKS_HOST"]  = f"https://{db_host}"
        os.environ["DATABRICKS_TOKEN"] = db_token
        # Probe the connection — PAT must have the 'mlflow' scope
        try:
            mlflow.set_tracking_uri("databricks")
            mlflow.set_experiment("/investment-platform/probe")
            # If we reach here the connection works
            print(f"    MLflow tracking → Databricks ({db_host})")
            return "databricks"
        except Exception as probe_err:
            print(f"   [WARNING]  Databricks MLflow unreachable ({type(probe_err).__name__}: {str(probe_err)[:80]})")
            print("    Falling back to local ./mlruns")

    # Local SQLite fallback (MLflow 3.x dropped file-store support)
    local_uri = "sqlite:///mlruns.db"
    mlflow.set_tracking_uri(local_uri)
    print(f"    MLflow tracking → {local_uri}")
    return local_uri


# ─── Main Training Orchestrator ───────────────────────────────────────────────

def main():
    import mlflow
    import mlflow.sklearn
    import mlflow.pytorch

    print("=" * 65)
    print(" PHASE 9 — ML EXPERIMENTATION & FEATURE STORE")
    print("=" * 65)

    # 1. Load data
    df = load_gold_features()

    # 2. Preprocess
    print("\n Preprocessing features...")
    X_tv, X_test, y_tv, y_test, feat_names, _mean, _std = preprocess(df)
    n_features = X_tv.shape[1]

    # 3. MLflow setup
    print("\n Configuring MLflow...")
    tracking_uri = setup_mlflow()

    # Set the working experiment — adjust name for local vs remote URIs
    if tracking_uri == "databricks":
        experiment_name = "/investment-platform/phase9-ml-experiments"
    else:
        experiment_name = "investment-platform-phase9"
    mlflow.set_experiment(experiment_name)
    print(f"    Experiment: {experiment_name}")

    # 4. Train all models and collect results
    results = {}
    best_model_name = None
    best_sharpe = -np.inf
    best_mlflow_run_id = None

    # ─── Optuna Tuning Helpers ────────────────────────────────────────────────

    def cv_score(X_tv, y_tv, model_factory, n_splits=5):
        """Walk-forward TimeSeriesSplit CV returning mean Sharpe across folds."""
        from sklearn.model_selection import TimeSeriesSplit
        tscv = TimeSeriesSplit(n_splits=n_splits)
        sharpes = []
        for fold_idx, (tr_idx, va_idx) in enumerate(tscv.split(X_tv)):
            X_tr_fold, X_va_fold = X_tv[tr_idx], X_tv[va_idx]
            y_tr_fold, y_va_fold = y_tv[tr_idx], y_tv[va_idx]
            m = model_factory()
            m.fit(X_tr_fold, y_tr_fold)
            preds = m.predict(X_va_fold)
            sharpes.append(simulated_sharpe(y_va_fold, preds))
        return float(np.mean(sharpes))

    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)

    # ── 4a. Optuna: Ridge ──────────────────────────────────────────────────────
    print("\n Optuna search: Ridge alpha (30 trials)...")
    mlflow.set_experiment(experiment_name)

    def ridge_objective(trial):
        alpha = trial.suggest_float("alpha", 1e-3, 100.0, log=True)
        from sklearn.linear_model import Ridge
        score = cv_score(X_tv, y_tv, lambda: Ridge(alpha=alpha))
        with mlflow.start_run(run_name=f"Ridge_trial_{trial.number}", nested=True):
            mlflow.log_param("alpha", alpha)
            mlflow.log_metric("cv_sharpe", score)
        return score

    with mlflow.start_run(run_name="Optuna_Ridge") as ridge_parent_run:
        ridge_study = optuna.create_study(direction="maximize")
        ridge_study.optimize(ridge_objective, n_trials=30, show_progress_bar=False)

    best_ridge_alpha = ridge_study.best_params["alpha"]
    print(f"    Best Ridge alpha={best_ridge_alpha:.4f}  (CV Sharpe={ridge_study.best_value:.3f})")

    # ── 4b. Optuna: XGBoost ───────────────────────────────────────────────────
    print("\n Optuna search: XGBoost params (30 trials)...")

    def xgb_objective(trial):
        from xgboost import XGBRegressor
        params = {
            "n_estimators":    trial.suggest_int("n_estimators", 100, 500),
            "max_depth":       trial.suggest_int("max_depth", 3, 8),
            "learning_rate":   trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
            "subsample":       trial.suggest_float("subsample", 0.5, 1.0),
            "colsample_bytree":trial.suggest_float("colsample_bytree", 0.5, 1.0),
            "random_state": 42, "verbosity": 0,
        }
        score = cv_score(X_tv, y_tv, lambda: XGBRegressor(**params))
        with mlflow.start_run(run_name=f"XGB_trial_{trial.number}", nested=True):
            mlflow.log_params(params)
            mlflow.log_metric("cv_sharpe", score)
        return score

    with mlflow.start_run(run_name="Optuna_XGBoost") as xgb_parent_run:
        xgb_study = optuna.create_study(direction="maximize")
        xgb_study.optimize(xgb_objective, n_trials=30, show_progress_bar=False)

    best_xgb_params = xgb_study.best_params
    best_xgb_params.update({"random_state": 42, "verbosity": 0})
    print(f"    Best XGBoost params={best_xgb_params}  (CV Sharpe={xgb_study.best_value:.3f})")

    # ── 5. Train final tuned models on full train+val set ─────────────────────
    print("\n  Training final tuned Ridge + XGBoost on full TrainVal set...")
    from sklearn.linear_model import Ridge
    from xgboost import XGBRegressor

    tuned_ridge = Ridge(alpha=best_ridge_alpha)
    tuned_ridge.fit(X_tv, y_tv)
    ridge_te_preds = tuned_ridge.predict(X_test)
    ridge_te_metrics = evaluate(y_test, ridge_te_preds, "Tuned Ridge [Test]")

    tuned_xgb = XGBRegressor(**best_xgb_params)
    tuned_xgb.fit(X_tv, y_tv)
    xgb_te_preds = tuned_xgb.predict(X_test)
    xgb_te_metrics = evaluate(y_test, xgb_te_preds, "Tuned XGBoost [Test]")

    # Log final test metrics and register both models
    with mlflow.start_run(run_name="FinalRidge_Tuned") as ridge_run:
        mlflow.log_param("model", "Ridge")
        mlflow.log_param("alpha", best_ridge_alpha)
        mlflow.log_metrics({f"test_{k}": v for k, v in ridge_te_metrics.items()})
        mlflow.sklearn.log_model(tuned_ridge, artifact_path="model")
        try:
            mlflow.register_model(
                model_uri=f"runs:/{ridge_run.info.run_id}/model",
                name="investment-platform-ridge",
            )
            print("    Registered → 'investment-platform-ridge'")
        except Exception as e:
            print(f"   [WARNING] Ridge registration skipped: {e}")

    with mlflow.start_run(run_name="FinalXGB_Tuned") as xgb_run:
        mlflow.log_param("model", "XGBoost")
        mlflow.log_params({f"xgb_{k}": v for k, v in best_xgb_params.items()})
        mlflow.log_metrics({f"test_{k}": v for k, v in xgb_te_metrics.items()})
        mlflow.xgboost.log_model(tuned_xgb, artifact_path="model")
        try:
            mlflow.register_model(
                model_uri=f"runs:/{xgb_run.info.run_id}/model",
                name="investment-platform-xgboost",
            )
            print("    Registered → 'investment-platform-xgboost'")
        except Exception as e:
            print(f"   [WARNING] XGBoost registration skipped: {e}")

    # ── 6. Also train remaining models (RF, LightGBM, LSTM) on a simple fold ──
    # Use the last 15% of trainval as a quick val slice for non-tuned models
    n_tv = len(X_tv)
    quick_val_start = int(n_tv * 0.85)
    X_qtr, X_qval = X_tv[:quick_val_start], X_tv[quick_val_start:]
    y_qtr, y_qval = y_tv[:quick_val_start], y_tv[quick_val_start:]

    models_to_train = [
        ("RandomForest", train_random_forest),
        ("XGBoost_default", train_xgboost),
        ("LightGBM",    train_lightgbm),
    ]

    for model_name, train_fn in models_to_train:
        print(f"\n Training {model_name}...")
        with mlflow.start_run(run_name=model_name) as run:
            mlflow.log_param("model", model_name)
            mlflow.log_param("features", len(feat_names))
            mlflow.log_param("train_rows", len(y_qtr))
            mlflow.log_param("val_rows", len(y_qval))

            model, val_preds = train_fn(X_qtr, y_qtr, X_qval, y_qval)
            metrics = evaluate(y_qval, val_preds, model_name)

            mlflow.log_metrics(metrics)

            # Log the model artifact
            try:
                mlflow.sklearn.log_model(model, artifact_path="model")
            except Exception:
                pass  # LightGBM booster — skip sklearn logging

            results[model_name] = {"metrics": metrics, "run_id": run.info.run_id}

            if metrics["sharpe"] > best_sharpe:
                best_sharpe = metrics["sharpe"]
                best_model_name = model_name
                best_mlflow_run_id = run.info.run_id

    # 5. Train LSTM separately (returns 3 values due to mask)
    print(f"\n Training LSTM...")
    with mlflow.start_run(run_name="LSTM") as run:
        mlflow.log_param("model", "LSTM")
        mlflow.log_param("hidden_size", LSTM_HIDDEN)
        mlflow.log_param("seq_len", SEQ_LEN)
        mlflow.log_param("epochs", LSTM_EPOCHS)
        mlflow.log_param("features", n_features)

        lstm_result = train_lstm(X_qtr, y_qtr, X_qval, y_qval, n_features)
        lstm_model, lstm_preds_padded, mask = lstm_result

        # Only evaluate on rows where we have predictions
        metrics = evaluate(y_qval[mask], lstm_preds_padded[mask], "LSTM")
        mlflow.log_metrics(metrics)

        try:
            import torch
            if lstm_model is not None:
                mlflow.pytorch.log_model(lstm_model, artifact_path="model")
        except Exception:
            pass

        results["LSTM"] = {"metrics": metrics, "run_id": run.info.run_id}

        if metrics["sharpe"] > best_sharpe:
            best_sharpe = metrics["sharpe"]
            best_model_name = "LSTM"
            best_mlflow_run_id = run.info.run_id

    # 6. Print leaderboard
    print("\n" + "=" * 65)
    print(" MODEL LEADERBOARD (Validation Set)")
    print("=" * 65)
    print(f"{'Model':<20} {'RMSE':>8} {'Dir Acc':>9} {'IC':>8} {'Sharpe':>8}")
    print("-" * 65)
    for mname, data in results.items():
        m = data["metrics"]
        marker = " *" if mname == best_model_name else ""
        print(f"{mname:<20} {m['rmse']:>8.4f} {m['dir_acc']:>8.2%} {m['ic']:>8.4f} {m['sharpe']:>8.3f}{marker}")
    print("=" * 65)
    print(f"\n Best Model: {best_model_name}  (Sharpe: {best_sharpe:.3f})")

    # 7. Register best model in MLflow Model Registry
    if best_mlflow_run_id:
        try:
            registered_name = "investment-platform-best-model"
            model_uri = f"runs:/{best_mlflow_run_id}/model"
            mlflow.register_model(model_uri=model_uri, name=registered_name)
            print(f" Registered '{best_model_name}' → Model Registry: '{registered_name}'")
        except Exception as e:
            print(f"   [WARNING] Model Registry registration skipped: {e}")

    print("\n Phase 9 — ML Experimentation completed successfully!")


if __name__ == "__main__":
    main()
