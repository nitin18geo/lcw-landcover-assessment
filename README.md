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

## Why each piece exists (traced to the brief)

| Component | Requirement it answers |
|---|---|
| `config.py` | "Record the exact products, dates, class crosswalk and processing choices." One file holds them, so every number in the report has one source and every change shows up in git. |
| `src/grid.py` (UTM, pixel-snapped) | "a fixed 3 × 4 grid of 12 non-overlapping cells, each roughly 250–500 metres per side" and "Compare the same geographical footprints". Cells are exactly 500 m and exactly 50 × 50 S2 pixels, so no partial pixels enter any cell statistic. |
| `outputs/geojson/` | "Save the boundary and cell IDs as GeoJSON". |
| `outputs/chips/` | "export one RGB chip per cell". Native and display versions are kept so a chip can be traced back to exact pixels. |
| `outputs/metadata/s2_image_inventory_2019.csv` | Dynamic World must be compared "for the same imagery window"; the scene list fixes that window. |
| `obs_total` / `obs_clear` bands + `cell_valid_data_part1.csv` | "account for valid-data coverage" and the CSV column for "valid-data counts or area". |
| `outputs/labels/` + seeded selection in `config.RANDOM_SEED` | "Select those six cells with a stated rule or random seed" and "Label them yourself from the imagery, without AI assistance… record one visual cue and a confidence level". The sheet is never overwritten by code. |
| `outputs/model_responses/raw/` + `outputs/model_inputs/` | "raw model responses where applicable"; storing the exact input image lets any prediction be traced to its pixels. |
| `MODEL_REVISION` pinned in `config.py` | "Implement a reproducible method": the Hugging Face weights cannot change under the analysis. |
| Sentinel-2A, Level-1C imagery | Matches EuroSAT (Sentinel-2A, not atmospherically corrected), so the model sees the input type it was trained on. |
| Model disclosure cell (notebook 02 §2a) | "Disclose any known overlap between a pretrained model's training data and your comparators." EuroSAT is Europe-only; no known overlap with India, Dynamic World or CGLS. |
| `SEASON_START_MONTH` / `SEASON_END_MONTH` in `config.py` | "Compare your results with Dynamic World for the same imagery window": one season drives the composite, the EuroSAT input and the DW window. |
| DW matched scene-by-scene to the S2 inventory, 35 % scene-cloud limit | Same imagery, not just the same dates; DW is only produced for scenes ≤ 35 % cloud. |
| `DW_TEMPORAL_AGG` (mode / mean / median) | "Explain how you aggregated probabilities or labels"; switchable for the aggregation-rule sensitivity test. |
| `outputs/comparators/*.tif` (DW 10 m; CGLS on 10 m grid **and** native 100 m) | "Compare the same geographical footprints and account for… the products' different resolutions and their temporal definitions." |
| `src/cell_agg.py` majority rule + pixel accounting | Cell labels by majority over valid pixels; valid / unmapped / no-data pixel counts give the "valid-data counts or area". |
| `outputs/tables/agreement_*.csv` | "Give denominators for any agreement statistic"; product agreement kept separate from the check against the six visual labels. |
| `outputs/tables/crosswalk.csv` | "Record the exact products, dates, class crosswalk and processing choices." |
| `runs/baseline/` vs `runs/sensitivity/` | "Change one choice, retain the original outputs and report what happened, including no change." |
| `docs/sensitivity_prediction.md` | "Before rerunning, write a brief prediction". Committing it first gives a git timestamp showing the prediction preceded the result. |
| `outputs/tables/cell_level_results.csv` | "a cell-level CSV showing initial visual labels…, method and comparator labels, valid-data counts or area, and uncertainty". |
| `src/` modules used by both notebooks | "Be ready to trace a CSV row back to the image and code": one function per step, one place to look. |
| `requirements.txt` logger | Reproducibility; pins are added as soon as a notebook uses a new library. |

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
