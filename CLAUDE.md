# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Where is SWOT?** is a Flask web app that visualizes the orbit of the SWOT (Surface Water and Ocean Topography) satellite. Users select a date range and the app generates an interactive Folium map showing predicted satellite swath passes. Deployed on Render at https://whereisswot.onrender.com/.

## Running the App

Local development uses pixi:

```bash
pixi install
pixi run start                   # runs on http://0.0.0.0:4242
```

After changing dependencies in `pyproject.toml`, regenerate `requirements.txt` for Render:

```bash
pixi run update-requirements
```

Production (Render) uses `requirements.txt` directly: build command `pip install -r requirements.txt`, start command `gunicorn app:app`.

There is no test suite or linter configured.

## Architecture

The app has two Python files:

- **`tools.py`** — Data processing and map creation:
  - `process_orbit_data()` — Loads calval and science orbit shapefiles from `data/external/swot_swath/`, then generates predicted pass times for many cycles by applying fixed time deltas. Returns a single concatenated DataFrame with columns: TIME, CYCLE, ORBIT ("calval"/"science"), PASS, and geometry.
  - `create_map()` — Filters the pre-computed orbit data by a date range, groups passes by geometry, builds a Folium map colored by "days from start", optionally overlays EEZ boundaries, and adds a layer control + mouse position plugin.
  - `calculate_time()` — Helper that parses START_TIME strings from shapefiles and converts to absolute timestamps relative to a reference date.

- **`app.py`** — Flask routes:
  - `process_orbit_data()` and EEZ shapefile are loaded **once at module level** (expensive startup).
  - `POST /` validates form input, calls `create_map()`, saves the resulting Folium map to a temp file, stores the path in the session, and renders `index.html` with an iframe pointing to `/show_map`.
  - `GET /show_map` serves the temp map HTML file and deletes it after reading.

## Key Data Dependencies

- **Orbit shapefiles** (`data/external/swot_swath/`): calval and science orbit swath geometries. These are the source for all pass predictions.
- **EEZ boundaries** (`data/external/eez/eez_boundaries_v12.shp`): Exclusive Economic Zone boundaries displayed as an optional map layer. The `DOC_DATE` column is dropped during loading.
- **Processed data** (`data/processed/`): Contains exported KML files (not used by the app itself).

## Domain Concepts

- **Calval orbit**: Calibration/validation orbit phase with ~0.99349-day cycle period, starting 2023-01-15.
- **Science orbit**: Science phase with ~20.864549-day cycle period. Passes are dissolved by ID_PASS.
- Opacity values in the map depend on the number of days selected (<=4 days: higher opacity).
- Maximum user-selectable range is 100 days.
