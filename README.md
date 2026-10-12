# LCW technical assessment — land cover on a fixed 3 × 4 grid (Sentinel-2, 2019)

Reproducible pipeline: build a fixed 12-cell grid, make a cloud-screened Sentinel-2A Level-1C composite for one season of 2019,
export per-cell RGB chips, classify all cells, and compare with Dynamic World and CGLS-LC100.

## Repository layout

```
lcw-landcover-assessment/
├── README.md                 # this file: layout, justifications, how to run
├── requirements.txt          # pinned; appended automatically as libraries are used
├── config.py                 # ALL global settings (AOI, dates, thresholds, classes, crosswalks, paths)
├── src/
│   ├── env_utils.py          # repo-root discovery, requirements.txt logger
│   ├── grid.py               # 3 × 4 UTM grid, cell IDs r{row}c{col}, GeoJSON export
│   ├── gee_utils.py          # EE auth, Cloud Score+ masking, composite, scene inventory, grid-aligned download
│   ├── chips.py              # fixed RGB stretch, 300-DPI PNG chips, GeoTIFF, overview panel
│   ├── eurosat_model.py      # EuroSAT ViT: 50→64 px inputs, inference, raw JSON, class aggregation
│   ├── comparators.py        # Dynamic World seasonal aggregate (mode/mean/median), CGLS 10 m + native 100 m
│   └── cell_agg.py           # crosswalks, cell majority rule, pixel accounting, agreement with denominators
├── notebooks/
│   ├── 01_part1_aoi_grid_composite.ipynb   # Part 1
│   └── 02_part2_classify_compare.ipynb     # Part 2: EuroSAT + comparators + agreement + cell CSV
├── outputs/
│   ├── geojson/              # aoi_boundary.geojson, grid_cells.geojson
│   ├── chips/rgb/            # one PNG per cell (display, nearest-neighbour ×10)
│   ├── chips/rgb_native/     # one PNG per cell at native 10 m pixels (50 × 50)
│   ├── rasters/              # grid-aligned composite + per-pixel observation counts (GeoTIFF)
│   ├── metadata/             # scene inventory, run metadata JSON
│   ├── labels/               # six hand-made visual labels (cue + confidence)
│   ├── model_inputs/         # exact 64×64 images fed to the classifier
│   ├── model_responses/raw/  # raw classifier responses (full 10-class vector), one JSON per cell
│   ├── comparators/          # Dynamic World and CGLS-LC100 per-cell extractions
│   ├── runs/baseline/        # original Part 2 outputs — never overwritten
│   ├── runs/sensitivity/     # outputs after changing one choice
│   ├── tables/               # valid-data table, final cell-level CSV
│   └── figures/              # map / image panels embedded in the Google Doc
└── docs/
    ├── report_notes.md       # mirror of what goes in the Google Doc
    └── sensitivity_prediction.md   # written and committed BEFORE the rerun
```

## How to run

```bash
pip install -r requirements.txt
export EE_PROJECT=<your-earth-engine-cloud-project>
jupyter lab notebooks/01_part1_aoi_grid_composite.ipynb
```
In Colab: clone the repo, `%cd` into it, `%env EE_PROJECT=...`, then run notebook 01 top to bottom.

## Conventions
* Cell IDs: `r{row}c{col}`, `r1` = northernmost row, `c1` = westernmost column (`r1c1` … `r3c4`).
* GeoJSON is EPSG:4326 (RFC 7946); all area and pixel work is in the local UTM zone.
* One fixed RGB stretch for every chip; DPI (300) is print metadata — a 500 m cell is 50 × 50 Sentinel-2 pixels.
