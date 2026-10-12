"""Earth Engine helpers: authentication, cloud-screened Sentinel-2 composite,
image inventory, and pixel download aligned exactly to the analysis grid."""
from __future__ import annotations

import ee
import numpy as np
import pandas as pd


# ---------------------------------------------------------------- auth
def init_ee(project: str, force_auth: bool = False) -> None:
    """Initialise Earth Engine against a Cloud project. Authenticates only if
    no valid credentials are cached (or force_auth=True). In Colab,
    ee.Authenticate() opens the Colab auth flow automatically."""
    if not project or project == "your-gcp-project-id":
        raise ValueError("Set EE_PROJECT (env var or config.py) to your Earth Engine Cloud project ID")
    if force_auth:
        ee.Authenticate(force=True)
    try:
        ee.Initialize(project=project)
    except Exception:
        ee.Authenticate()
        ee.Initialize(project=project)
    print(f"Earth Engine initialised | project={project} | ee {ee.__version__}")


def aoi_rectangle(spec: dict) -> ee.Geometry:
    """Planar rectangle in the grid's UTM CRS (identical footprint to the GeoJSON)."""
    return ee.Geometry.Rectangle(
        [spec["x_min"], spec["y_min"], spec["x_max"], spec["y_max"]],
        spec["crs"], False)


# ---------------------------------------------------------------- Sentinel-2
def s2_cloud_screened(aoi, start, end, collection, max_scene_cloud,
                      cs_collection, cs_band, cs_threshold, platforms=None):
    """Return (raw filtered collection, cloud-masked collection).

    Optional platform filter on SPACECRAFT_NAME (e.g. ['Sentinel-2A']), a scene
    pre-filter on CLOUDY_PIXEL_PERCENTAGE, then per-pixel masking with
    Cloud Score+ (pixels kept where cs_band >= cs_threshold)."""
    raw = (ee.ImageCollection(collection)
           .filterBounds(aoi)
           .filterDate(start, end)
           .filter(ee.Filter.lte("CLOUDY_PIXEL_PERCENTAGE", max_scene_cloud)))
    if platforms:
        raw = raw.filter(ee.Filter.inList("SPACECRAFT_NAME", list(platforms)))
    linked = raw.linkCollection(ee.ImageCollection(cs_collection), [cs_band])
    masked = linked.map(lambda img: img.updateMask(img.select(cs_band).gte(cs_threshold)))
    return raw, masked


def image_inventory(coll: ee.ImageCollection) -> pd.DataFrame:
    """One row per scene used: ID, date, tile, platform, scene cloud %."""
    props = {
        "system_index": "system:index",
        "time_start": "system:time_start",
        "mgrs_tile": "MGRS_TILE",
        "spacecraft": "SPACECRAFT_NAME",
        "cloudy_pixel_pct": "CLOUDY_PIXEL_PERCENTAGE",
        "processing_baseline": "PROCESSING_BASELINE",
    }
    d = ee.Dictionary({k: coll.aggregate_array(v) for k, v in props.items()}).getInfo()
    df = pd.DataFrame(d)
    if not df.empty:
        df["date"] = pd.to_datetime(df["time_start"], unit="ms").dt.date.astype(str)
        df = df.drop(columns="time_start").sort_values("date").reset_index(drop=True)
    return df


def median_composite(masked: ee.ImageCollection, bands: list[str]) -> ee.Image:
    return masked.select(bands).median()


def obs_count_images(raw: ee.ImageCollection, masked: ee.ImageCollection, ref_band="B4") -> ee.Image:
    """Per-pixel counts: all observations vs. clear (unmasked) observations.
    These become the valid-data counts reported per cell."""
    total = raw.select(ref_band).count().rename("obs_total")
    clear = masked.select(ref_band).count().rename("obs_clear")
    return total.addBands(clear).unmask(0)


# ---------------------------------------------------------------- download
def fetch_grid_array(image: ee.Image, spec: dict, nodata: float):
    """Download `image` on exactly the grid's pixel lattice via computePixels.

    Returns (array[H, W, B] float32, band_names). Masked pixels -> nodata.
    No reprojection guesswork: the affine transform is the grid's own."""
    img = image.toFloat().unmask(nodata)
    request = {
        "expression": img,
        "fileFormat": "NUMPY_NDARRAY",
        "grid": {
            "dimensions": {"width": spec["width_px"], "height": spec["height_px"]},
            "affineTransform": {
                "scaleX": spec["pixel_m"], "shearX": 0, "translateX": spec["x_min"],
                "shearY": 0, "scaleY": -spec["pixel_m"], "translateY": spec["y_max"],
            },
            "crsCode": spec["crs"],
        },
    }
    arr = ee.data.computePixels(request)
    names = list(arr.dtype.names)
    stack = np.stack([arr[n] for n in names], axis=-1).astype("float32")
    return stack, names
