"""Dummy end-to-end (features -> inference -> evaluation) marimo app.

Run:
  marimo edit notebooks/marimo_dummy_e2e.py
  marimo run notebooks/marimo_dummy_e2e.py

Notes:
  - This notebook uses only numpy + pandas (no sklearn) to stay lightweight.
  - It's a template for wiring a real pipeline: swap data/loaders, feature code,
    model inference, and evaluation for your project.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import marimo as mo
import numpy as np
import pandas as pd


app = mo.App(width="full")


@dataclass(frozen=True)
class Metrics:
    n_train: int
    n_test: int
    accuracy: float
    log_loss: float
    brier: float
    threshold: float


def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-z))


def _standardize_fit(X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mu = X.mean(axis=0)
    sigma = X.std(axis=0)
    sigma = np.where(sigma == 0.0, 1.0, sigma)
    return mu, sigma


def _standardize_apply(X: np.ndarray, mu: np.ndarray, sigma: np.ndarray) -> np.ndarray:
    return (X - mu) / sigma


def _train_logreg_gd(
    X: np.ndarray,
    y: np.ndarray,
    lr: float,
    l2: float,
    steps: int,
    seed: int,
) -> tuple[np.ndarray, float]:
    """Tiny logistic regression trainer (GD) for demo purposes."""
    rng = np.random.default_rng(seed)
    w = rng.normal(scale=0.1, size=(X.shape[1],))
    b = 0.0

    for _ in range(steps):
        z = X @ w + b
        p = _sigmoid(z)
        # gradients
        grad_w = (X.T @ (p - y)) / X.shape[0] + l2 * w
        grad_b = float((p - y).mean())
        w -= lr * grad_w
        b -= lr * grad_b

    return w, b


def _predict_proba(X: np.ndarray, w: np.ndarray, b: float) -> np.ndarray:
    return _sigmoid(X @ w + b)


def _log_loss(y: np.ndarray, p: np.ndarray, eps: float = 1e-12) -> float:
    p = np.clip(p, eps, 1 - eps)
    return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())


def _brier(y: np.ndarray, p: np.ndarray) -> float:
    return float(((p - y) ** 2).mean())


def _accuracy(y: np.ndarray, p: np.ndarray, threshold: float) -> float:
    return float(((p >= threshold).astype(int) == y).mean())


@app.cell
def _(mo):
    mo.md(
        r"""
        # Dummy end-to-end marimo pipeline

        This is a deliberately simple, fully-contained example that shows the wiring for:

        - data generation (replace with SQLite/Parquet loaders)
        - feature processing
        - model training + inference pipeline
        - evaluation + quick validation views

        You can treat this as a template and swap in your real steps.
        """
    )
    return


@app.cell
def _(mo):
    mo.md("## Controls")
    return


@app.cell
def _(mo):
    seed = mo.ui.number(value=7, label="Random seed", step=1)
    n_rows = mo.ui.slider(200, 20000, value=3000, step=100, label="Rows")
    n_features = mo.ui.slider(2, 40, value=10, step=1, label="Raw features")
    noise = mo.ui.slider(0.0, 3.0, value=0.8, step=0.05, label="Label noise")
    test_frac = mo.ui.slider(0.1, 0.5, value=0.25, step=0.05, label="Test fraction")

    use_interactions = mo.ui.checkbox(value=True, label="Add interaction features")
    use_nonlinear = mo.ui.checkbox(value=True, label="Add non-linear features")

    lr = mo.ui.slider(0.01, 1.0, value=0.2, step=0.01, label="Training LR")
    l2 = mo.ui.slider(0.0, 1.0, value=0.05, step=0.01, label="L2")
    steps = mo.ui.slider(50, 2000, value=300, step=50, label="Training steps")
    threshold = mo.ui.slider(
        0.05, 0.95, value=0.5, step=0.01, label="Decision threshold"
    )

    controls = mo.ui.form(
        mo.vstack(
            [
                mo.hstack([seed, n_rows, n_features]),
                mo.hstack([noise, test_frac]),
                mo.hstack([use_interactions, use_nonlinear]),
                mo.hstack([lr, l2, steps, threshold]),
            ]
        ),
        submit_button_label="Recompute",
        show_clear_button=False,
    )

    controls
    return (
        controls,
        l2,
        lr,
        n_features,
        n_rows,
        noise,
        seed,
        steps,
        test_frac,
        threshold,
        use_interactions,
        use_nonlinear,
    )


@app.cell
def _(controls, math, np, pd):
    # Parameters only update when the form is submitted.
    params = controls.value

    rng = np.random.default_rng(int(params["Random seed"]))
    n = int(params["Rows"])
    d = int(params["Raw features"])
    label_noise = float(params["Label noise"])

    X_raw = rng.normal(size=(n, d))

    # Ground-truth weights + mild nonlinearity in the data generating process.
    w_true = rng.normal(size=(d,))
    z = X_raw @ w_true
    z = z + 0.25 * np.sin(X_raw[:, 0])
    z = z / (1.0 + label_noise)
    p = 1.0 / (1.0 + np.exp(-z))
    y = (rng.random(n) < p).astype(int)

    cols = [f"x{i:02d}" for i in range(d)]
    df = pd.DataFrame(X_raw, columns=cols)
    df["y"] = y

    df
    return X_raw, cols, df, d, n, rng, w_true, y


@app.cell
def _(controls, df, np, pd):
    params = controls.value
    add_interactions = bool(params["Add interaction features"])
    add_nonlinear = bool(params["Add non-linear features"])

    X = df.drop(columns=["y"]).to_numpy(dtype=float)

    feats: list[np.ndarray] = [X]
    feat_names = list(df.drop(columns=["y"]).columns)

    if add_nonlinear:
        feats.append(np.tanh(X))
        feat_names.extend([f"tanh({c})" for c in df.drop(columns=["y"]).columns])

    if add_interactions and X.shape[1] >= 2:
        inter = (X[:, 0] * X[:, 1]).reshape(-1, 1)
        feats.append(inter)
        feat_names.append(f"{df.columns[0]}*{df.columns[1]}")

    X_feat = np.concatenate(feats, axis=1)
    y = df["y"].to_numpy(dtype=int)

    feature_df = pd.DataFrame(X_feat, columns=feat_names)
    feature_df["y"] = y
    return X_feat, feat_names, feature_df, y


@app.cell
def _(controls, np, y):
    params = controls.value
    rng = np.random.default_rng(int(params["Random seed"]))
    test_frac = float(params["Test fraction"])

    n = y.shape[0]
    idx = rng.permutation(n)
    n_test = max(1, int(round(n * test_frac)))
    test_idx = idx[:n_test]
    train_idx = idx[n_test:]

    return n_test, test_idx, train_idx


@app.cell
def _(X_feat, np, train_idx, y):
    X_train = X_feat[train_idx]
    y_train = y[train_idx]

    mu, sigma = _standardize_fit(X_train)
    X_train_s = _standardize_apply(X_train, mu, sigma)

    return X_train_s, X_train, mu, sigma, y_train


@app.cell
def _(X_feat, np, sigma, test_idx, y, mu):
    X_test = X_feat[test_idx]
    y_test = y[test_idx]
    X_test_s = _standardize_apply(X_test, mu, sigma)
    return X_test_s, X_test, y_test


@app.cell
def _(X_train_s, controls, np, y_train):
    params = controls.value
    w, b = _train_logreg_gd(
        X=X_train_s,
        y=y_train.astype(float),
        lr=float(params["Training LR"]),
        l2=float(params["L2"]),
        steps=int(params["Training steps"]),
        seed=int(params["Random seed"]) + 123,
    )
    return b, w


@app.cell
def _(X_test_s, b, controls, np, test_idx, train_idx, w, y_test, y_train):
    params = controls.value
    thr = float(params["Decision threshold"])

    p_test = _predict_proba(X_test_s, w=w, b=b)
    metrics = Metrics(
        n_train=int(train_idx.shape[0]),
        n_test=int(test_idx.shape[0]),
        accuracy=_accuracy(y_test, p_test, threshold=thr),
        log_loss=_log_loss(y_test.astype(float), p_test),
        brier=_brier(y_test.astype(float), p_test),
        threshold=thr,
    )
    return metrics, p_test, thr


@app.cell
def _(metrics, mo):
    mo.md("## Evaluation")
    mo.hstack(
        [
            mo.stat("Train rows", f"{metrics.n_train:,}"),
            mo.stat("Test rows", f"{metrics.n_test:,}"),
            mo.stat("Accuracy", f"{metrics.accuracy:.3f}"),
            mo.stat("Log loss", f"{metrics.log_loss:.3f}"),
            mo.stat("Brier", f"{metrics.brier:.3f}"),
            mo.stat("Threshold", f"{metrics.threshold:.2f}"),
        ]
    )
    return


@app.cell
def _(feature_df, mo, p_test, test_idx):
    mo.md("## Quick validation")

    # Show a small slice of test rows with predicted probabilities.
    preview = feature_df.iloc[test_idx].copy()
    preview.insert(0, "p_hat", p_test)
    preview = preview.sort_values("p_hat", ascending=False)
    mo.ui.table(preview.head(50))
    return preview


@app.cell
def _(mo, np, p_test, y_test):
    mo.md("## Calibration snapshot")

    # Simple 10-bin calibration table.
    bins = np.linspace(0.0, 1.0, 11)
    b = np.digitize(p_test, bins) - 1

    rows = []
    for i in range(10):
        mask = b == i
        if not mask.any():
            continue
        rows.append(
            {
                "bin": f"[{bins[i]:.1f}, {bins[i + 1]:.1f})",
                "n": int(mask.sum()),
                "mean_p": float(p_test[mask].mean()),
                "emp_rate": float(y_test[mask].mean()),
            }
        )

    mo.ui.table(rows)
    return b, bins, rows


@app.cell
def _(feature_df, mo):
    mo.md(
        """
        ## Next steps

        Replace the dummy pieces with your real pipeline:

        - Load from SQLite (DuckDB/sqlite3) and/or read Parquet (polars/pyarrow)
        - Implement your feature transforms in pure functions in `src/` and import them
        - Swap the toy model for your actual inference (e.g. a saved model artifact)
        - Add evaluation suites (slice metrics, regression tests, goldens)
        """
    )
    return


if __name__ == "__main__":
    app.run()
