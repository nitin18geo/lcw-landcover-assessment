"""Comparator products: Dynamic World V1 (seasonal, 10 m) and CGLS-LC100 C3 (2019, 100 m).

Earth Engine side: build the seasonal DW aggregate and the CGLS image.
Download side: fetch on the analysis grid (10 m, via gee_utils.fetch_grid_array) and,
for CGLS, also on its own native 100 m grid. GeoTIFF writing for an arbitrary affine.
"""
from __future__ import annotations

import math
from pathlib import Path

import ee
import numpy as np
import pandas as pd
import rasterio
from affine import Affine


# ===================================================================== Dynamic World
def dw_collection(aoi, start, end, collection, scene_ids=None,
                  cs_collection=None, cs_band=None, cs_threshold=None):
    """DW images over the AOI and season.

    scene_ids     : if given, keep only DW images whose system:index (= source S2 L1C
                    scene ID) is in this list -> same imagery as the S2 composite.
    cs_collection : if given, apply the same Cloud Score+ mask as the S2 composite
                    (on top of DW's own cloud/shadow mask)."""
    dw = ee.ImageCollection(collection).filterBounds(aoi).filterDate(start, end)
    if scene_ids is not None:
        dw = dw.filter(ee.Filter.inList("system:index", list(scene_ids)))
    if cs_collection:
        dw = (dw.linkCollection(ee.ImageCollection(cs_collection), [cs_band])
                .map(lambda img: img.updateMask(img.select(cs_band).gte(cs_threshold))))
    return dw


def dw_inventory(dw: ee.ImageCollection) -> pd.DataFrame:
    d = ee.Dictionary({
        "system_index": dw.aggregate_array("system:index"),
        "time_start": dw.aggregate_array("system:time_start"),
        "dw_algorithm_version": dw.aggregate_array("dynamicworld_algorithm_version"),
        "qa_algorithm_version": dw.aggregate_array("qa_algorithm_version"),
    }).getInfo()
    df = pd.DataFrame(d)
    if not df.empty:
        df["date"] = pd.to_datetime(df["time_start"], unit="ms").dt.date.astype(str)
        df = df.drop(columns="time_start").sort_values("date").reset_index(drop=True)
    return df


def dw_seasonal(dw: ee.ImageCollection, class_names: list[str], method: str) -> ee.Image:
    """Per-pixel seasonal aggregate. Returns an image with bands:
      sup_<class> x 9 : class support in [0, 1], summing to 1 where valid
                        (mode: share of observations labelled <class>;
                         mean/median: aggregated probability)
      label_agg       : argmax of support (DW class index 0-8)
      conf_agg        : max support (mode: share of obs agreeing with the mode)
      n_obs           : number of valid DW observations at the pixel
    """
    if method == "mode":
        lab = dw.select("label")
        support = ee.Image.cat([
            lab.map(lambda img, k=k: img.eq(k).rename("s")).mean().rename(f"sup_{name}")
            for k, name in enumerate(class_names)])
    elif method == "mean":
        support = dw.select(class_names).mean().rename([f"sup_{n}" for n in class_names])
    elif method == "median":
        med = dw.select(class_names).median()
        support = med.divide(med.reduce(ee.Reducer.sum())).rename([f"sup_{n}" for n in class_names])
    else:
        raise ValueError(f"Unknown DW aggregation: {method}")

    label = support.toArray().arrayArgmax().arrayGet([0]).rename("label_agg")
    conf = support.reduce(ee.Reducer.max()).rename("conf_agg")
    n_obs = dw.select("label").count().rename("n_obs")
    return support.addBands([label, conf, n_obs.unmask(0)])


# ===================================================================== CGLS-LC100
def cgls_image(image_id: str, bands: list[str]) -> tuple[ee.Image, list[str]]:
    """CGLS-LC100 image restricted to the requested bands that actually exist."""
    img = ee.Image(image_id)
    available = img.bandNames().getInfo()
    use = [b for b in bands if b in available]
    missing = sorted(set(bands) - set(use))
    if missing:
        print("CGLS bands not found and skipped:", missing)
    return img.select(use), use


def fetch_native_array(image: ee.Image, bounds_lonlat: tuple, nodata: float):
    """Download `image` on its OWN native pixel grid, covering the AOI bounds
    (lon_min, lat_min, lon_max, lat_max). Returns (array[H, W, B], band_names, Affine, crs)."""
    proj = image.select(0).projection().getInfo()
    crs = proj["crs"]
    sx, shx, tx, shy, sy, ty = proj["transform"]
    assert shx == 0 and shy == 0 and sy < 0, f"Unexpected native transform {proj}"
    lon0, lat0, lon1, lat1 = bounds_lonlat
    c0 = math.floor((lon0 - tx) / sx)
    c1 = math.ceil((lon1 - tx) / sx)
    r0 = math.floor((lat1 - ty) / sy)
    r1 = math.ceil((lat0 - ty) / sy)
    width, height = c1 - c0, r1 - r0
    x_origin, y_origin = tx + c0 * sx, ty + r0 * sy
    request = {
        "expression": image.toFloat().unmask(nodata),
        "fileFormat": "NUMPY_NDARRAY",
        "grid": {"dimensions": {"width": width, "height": height},
                 "affineTransform": {"scaleX": sx, "shearX": 0, "translateX": x_origin,
                                     "shearY": 0, "scaleY": sy, "translateY": y_origin},
                 "crsCode": crs},
    }
    arr = ee.data.computePixels(request)
    names = list(arr.dtype.names)
    stack = np.stack([arr[n] for n in names], axis=-1).astype("float32")
    return stack, names, Affine(sx, 0, x_origin, 0, sy, y_origin), crs


# ===================================================================== I/O
def write_geotiff_affine(arr, band_names, transform: Affine, crs: str, path: Path, nodata: float):
    """GeoTIFF writer for any affine/CRS (used for the native 100 m CGLS raster)."""
    with rasterio.open(path, "w", driver="GTiff", height=arr.shape[0], width=arr.shape[1],
                       count=arr.shape[2], dtype=arr.dtype, crs=crs, transform=transform,
                       nodata=nodata, compress="deflate") as dst:
        for i, name in enumerate(band_names, start=1):
            dst.write(arr[:, :, i - 1], i)
            dst.set_band_description(i, name)
    return Path(path)
