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
| 4 | Training pipeline (synthetic data from portraits) | ✅ done |
| 5 | Inference wiring (capture → classify → engine) | ✅ done |
| 6 | Dashboard UI | ✅ done |
| 7 | One-click launcher (`run.bat`) | ✅ done |

## Run it (Windows, one click)

Double-click **`run.bat`**. The first run sets up a virtual environment,
installs dependencies, downloads champion data, and trains the recognizer (a few
minutes). Every run after that just launches the app instantly — so you can keep
editing the code and relaunch with one click. No build/packaging step.

## Quick start (manual / other platforms)

```bash
pip install -r requirements.txt   # torch CPU build is the default on Windows

python -m src.data.fetch_data --set 17     # 1. champion data + portraits
python -m src.model.train --epochs 8       # 2. train the recognizer
python -m src.capture.calibrate            # 3. set the capture region

python main.py        # launch the always-on-top dashboard
python main.py --cli  # or print the report to stdout (no GUI)
```

In game (windowed): press `1`–`7` while scouting each opponent, `0` for your own
board, `` ` `` to reset. The dashboard shows copies remaining, sorted by
contestability — the fuller the bar, the more of that champion is left to roll.

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

## Training the recognizer

No hand-labeling: training crops are **synthesized** from the champion portraits
(`src/model/synth.py`) — portrait + star pips (1/2/3, bronze/silver/gold) on a
cost-tinted, augmented background, plus an EMPTY class. A small multi-task CNN
(`src/model/net.py`) predicts champion **and** star level.

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
python -m src.model.train --epochs 8 --batch 128 --steps 200   # full run
python -m src.model.train --smoke                              # tiny sanity run
```

Weights land in `models/classifier.pt` (+ `models/labels.json`); both are
git-ignored and regenerated. A quick 4-epoch CPU run already reaches ~100%
champ / ~96% star accuracy **on synthetic data** — real-screenshot accuracy
depends on calibrating backgrounds/positions to your client, which is the next
tuning step. Inference (`src/model/infer.py`) turns slot crops into engine
`Unit`s via `ChampionRecognizer.recognize_slots`.

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
src/model/labels.py           champion/star label space
src/model/synth.py            synthetic training-image generator (numpy/PIL)
src/model/net.py              multi-task CNN (champion + star)
src/model/dataset.py          torch dataset over the synthetic generator
src/model/train.py            training loop -> models/classifier.pt
src/model/infer.py            crops -> recognized Units (bridges to engine)
src/app/controller.py         orchestration: action -> capture -> recognize -> pool
src/ui/render.py              text rendering of the contestability report
src/ui/dashboard.py           always-on-top Qt dashboard (PySide6, lazy import)
main.py                       entry point (GUI or --cli)
tests/                        engine + geometry + slicer + synth + model
                              + controller + render tests
```

## Status note

The recognizer is validated on **synthetic** data; on real screenshots its
accuracy depends on calibrating the slot geometry and background tints to your
client. Drop in one 1024×768 scout screenshot to lock those in.
