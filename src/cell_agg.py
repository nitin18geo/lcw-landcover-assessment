"""Pixel -> cell aggregation, crosswalks and agreement statistics.

Conventions for crosswalked class arrays:
    0..K-1 : index into the project class list
    -1     : unmapped (product class with crosswalk value None, e.g. snow, CGLS 'unknown')
    -2     : no data (masked / no valid observation)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

UNMAPPED, NODATA_CLS = -1, -2


def crosswalk_codes(codes: np.ndarray, code_to_class: dict, classes: list[str], nodata: float) -> np.ndarray:
    """Map product class codes to project class indices (see module conventions)."""
    out = np.full(codes.shape, UNMAPPED, dtype=np.int16)
    out[codes == nodata] = NODATA_CLS
    for code, cls in code_to_class.items():
        if cls is not None:
            out[codes == code] = classes.index(cls)
    return out


def crosswalk_support(support: np.ndarray, product_names: list[str], name_to_class: dict,
                      classes: list[str], nodata: float) -> np.ndarray:
    """Sum per-pixel product-class support [H, W, n_product] into project classes [H, W, K].
    Nodata pixels become NaN."""
    H, W, _ = support.shape
    out = np.zeros((H, W, len(classes)), dtype="float32")
    for j, name in enumerate(product_names):
        cls = name_to_class.get(name)
        if cls is not None:
            out[..., classes.index(cls)] += support[..., j]
    out[np.any(support == nodata, axis=-1)] = np.nan
    return out


def cell_majority(cls_arr: np.ndarray, cells, classes: list[str], threshold: float,
                  prefix: str, mixed_label: str = "mixed") -> pd.DataFrame:
    """Majority rule per cell over valid (mapped) pixels.

    <prefix>_label        plurality class (largest share of valid pixels)
    <prefix>_top_frac     share of valid pixels in that class
    <prefix>_second       runner-up class, <prefix>_second_frac its share
    <prefix>_label_strict class if top_frac >= threshold (true majority), else `mixed`
    <prefix>_frac_<class> share of each class (denominator = n_valid_px)
    <prefix>_n_valid_px / _n_unmapped_px / _n_nodata_px / _n_px : pixel accounting
    """
    rows = []
    for _, c in cells.iterrows():
        w = cls_arr[c.px_row0:c.px_row1, c.px_col0:c.px_col1]
        valid = w >= 0
        n_valid = int(valid.sum())
        counts = np.bincount(w[valid].ravel(), minlength=len(classes)) if n_valid else np.zeros(len(classes))
        fr = counts / n_valid if n_valid else np.full(len(classes), np.nan)
        rec = {"cell_id": c.cell_id,
               f"{prefix}_n_px": int(w.size),
               f"{prefix}_n_valid_px": n_valid,
               f"{prefix}_n_unmapped_px": int((w == UNMAPPED).sum()),
               f"{prefix}_n_nodata_px": int((w == NODATA_CLS).sum())}
        if n_valid:
            order = np.argsort(-fr, kind="stable")
            top, sec = order[0], order[1]
            rec.update({f"{prefix}_label": classes[top], f"{prefix}_top_frac": round(float(fr[top]), 4),
                        f"{prefix}_second": classes[sec] if fr[sec] > 0 else "",
                        f"{prefix}_second_frac": round(float(fr[sec]), 4),
                        f"{prefix}_label_strict": classes[top] if fr[top] >= threshold else mixed_label})
        else:
            rec.update({f"{prefix}_label": "", f"{prefix}_top_frac": np.nan, f"{prefix}_second": "",
                        f"{prefix}_second_frac": np.nan, f"{prefix}_label_strict": ""})
        rec.update({f"{prefix}_frac_{k}": round(float(v), 4) for k, v in zip(classes, fr)})
        rows.append(rec)
    return pd.DataFrame(rows)


def cell_band_stats(arr: np.ndarray, cells, band_idx: int, nodata: float, name: str,
                    stats=("median", "mean", "min")) -> pd.DataFrame:
    """Per-cell summary of one raster band, ignoring nodata."""
    rows = []
    for _, c in cells.iterrows():
        v = arr[c.px_row0:c.px_row1, c.px_col0:c.px_col1, band_idx]
        v = v[v != nodata]
        rec = {"cell_id": c.cell_id}
        for s in stats:
            rec[f"{name}_{s}"] = round(float(getattr(np, s)(v)), 4) if v.size else np.nan
        rows.append(rec)
    return pd.DataFrame(rows)


def cell_mean_support(sup: np.ndarray, cells, classes: list[str], prefix: str) -> pd.DataFrame:
    """Cell mean of per-pixel crosswalked support (NaN pixels ignored)."""
    rows = []
    for _, c in cells.iterrows():
        w = sup[c.px_row0:c.px_row1, c.px_col0:c.px_col1].reshape(-1, len(classes))
        m = np.nanmean(w, axis=0) if np.isfinite(w).any() else np.full(len(classes), np.nan)
        rows.append({"cell_id": c.cell_id, **{f"{prefix}_meanprob_{k}": round(float(v), 4)
                                             for k, v in zip(classes, m)}})
    return pd.DataFrame(rows)


def count_points_in_cells(xs: np.ndarray, ys: np.ndarray, cells_same_crs) -> pd.Series:
    """Count points (e.g. native 100 m pixel centres) falling inside each cell polygon."""
    import shapely
    return pd.Series({c.cell_id: int(shapely.contains_xy(c.geometry, xs, ys).sum())
                      for _, c in cells_same_crs.iterrows()})


def pairwise_agreement(df: pd.DataFrame, pairs: list[tuple[str, str]], scope: str) -> pd.DataFrame:
    """Cell-level label agreement with explicit denominators.
    A cell enters the denominator only if both labels are present and non-empty."""
    rows = []
    for a, b in pairs:
        ok = df[a].fillna("").ne("") & df[b].fillna("").ne("")
        sub = df[ok]
        agree = sub[a] == sub[b]
        rows.append({"scope": scope, "label_a": a, "label_b": b,
                     "n_agree": int(agree.sum()), "n_compared": int(len(sub)),
                     "n_excluded": int((~ok).sum()),
                     "pct_agree": round(100 * agree.mean(), 1) if len(sub) else np.nan,
                     "agree_cells": ",".join(sub.loc[agree, "cell_id"]),
                     "disagree_cells": ",".join(sub.loc[~agree, "cell_id"])})
    return pd.DataFrame(rows)
