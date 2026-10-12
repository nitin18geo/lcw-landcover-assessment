"""
config.py — single source of truth for every global variable and setting.

Every notebook and module imports from here; nothing below is redefined
elsewhere. Change a value here, rerun, and the change is traceable in git.

Values marked  # >>> CONFIRM  are decisions still to be confirmed.
"""
from pathlib import Path
import os

# ---------------------------------------------------------------------------
# 0. Repository paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent
OUT = ROOT / "outputs"

PATHS = {
    "geojson":        OUT / "geojson",
    "chips_rgb":      OUT / "chips" / "rgb",          # upscaled PNG chips for viewing / the doc
    "chips_native":   OUT / "chips" / "rgb_native",   # 10 m native-pixel PNG chips (50 x 50 px)
    "rasters":        OUT / "rasters",
    "figures":        OUT / "figures",
    "metadata":       OUT / "metadata",
    "labels":         OUT / "labels",
    "model_raw":      OUT / "model_responses" / "raw",
    "comparators":    OUT / "comparators",
    "runs_baseline":  OUT / "runs" / "baseline",
    "runs_sensitivity": OUT / "runs" / "sensitivity",
    "tables":         OUT / "tables",
    "model_inputs":   OUT / "model_inputs",           # exact images fed to the classifier
    "docs":           ROOT / "docs",
}
for _p in PATHS.values():
    _p.mkdir(parents=True, exist_ok=True)

REQUIREMENTS_FILE = ROOT / "requirements.txt"

# ---------------------------------------------------------------------------
# 1. Google Earth Engine
# ---------------------------------------------------------------------------

# Read from the environment first so the project ID never has to be committed.
EE_PROJECT = "ee-nitinsharma"
# ---------------------------------------------------------------------------
# 2. Area of interest and grid
# ---------------------------------------------------------------------------
AOI_NAME = "placeholder_site"                                     # >>> CONFIRM
AOI_DESCRIPTION = "Near Dhamtari district, Chhattisgarh"  # >>> CONFIRM
# Centre of the AOI (lon, lat, WGS84). The grid is built around this point.
AOI_CENTER_LONLAT = (81.525026 , 20.703383)                         # >>> CONFIRM

GRID_ROWS = 3          # rows run north -> south  (r1 = northernmost)
GRID_COLS = 4          # columns run west -> east (c1 = westernmost)
CELL_SIZE_M = 500      # metres per side
CELL_ID_FMT = "r{row}c{col}"   # e.g. r1c1 ... r3c4

PIXEL_SIZE_M = 10      # Sentinel-2 native resolution for B2/B3/B4/B8
MAX_AOI_AREA_KM2 = 4.0 # assessment limit

# Sanity checks enforced at import time
_area_km2 = GRID_ROWS * GRID_COLS * CELL_SIZE_M ** 2 / 1e6
assert GRID_ROWS * GRID_COLS == 12, "Assessment requires a fixed 3 x 4 grid of 12 cells"
assert 250 <= CELL_SIZE_M <= 500, "Cells must be roughly 250-500 m per side"
assert _area_km2 <= MAX_AOI_AREA_KM2, f"AOI {_area_km2} km2 exceeds {MAX_AOI_AREA_KM2} km2"
assert CELL_SIZE_M % PIXEL_SIZE_M == 0, "Cell size must be a whole number of pixels"
AOI_AREA_KM2 = _area_km2

# ---------------------------------------------------------------------------
# 3. Sentinel-2 imagery window and cloud screening
# ---------------------------------------------------------------------------
# One season drives EVERYTHING date-related: the Sentinel-2 composite (Part 1), the EuroSAT
# input (Part 2) and the Dynamic World window (Part 2). Change these two numbers to change
# the window for all of them at once (e.g. for the date-window sensitivity test).
YEAR = 2019
SEASON_START_MONTH = 1         # inclusive, 1-12                            # >>> CONFIRM
SEASON_END_MONTH = 3           # inclusive, 1-12 (same calendar year)      # >>> CONFIRM
assert 1 <= SEASON_START_MONTH <= SEASON_END_MONTH <= 12, \
    "Season must lie within one calendar year (start <= end)"

S2_START = f"{YEAR}-{SEASON_START_MONTH:02d}-01"                       # inclusive
S2_END = (f"{YEAR + 1}-01-01" if SEASON_END_MONTH == 12
          else f"{YEAR}-{SEASON_END_MONTH + 1:02d}-01")                # exclusive
SEASON_TAG = f"{YEAR}m{SEASON_START_MONTH:02d}-m{SEASON_END_MONTH:02d}"   # used in file names
COMPOSITE_METHOD = "median"

# Matched to the classifier's training data (EuroSAT, Helber et al. 2019): images from the
# Sentinel-2A satellite, NOT atmospherically corrected -> Level-1C top-of-atmosphere.
# Dynamic World is also derived from Level-1C, so the comparison shares the same input level.
S2_COLLECTION = "COPERNICUS/S2_HARMONIZED"      # Level-1C TOA reflectance (DN = reflectance x 10 000)
S2_PROCESSING_LEVEL = "L1C"
S2_PLATFORMS = ["Sentinel-2A"]                  # SPACECRAFT_NAME filter; Sentinel-2B excluded
MIN_IMAGES = 10                # below this the notebook warns; it does NOT silently add Sentinel-2B

MAX_SCENE_CLOUD_PCT = 35       # scene filter (CLOUDY_PIXEL_PERCENTAGE <= 35). Dynamic World is only
                               # produced for scenes at or below 35%, so S2 and DW share one scene set.
CLOUD_SCORE_COLLECTION = "GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED"
CS_BAND = "cs_cdf"             # Cloud Score+ band
CS_THRESHOLD = 0.60            # keep pixels with cs_cdf >= threshold (Google's suggested default)

S2_EXPORT_BANDS = ["B2", "B3", "B4", "B8", "B11", "B12"]  # B11/B12 are 20 m, resampled to 10 m grid
S2_SCALE_FACTOR = 1e-4         # DN -> reflectance
NODATA = -9999.0

# ---------------------------------------------------------------------------
# 4. RGB chips
# ---------------------------------------------------------------------------
RGB_BANDS = ["B4", "B3", "B2"]
RGB_STRETCH_MIN = 0            # DN; one fixed stretch for ALL cells so chips are comparable
RGB_STRETCH_MAX = 3000         # DN (= 0.30 reflectance)
RGB_GAMMA = 1.0
PNG_DPI = 300
CHIP_UPSCALE = 10              # nearest-neighbour: 50 px -> 500 px; no new information added

# ---------------------------------------------------------------------------
# 5. Visual-label cell selection (Part 1 requirement)
# ---------------------------------------------------------------------------
RANDOM_SEED = 2019                                                 # >>> CONFIRM
N_VISUAL_LABEL_CELLS = 6

# ---------------------------------------------------------------------------
# 6. Class scheme (recorded in the Google Doc) and comparator crosswalks
#    Used in Part 2; defined here so Part 1 records the same definitions.
# ---------------------------------------------------------------------------
CLASSES = {                                                        # >>> CONFIRM
    "water":       "Open surface water (rivers, ponds, tanks, reservoirs) visible in the composite",
    "tree_cover":  "Closed or open tree canopy, incl. forest plantations",
    "cropland":    "Cultivated fields incl. fallow with visible field geometry; orchards and other permanent crops",
    "shrub_grass": "Shrubland, scrub, grassland, open grazing land; also flooded vegetation",
    "built_up":    "Buildings, roads, paved and industrial surfaces",
    "bare":        "Bare soil, rock, sand, quarries with little vegetation",
}
MIXED_LABEL = "mixed"
CLASS_COLORS = {"water": "#2f6db5", "tree_cover": "#1f7a3a", "cropland": "#e3b505",
                "shrub_grass": "#9dc25a", "built_up": "#c8442b", "bare": "#a08770"}
DOMINANT_CLASS_THRESHOLD = 0.50   # a cell gets a single class only if it covers >= 50% of valid area

DW_COLLECTION = "GOOGLE/DYNAMICWORLD/V1"
DW_CLASS_NAMES = ["water", "trees", "grass", "flooded_vegetation", "crops",
                  "shrub_and_scrub", "built", "bare", "snow_and_ice"]
DW_CROSSWALK = {
    "water": "water", "trees": "tree_cover", "grass": "shrub_grass",
    "flooded_vegetation": "shrub_grass", "crops": "cropland",
    "shrub_and_scrub": "shrub_grass", "built": "built_up", "bare": "bare",
    "snow_and_ice": None,
}

# --- Dynamic World V1 (10 m, one prediction per Sentinel-2 L1C scene) ---
# Temporal aggregation over the season, per pixel:
#   "mode"   : class frequency = share of valid observations whose `label` is that class;
#              aggregated label = most frequent class (ties -> lowest DW class index)
#   "mean"   : temporal mean of the 9 probability bands; label = argmax
#   "median" : temporal median of the 9 probability bands, rescaled to sum to 1; label = argmax
DW_TEMPORAL_AGG = "mode"       # "mode" | "mean" | "median"
DW_MATCH_S2_SCENES = True      # keep only DW images whose source scene is in the S2 scene inventory
DW_APPLY_CLOUD_SCORE = True    # also apply the same Cloud Score+ mask used for the S2 composite
assert DW_TEMPORAL_AGG in {"mode", "mean", "median"}

# --- CGLS-LC100 Collection 3, 2019 epoch (100 m, annual) ---
CGLS_IMAGE = "COPERNICUS/Landcover/100m/Proba-V-C3/Global/2019"
CGLS_BAND = "discrete_classification"
CGLS_EXPORT_BANDS = [
    "discrete_classification", "discrete_classification-proba", "data-density-indicator",
    "bare-coverfraction", "crops-coverfraction", "grass-coverfraction", "shrub-coverfraction",
    "tree-coverfraction", "urban-coverfraction", "water-permanent-coverfraction",
    "water-seasonal-coverfraction",
]
# CGLS is resampled to the 10 m grid with NEAREST neighbour (each 10 m pixel takes the 100 m
# class it falls in), so the per-cell majority is an area-weighted majority at 10 m precision.
# The native 100 m raster is also saved, and native pixel centres per cell are counted.
CGLS_CROSSWALK = {
    0: None,                       # unknown
    20: "shrub_grass",             # shrubs
    30: "shrub_grass",             # herbaceous vegetation
    40: "cropland",                # cultivated and managed vegetation / agriculture
    50: "built_up",                # urban / built up
    60: "bare",                    # bare / sparse vegetation
    70: None,                      # snow and ice
    80: "water",                   # permanent water bodies
    90: "shrub_grass",             # herbaceous wetland
    100: None,                     # moss and lichen
    111: "tree_cover", 112: "tree_cover", 113: "tree_cover",
    114: "tree_cover", 115: "tree_cover", 116: "tree_cover",   # closed forest
    121: "tree_cover", 122: "tree_cover", 123: "tree_cover",
    124: "tree_cover", 125: "tree_cover", 126: "tree_cover",   # open forest
    200: "water",                  # open sea
}

# ---------------------------------------------------------------------------
# 7. Primary classifier: ViT fine-tuned on EuroSAT RGB (Part 2)
# ---------------------------------------------------------------------------
MODEL_ID = "Haifald/vit-eurosat"
MODEL_REVISION = "1f933744e16bdda62c2a267a29b7a2ce753c4ff9"   # pinned HF commit
MODEL_BASE = "google/vit-base-patch16-224"
MODEL_TRAIN_DATA = "cm93/eurosat (EuroSAT RGB: 27,000 64x64 Sentinel-2A patches, 34 European countries)"
MODEL_DEVICE = -1              # -1 = CPU; 0 = first GPU

EUROSAT_PATCH_PX = 64          # training patch size (640 m at 10 m)
MODEL_INPUT_PX = 64            # each 50x50 cell chip is resized to 64x64 before the processor
MODEL_INPUT_RESAMPLE = "bilinear"   # 50 -> 64 resampling; the HF processor then resizes 64 -> 224
MODEL_TOP_K = 10               # keep the full probability vector in the raw responses

EUROSAT_CLASSES = ["AnnualCrop", "Forest", "HerbaceousVegetation", "Highway", "Industrial",
                   "Pasture", "PermanentCrop", "Residential", "River", "SeaLake"]
EUROSAT_CROSSWALK = {
    "AnnualCrop": "cropland",
    "PermanentCrop": "cropland",
    "Forest": "tree_cover",
    "HerbaceousVegetation": "shrub_grass",
    "Pasture": "shrub_grass",
    "Highway": "built_up",
    "Industrial": "built_up",
    "Residential": "built_up",
    "River": "water",
    "SeaLake": "water",
}   # NB: EuroSAT has no bare-soil class, so 'bare' can never be predicted by this model.

# Cell label from the model = argmax of crosswalked (summed) probabilities.
# If that maximum is below this threshold, the cell is also flagged 'uncertain'.
MODEL_UNCERTAINTY_THRESHOLD = 0.50

# ---------------------------------------------------------------------------
# 8. Output file names (season and aggregation encoded, so reruns never collide)
# ---------------------------------------------------------------------------
S2_INVENTORY_CSV = PATHS["metadata"] / f"s2_scene_inventory_{SEASON_TAG}.csv"
S2_COMPOSITE_TIF = PATHS["rasters"] / f"s2_{SEASON_TAG}_{COMPOSITE_METHOD}_10m.tif"
DW_INVENTORY_CSV = PATHS["metadata"] / f"dw_scene_inventory_{SEASON_TAG}.csv"
DW_TIF = PATHS["comparators"] / f"dw_{SEASON_TAG}_{DW_TEMPORAL_AGG}_10m.tif"
CGLS_TIF_10M = PATHS["comparators"] / f"cgls_lc100_c3_{YEAR}_on10mgrid.tif"
CGLS_TIF_NATIVE = PATHS["comparators"] / f"cgls_lc100_c3_{YEAR}_native100m.tif"
DW_CELLS_CSV = PATHS["comparators"] / f"dw_cells_{SEASON_TAG}_{DW_TEMPORAL_AGG}.csv"
CGLS_CELLS_CSV = PATHS["comparators"] / f"cgls_cells_{YEAR}.csv"
AGREEMENT_CSV = PATHS["tables"] / f"agreement_{SEASON_TAG}_{DW_TEMPORAL_AGG}.csv"
CELL_RESULTS_CSV = PATHS["tables"] / "cell_level_results.csv"
