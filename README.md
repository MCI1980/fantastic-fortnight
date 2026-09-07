# Golf Coach

A personal practice-planning app for the 80s golfer with a TrackMan at home.

It reads your **TrackMan Performance Studio CSV exports** and your **rounds**, then tells you:

- **My Numbers** – a yardage card with *Safe / Plan / Max* carry per club, miss bias, dispersion and bag gaps
- **Coach** – what is costing you strokes (face-to-path, path, attack angle, strike, distance control) and, from your rounds, where the strokes actually go (penalties, three-putts, blow-up holes) versus a target scoring level
- **Plan** – a weekly plan of two or three simulator sessions with drills, scored games and pass marks you can verify on the next export
- **Progress** – per-club trends by session, scoring trends and whether last week's plan checks passed

No camera, no video, no cloud. Runs on the simulator PC; open it on your phone over Wi-Fi.

## Quick start (simulator PC, Windows)

1. Install Python 3.10+ from python.org (tick *Add to PATH*).
2. Download or clone this repository into a folder, e.g. `C:\GolfCoach`.
3. Double-click **`run_app.bat`**. The first run creates a virtual environment and installs dependencies.
4. The window prints a **Network URL** like `http://192.168.1.23:8501`. Open it on your phone (same Wi-Fi) or on the PC.
5. In the sidebar set the **TrackMan export folder** (see below), your handedness and target score. Save.

Mac/Linux:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run streamlit_app.py --server.address 0.0.0.0
```

### Keeping it running

The app stops when the `run_app.bat` window is closed or the PC sleeps. To make it start hidden at every login and keep the PC awake while plugged in, double-click **`install_autostart.bat`** once (after the first `run_app.bat` run). Then:

- `stop_app.bat` stops it, `run_app.bat` or a reboot starts it again
- `remove_autostart.bat` undoes the autostart
- output goes to `data\store\app.log`

### Reaching it away from home

Install [Tailscale](https://tailscale.com) (free) on the PC and your phone; then the same URL works from anywhere. Or download the yardage card PNG from **My Numbers** and keep it on your phone.

## Getting data in

### TrackMan sessions (one click per session)

In **TrackMan Performance Studio**:

1. Open **Shot Analysis** (practice/range mode, not Virtual Golf) and load the session – today's, or one from the **Shot Library**.
2. **View Selector → Table View**.
3. **File Options → Trackman CSV**.
4. Save into your export folder. The app imports new files automatically the next time it loads (or press *Scan export folder now* in the sidebar).

Notes:

- CSV export only exists in TPS on the simulator PC and needs an active software subscription. The TrackMan phone app and web portal only share reports.
- **Tag the club in TPS before each set.** Without a club name the shots import as "Unknown" and are ignored by the analysis.
- Re-exporting a session is safe: files and individual shots are de-duplicated.
- The importer handles comma/semicolon files, a units row, km/h and metres, `5.2 R` / `L 3.1` side values, and drops the *Average / Std Dev* rows.

You can also drag files onto the **Import** tab.

**Tags.** Use the TPS **Tag** button before a set (clear it afterwards):

| Tag | Effect |
|---|---|
| `warmup`, `drill` (or `drill: gate`) | kept, but excluded from the yardage card and coaching rules |
| `game` | scores every practice game that fits the club |
| `game: fairway finder` | scores that game only |

**Impact location.** TrackMan 4 exports `Impact Offset` and `Impact Height` (mm from face centre). The app draws a strike map per club and adds heel / toe / low-on-the-face findings with matching drills.

### Rounds

Either:

- **Log it in the Rounds tab** (two minutes: score, putts, fairway, green, penalties per hole), or
- **Import a hole-by-hole CSV** from a scoring app that exports one – [Golfity](https://golfity.com) (free, exports rounds/holes/shots) or Golf Pad (comprehensive export needs Premium). Bushnell Golf does not export.

With two or more rounds the Coach tab shows a *strokes lost* table against your target score.

## What the coaching is based on

Every rule is a comparison of your per-club averages (last N days, 8+ shots) with an amateur-realistic window in `coaching/goals.py`. Each finding carries:

- **why it costs strokes**
- **measured vs target**
- **a pass mark** ("7 of 10 shots with face-to-path inside ±3°") that the Plan and Progress tabs check automatically
- **drills** tagged to the fault in `data/drills.yaml`, each marked *sim*, *home* or *course* and with the TrackMan number to watch

Round rules compare putts, three-putts, penalties, GIR, FIR, doubles and scrambling with approximate benchmarks for your target score (`analysis/scoring.py`). The ranking is the point; the decimals are indicative.

Scored practice games (`data/games.yaml`) are computed from the last 10 shots of a club in a session – Fairway Finder, Face Control 10, Smash Ten, Distance Control, Hit Up Ten, Down and Through.

## Project layout

```
streamlit_app.py        UI: Import · My Numbers · Coach · Plan · Rounds · Progress
run_app.bat             Windows launcher (creates venv, installs, runs)

integrations/
  base.py               canonical shot schema (names + units)
  trackman.py           tolerant TPS CSV importer, club normalization
  rounds_csv.py         hole-by-hole round CSV importer

data/
  shots.py              JSONL shot store, folder scan, de-duplication
  rounds.py             Round / HoleResult + JSONL store
  plans.py              weekly plan history
  settings.py           settings (export folder, handedness, target score)
  drills.yaml           drills tagged to faults
  games.yaml            scored practice games
  store/                YOUR DATA (git-ignored)

analysis/
  prep.py               handedness sign normalization, filters, windows
  gapping.py            per-club summary, bag gaps, yardage card
  tendencies.py         shot-shape classification, strike quality
  scoring.py            round stats, benchmarks, strokes lost
  games.py              game scoring

coaching/
  goals.py              target windows per club category
  rules.py              shot + round rules → CoachingPointer
  plan.py               weekly plan generator + check evaluation
  drills.py             drill loading / tag matching

core/report.py          yardage card PNG
tests/                  pytest suite with sample TrackMan + rounds CSVs
```

Your data lives in `data/store/` (override with the `GOLF_DATA_DIR` environment variable). Back it up occasionally; the Progress tab can export everything.

## Development

```bash
pip install -r requirements.txt
pytest tests/ -v
```

The video/camera version of this app is preserved on the `archive/video-capture-v1` branch.

## Roadmap

- Screenshot → round import (photograph a scorecard/app screen, extract the holes)
- TrackMan Cloud API sync if TrackMan grants personal API credentials
- Approach-shot proximity games using a target distance
