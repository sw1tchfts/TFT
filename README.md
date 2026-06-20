# TFT Scout

A companion app for Teamfight Tactics that reads champions off opponents'
boards from screenshots and tells you which champions are still **contestable**
in the shared pool — so you know what to roll for.

## How it works

```
TFT (windowed)  --hotkey-->  screen capture  -->  slice into unit slots
      -->  trained CNN classifier (champion id) + star detector
      -->  pool tracker (per-source snapshots, deduped)
      -->  dashboard: copies remaining, sorted by contestability
```

Every champion has a fixed number of copies in a shared pool, set by its cost.
Units held on boards/benches remove copies from the pool. Star level matters:

| Star | Copies consumed |
|------|-----------------|
| 1★   | 1 |
| 2★   | 3 |
| 3★   | 9 |

Snapshots are keyed per source (each opponent + yourself). Re-scouting a source
**overwrites** its snapshot, so changing boards never double-count.

## Status

| Phase | Description | State |
|-------|-------------|-------|
| 1 | Scaffold + champion/pool data | ✅ done |
| 2 | Pool-tracking engine + tests | ✅ done |
| 3 | Capture, region calibration, hotkeys (1024×768 windowed) | ✅ done |
| 4 | Training pipeline (synthetic data from portraits) | ☐ |
| 5 | Inference wiring (capture → classify → engine) | ☐ |
| 6 | Dashboard UI | ☐ |
| 7 | Package to Windows `.exe` (PyInstaller) | ☐ |

## Setup

```bash
pip install -r requirements.txt
```

## Data

Champion data and portraits come from [CommunityDragon](https://www.communitydragon.org/)
(free, no auth). Regenerate per set/patch:

```bash
# current live set (17), pinned-version recommended over 'latest' for stability
python -m src.data.fetch_data --set 17 --version latest
```

This writes `config/set_data.json` and downloads HUD portraits to
`assets/portraits/set<N>/`. Pool sizes (copies-per-cost) are not in the source
data — they default to the table above and are editable in `set_data.json`.

## Capture & calibration

Slot geometry lives in `config/layout_1024x768.json` as **fractions of the
capture region**, so one file scales to any window size. The shipped values are
estimates — calibrate against your client:

```bash
# drag a rectangle over the TFT play area; writes the region into the layout
python -m src.capture.calibrate --out config/layout_1024x768.json
```

Hotkeys (while TFT is focused) tag each capture to a source:

| Key | Action |
|-----|--------|
| `1`–`7` | scout opponent N → snapshot `opp1`..`opp7` |
| `0` | capture your own board / bench / shop → `self` |
| `` ` `` | reset the running pool tally |

The geometry (`src/capture/layout.py`) and slicing (`src/capture/slicer.py`) are
pure/numpy and fully tested headless. Capture (`screen.py`, mss), hotkeys
(`hotkeys.py`, pynput), and the calibration overlay (`calibrate.py`, PySide6)
are thin wrappers that lazy-import their deps.

## Tests

```bash
pytest -q
```

## Layout

```
config/set_data.json          champions, costs, traits, pool sizes (per set)
config/layout_1024x768.json   slot geometry (region + grid fractions)
assets/portraits/             champion HUD portraits (classifier training data)
src/data/fetch_data.py        CommunityDragon fetch -> config + portraits
src/engine/pool.py            pool-tracking engine (pure Python)
src/capture/layout.py         slot geometry engine (pure)
src/capture/slicer.py         region image -> per-slot crops (numpy)
src/capture/screen.py         mss screen capture (lazy import)
src/capture/hotkeys.py        global hotkeys (lazy import)
src/capture/calibrate.py      drag region selector (PySide6, lazy import)
tests/                        engine + geometry + slicer tests
```
