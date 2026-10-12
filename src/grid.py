"""Fixed 3 x 4 analysis grid, built in metric UTM so every cell is exactly
CELL_SIZE_M per side and aligned to the 10 m Sentinel-2 pixel grid."""
from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
from pyproj import Transformer
from shapely.geometry import box


def utm_epsg(lon: float, lat: float) -> int:
    zone = int((lon + 180) // 6) + 1
    return (32600 if lat >= 0 else 32700) + zone


def build_grid(center_lon: float, center_lat: float, rows: int, cols: int,
               cell_m: int, pixel_m: int, id_fmt: str = "r{row}c{col}"):
    """Return (cells GeoDataFrame in UTM, grid_spec dict).

    The north-west corner is snapped to a multiple of `pixel_m`, so cell edges
    fall exactly on pixel edges (no partial pixels inside a cell).
    Row 1 is the northernmost row; column 1 is the westernmost column."""
    epsg = utm_epsg(center_lon, center_lat)
    to_utm = Transformer.from_crs(4326, epsg, always_xy=True)
    cx, cy = to_utm.transform(center_lon, center_lat)

    width_m, height_m = cols * cell_m, rows * cell_m
    x_min = round((cx - width_m / 2) / pixel_m) * pixel_m
    y_max = round((cy + height_m / 2) / pixel_m) * pixel_m
    px_per_cell = cell_m // pixel_m

    recs = []
    for r in range(rows):
        for c in range(cols):
            x0 = x_min + c * cell_m
            y1 = y_max - r * cell_m
            recs.append({
                "cell_id": id_fmt.format(row=r + 1, col=c + 1),
                "row": r + 1,
                "col": c + 1,
                # pixel window into the AOI array (row = y, col = x; origin top-left)
                "px_row0": r * px_per_cell, "px_row1": (r + 1) * px_per_cell,
                "px_col0": c * px_per_cell, "px_col1": (c + 1) * px_per_cell,
                "geometry": box(x0, y1 - cell_m, x0 + cell_m, y1),
            })
    cells = gpd.GeoDataFrame(recs, crs=f"EPSG:{epsg}")
    cells["area_m2"] = cells.geometry.area

    spec = {
        "crs": f"EPSG:{epsg}",
        "x_min": x_min, "y_max": y_max,
        "x_max": x_min + width_m, "y_min": y_max - height_m,
        "width_px": width_m // pixel_m, "height_px": height_m // pixel_m,
        "pixel_m": pixel_m, "cell_m": cell_m, "rows": rows, "cols": cols,
        "center_lonlat_requested": [center_lon, center_lat],
    }
    return cells, spec


def to_wgs84_with_centroids(cells_utm: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Reproject to EPSG:4326 (RFC 7946 GeoJSON) and add centroid lon/lat
    (centroid computed in UTM, then transformed)."""
    cent = cells_utm.geometry.centroid.to_crs(4326)
    out = cells_utm.to_crs(4326)
    out["centroid_lon"] = cent.x.round(6)
    out["centroid_lat"] = cent.y.round(6)
    return out


def save_geojson(gdf: gpd.GeoDataFrame, path: Path, properties: dict | None = None):
    """Write GeoJSON; optional top-level properties (e.g. AOI name, dates) are
    added as a 'metadata' member so the file is self-describing."""
    path = Path(path)
    gdf.to_file(path, driver="GeoJSON")
    if properties:
        fc = json.loads(path.read_text())
        fc["metadata"] = properties
        path.write_text(json.dumps(fc, indent=2))
    return path
