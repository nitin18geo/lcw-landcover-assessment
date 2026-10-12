# Report notes (mirror of the Google Doc)

## Area
- Name / location:
- Centre (lon, lat):           | CRS of grid:            | Area: 3.00 km² (3 × 4 cells of 500 m)

## Dates
- Season: SEASON_TAG from config (S2_START to S2_END excl.); Sentinel-2A L1C median, scenes ≤35% cloud, Cloud Score+ cs_cdf ≥ 0.60
- Dynamic World: same scenes, aggregation DW_TEMPORAL_AGG; CGLS-LC100 C3 2019 (annual, 100 m)
- Scenes used: see outputs/metadata/s2_scene_inventory_<SEASON_TAG>.csv and dw_scene_inventory_<SEASON_TAG>.csv

## Class definitions
(copy from config.CLASSES)

## Six visual-label cells
- Rule: numpy default_rng(seed=2019).choice(12, 6, replace=False)
- Cells:

| cell_id | label | visual cue | confidence |
|---|---|---|---|

## Report (≤ 350 words)
