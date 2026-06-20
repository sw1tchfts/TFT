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
| 3 | Capture, region calibration, hotkeys (1024×768 windowed) | ☐ |
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

## Tests

```bash
pytest -q
```

## Layout

```
config/set_data.json     champions, costs, traits, pool sizes (per set)
assets/portraits/        champion HUD portraits (classifier training data)
src/data/fetch_data.py   CommunityDragon fetch -> config + portraits
src/engine/pool.py       pool-tracking engine (pure Python)
tests/                   engine tests
```
