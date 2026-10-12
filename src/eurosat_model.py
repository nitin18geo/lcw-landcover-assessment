"""EuroSAT ViT classifier: input preparation, inference with raw-response logging,
and aggregation of the 10 EuroSAT probabilities into the project's classes.

Pipeline per cell:
  native 50x50 RGB chip (10 m)  --bilinear-->  64x64 (EuroSAT patch size)
  --> HF ViTImageProcessor (bilinear -> 224x224, rescale 1/255, normalise mean 0.5 / std 0.5)
  --> ViT softmax over 10 EuroSAT classes  --> sum into project classes via crosswalk
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

_RESAMPLE = {"nearest": Image.NEAREST, "bilinear": Image.BILINEAR, "bicubic": Image.BICUBIC}


def load_classifier(model_id: str, revision: str | None = None, device: int = -1):
    """HF image-classification pipeline, pinned to a commit for reproducibility."""
    from transformers import pipeline
    clf = pipeline("image-classification", model=model_id, revision=revision, device=device)
    labels = [clf.model.config.id2label[i] for i in range(clf.model.config.num_labels)]
    print(f"Loaded {model_id} @ {revision or 'latest'} | {len(labels)} labels: {labels}")
    return clf


def prepare_input(native_png: Path, out_png: Path, size_px: int, resample: str) -> Image.Image:
    """Resize the native-resolution cell chip to the model input size and save the
    exact image that is fed to the model (lossless PNG)."""
    im = Image.open(native_png).convert("RGB")
    if im.size != (size_px, size_px):
        im = im.resize((size_px, size_px), _RESAMPLE[resample])
    im.save(out_png)
    return im


def classify_cells(clf, inputs: dict[str, Image.Image], raw_dir: Path, top_k: int,
                   run_info: dict) -> pd.DataFrame:
    """Run the model on every cell; write one raw JSON per cell, unedited, and
    return a wide table of EuroSAT probabilities (one row per cell)."""
    raw_dir = Path(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    ids = list(inputs)
    preds = clf([inputs[i] for i in ids], top_k=top_k)
    rows = []
    for cid, p in zip(ids, preds):
        record = {"cell_id": cid,
                  "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                  **run_info, "predictions": p}
        (raw_dir / f"{cid}.json").write_text(json.dumps(record, indent=2))
        rows.append({"cell_id": cid, **{f"p_{d['label']}": d["score"] for d in p}})
    df = pd.DataFrame(rows)
    # fixed, alphabetical column order (pipeline output is sorted by score per cell)
    return df[["cell_id"] + sorted(c for c in df.columns if c.startswith("p_"))]


def aggregate_to_classes(probs: pd.DataFrame, crosswalk: dict, classes: list[str],
                         threshold: float) -> pd.DataFrame:
    """Sum EuroSAT probabilities into project classes and derive the cell label
    and uncertainty measures.

    method_label       argmax of the summed class probabilities
    method_top_eurosat argmax over the 10 raw EuroSAT classes (kept for tracing)
    method_max_prob    probability of method_label
    method_margin      max minus second-highest summed probability
    method_entropy     normalised Shannon entropy of the summed vector (0 = certain, 1 = uniform)
    method_uncertain   method_max_prob < threshold
    """
    out = probs[["cell_id"]].copy()
    eu_cols = [c for c in probs.columns if c.startswith("p_")]
    for k in classes:
        src = [f"p_{e}" for e, tgt in crosswalk.items() if tgt == k]
        out[f"prob_{k}"] = probs[src].sum(axis=1) if src else 0.0
    P = out[[f"prob_{k}" for k in classes]].to_numpy()
    srt = np.sort(P, axis=1)
    out["method_label"] = [classes[i] for i in P.argmax(axis=1)]
    out["method_top_eurosat"] = probs[eu_cols].idxmax(axis=1).str[2:]
    out["method_max_prob"] = srt[:, -1].round(4)
    out["method_margin"] = (srt[:, -1] - srt[:, -2]).round(4)
    with np.errstate(divide="ignore", invalid="ignore"):
        ent = -np.nansum(np.where(P > 0, P * np.log(P), 0), axis=1) / np.log(len(classes))
    out["method_entropy"] = ent.round(4)
    out["method_uncertain"] = out["method_max_prob"] < threshold
    return out
