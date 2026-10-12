"""RGB rendering: one fixed stretch for the whole AOI, per-cell PNG chips at
300 DPI, a GeoTIFF writer, and the overview panel for the report."""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from PIL import Image
from rasterio.transform import from_origin


def stretch_rgb(rgb: np.ndarray, vmin: float, vmax: float, gamma: float, nodata: float):
    """Linear stretch DN -> uint8 with optional gamma. The same vmin/vmax is used
    for every cell so chips are visually comparable. Nodata -> black."""
    nod = np.any(rgb == nodata, axis=-1)
    x = np.clip((rgb - vmin) / (vmax - vmin), 0, 1) ** (1.0 / gamma)
    out = (x * 255).round().astype("uint8")
    out[nod] = 0
    return out, int(nod.sum())


def save_png(rgb8: np.ndarray, path: Path, dpi: int, upscale: int = 1) -> Path:
    """Save uint8 RGB as PNG with DPI metadata. Upscaling is nearest-neighbour
    only (each 10 m pixel becomes an upscale x upscale block)."""
    im = Image.fromarray(rgb8, mode="RGB")
    if upscale > 1:
        im = im.resize((im.width * upscale, im.height * upscale), Image.NEAREST)
    im.save(path, dpi=(dpi, dpi))
    return Path(path)


def write_geotiff(arr: np.ndarray, band_names: list[str], spec: dict, path: Path, nodata: float):
    """Write array[H, W, B] as a GeoTIFF on the grid's CRS and transform."""
    transform = from_origin(spec["x_min"], spec["y_max"], spec["pixel_m"], spec["pixel_m"])
    with rasterio.open(path, "w", driver="GTiff", height=arr.shape[0], width=arr.shape[1],
                       count=arr.shape[2], dtype=arr.dtype, crs=spec["crs"],
                       transform=transform, nodata=nodata, compress="deflate") as dst:
        for i, name in enumerate(band_names, start=1):
            dst.write(arr[:, :, i - 1], i)
            dst.set_band_description(i, name)
    return Path(path)


def overview_panel(rgb8: np.ndarray, cells, spec: dict, path: Path, dpi: int,
                   title: str = "", highlight: list[str] | None = None):
    """Full-AOI RGB with the 3 x 4 grid and cell IDs drawn on top.
    Cells in `highlight` (e.g. the six visual-label cells) get a thicker yellow outline."""
    highlight = set(highlight or [])
    h, w = rgb8.shape[:2]
    fig, ax = plt.subplots(figsize=(w / h * 5 + 0.5, 5.4))
    ext = [spec["x_min"], spec["x_max"], spec["y_min"], spec["y_max"]]
    ax.imshow(rgb8, extent=ext, interpolation="nearest")
    for _, c in cells.iterrows():
        x, y = c.geometry.exterior.xy
        hl = c["cell_id"] in highlight
        ax.plot(x, y, color="#ffd400" if hl else "white", lw=2.2 if hl else 0.9)
        cx, cy = c.geometry.centroid.x, c.geometry.centroid.y
        ax.text(cx, cy, c["cell_id"], color="white", ha="center", va="center", fontsize=10,
                weight="bold", bbox=dict(facecolor="black", alpha=0.45, lw=0, pad=1.5))
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_title(title, fontsize=10)
    # 500 m scale bar
    sb_x, sb_y = spec["x_min"] + 60, spec["y_min"] + 60
    ax.plot([sb_x, sb_x + spec["cell_m"]], [sb_y, sb_y], color="white", lw=3)
    ax.text(sb_x + spec["cell_m"] / 2, sb_y + 40, f'{spec["cell_m"]} m', color="white",
            ha="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    return Path(path)


def chip_mosaic(chip_paths: dict, rows: int, cols: int, path: Path, dpi: int, title: str = ""):
    """3 x 4 mosaic of the individual chips, labelled by cell ID."""
    fig, axes = plt.subplots(rows, cols, figsize=(cols * 2.2, rows * 2.4))
    for ax, (cid, p) in zip(axes.ravel(), chip_paths.items()):
        ax.imshow(Image.open(p), interpolation="nearest")
        ax.set_title(cid, fontsize=9)
        ax.set_xticks([]); ax.set_yticks([])
    fig.suptitle(title, fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    return Path(path)


def comparison_panel(rgb8, class_maps: dict, eurosat_labels, cells, spec, classes, colors, path, dpi):
    """2 x 2 panel: RGB composite | each comparator's crosswalked 10 m class map | EuroSAT cell labels.
    class_maps: {title: (class_index_array, Series cell_id -> cell label)}.
    Unmapped pixels light grey, no-data white. Cell labels printed on each panel."""
    from matplotlib.colors import ListedColormap
    from matplotlib.patches import Patch
    cmap = ListedColormap(["#ffffff", "#d0d0d0"] + [colors[k] for k in classes])   # -2, -1, 0..K-1
    ext = [spec["x_min"], spec["x_max"], spec["y_min"], spec["y_max"]]

    def grid(ax, labels=None):
        for _, c in cells.iterrows():
            x, y = c.geometry.exterior.xy
            ax.plot(x, y, color="black", lw=0.7)
            txt = c["cell_id"] + (f"\n{labels.get(c['cell_id'], '')}" if labels is not None else "")
            ax.text(c.geometry.centroid.x, c.geometry.centroid.y, txt, ha="center", va="center",
                    fontsize=6.5, bbox=dict(facecolor="white", alpha=0.7, lw=0, pad=1))
        ax.set_xticks([]); ax.set_yticks([])

    fig, axes = plt.subplots(2, 2, figsize=(11, 8.6))
    axes = axes.ravel()
    axes[0].imshow(rgb8, extent=ext, interpolation="nearest"); grid(axes[0]); axes[0].set_title("Sentinel-2A composite (RGB)", fontsize=9)
    for ax, (title, (arr, lab)) in zip(axes[1:3], class_maps.items()):
        ax.imshow(arr + 2, extent=ext, cmap=cmap, vmin=0, vmax=len(classes) + 1, interpolation="nearest")
        grid(ax, lab.to_dict()); ax.set_title(title, fontsize=9)
    eu = np.full((spec["height_px"], spec["width_px"]), -2, dtype=int)
    for _, c in cells.iterrows():
        lab = eurosat_labels.get(c["cell_id"], "")
        eu[c.px_row0:c.px_row1, c.px_col0:c.px_col1] = classes.index(lab) if lab in classes else -1
    axes[3].imshow(eu + 2, extent=ext, cmap=cmap, vmin=0, vmax=len(classes) + 1, interpolation="nearest")
    grid(axes[3], eurosat_labels.to_dict()); axes[3].set_title("EuroSAT ViT (one label per cell)", fontsize=9)
    handles = [Patch(color=colors[k], label=k) for k in classes] + [Patch(color="#d0d0d0", label="unmapped"),
                                                                     Patch(facecolor="#ffffff", edgecolor="grey", label="no data")]
    fig.legend(handles=handles, loc="lower center", ncol=len(handles), fontsize=8, frameon=False)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    return Path(path)
