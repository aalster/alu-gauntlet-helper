# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ALU Gauntlet Helper — desktop application for Asphalt 9: Legends players to track race statistics. Features OCR-based screenshot recognition, race/car/track management, and statistics filtering.

## Tech Stack

- **Python 3.9+**, **PyQt6** (GUI), **SQLite** (database)
- **OpenCV + Tesseract** (screen recognition)
- **Pydantic** (data models)

## Commands

```bash
# Run application
python main.py

# Run minimized to tray
python main.py --minimized

# Build installer (PyInstaller onedir + Inno Setup), see installer/README.md
powershell -File scripts/build_installer.ps1
```

## Architecture

```
main.py                      # Entry point: init DB → load settings → init_data() → QApplication
alu_gauntlet_helper/
├── app_context.py           # Singleton service container (AppContext)
├── database.py              # SQLite connection + migration runner
├── models.py                # Pydantic models (PageResult, FieldGuess, RaceCapture, RecognitionResult)
├── services/                # Repository + Service pattern
│   ├── maps.py              # Map, MapsRepository, MapsService
│   ├── tracks.py            # Track, TrackView, TracksRepository, TracksService
│   ├── cars.py              # Car, CarsRepository, CarsService
│   ├── races.py             # Race, RaceView, RacesRepository, RacesService
│   ├── settings.py          # Settings persistence
│   ├── cars_sync.py         # Cars sync from asec.tools (bundled JSON seed + daily remote refresh)
│   └── initial_data.py      # Seed data (maps, tracks; cars come from cars_sync)
├── views/                   # PyQt6 UI
│   ├── style.py             # ALU game theme: palette constants + global QSS, applied in main.py
│   ├── main_window.py       # Main window with tabs + tray icon + CaptureController
│   ├── capture_tab.py       # Inline review of captured races: checkboxes, edit via RaceDialog, save/discard
│   ├── car_selection_tab.py # Manual car-vs-track picker (per-track car suggestions)
│   ├── races_tab.py
│   ├── tracks_tab.py        # Two panels: maps (left) + tracks (right)
│   ├── cars_tab.py
│   ├── settings_tab.py
│   ├── overlay.py           # On-screen capture overlay
│   └── components/          # Reusable widgets (EditDialog, ValidatedLineEdit, etc.)
├── capture/                 # Hotkeys, screen grab (mss), CaptureController
├── screen_recognition/      # OCR (Tesseract), regions, matching, RecognitionEngine, screens/
└── utils/
    ├── utils.py             # Helpers (time formatting, image processing, resource paths)
    └── single_instance_lock.py

resources/
├── migrations/              # SQL migrations (001__init.sql, etc.)
├── data/cars.json           # Bundled snapshot of asec.tools carsList (seed for first start)
├── icons/cars/              # Car icons from img.asec.tools, named {asec_id}.webp
└── icons/maps/              # Map icon images
```

## Key Patterns

- **Service/Repository**: Services handle business logic, repositories handle DB queries
- **AppContext**: Global singleton providing access to all services
- **Migrations**: SQL files in `resources/migrations/` applied automatically by `database.py`
- **Resource paths**: Use `get_resource_path()` for PyInstaller compatibility
- **Data storage**: User data (icons, etc.) goes to `data/` directory, not `resources/`
- **Data location**: frozen-збірка робить `os.chdir(<тека exe>)` на старті — `app.db` і `data/` живуть поруч з exe; cwd після старту не змінювати
