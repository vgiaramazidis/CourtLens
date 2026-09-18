# CourtLens

## Frontend

Start the backend as described below, then serve the English-only frontend:

```bash
python3 -m http.server 3000 --directory src/frontend
```

Open `http://localhost:3000` rather than opening `index.html` directly.
The fixed light interface has three primary sections:

- **Explore**: AI Search, shot locations, result tables, and player/team analysis.
- **Video Analysis**: available YouTube games, synchronized shots and Play-by-Play,
  with AI Search filtering the matching actions.
- **Games**: Coach Challenge and all five Quiz Ball modes.

Season/game selections belong to each workspace. Navigating between sections
clears queries and results and cancels pending requests. Mobile navigation uses
three bottom tabs; tables and court views have a local display switch.

Frontend and related backend regression checks:

```bash
node --test src/frontend/tests/state.test.cjs
.venv/bin/python -m unittest src.backend.test_english_ui src.backend.test_coach_scope src.backend.test_video_sync src.backend.test_ai_search_evaluation
```

## Backend AI configuration

Keep AI credentials in a local `.env` file. The repository ignores `.env`, so
real keys must never be added to `.env.example` or committed.

Install dotenv support once and create the local configuration file:

```bash
.venv/bin/pip install python-dotenv
cp .env.example .env
```

Open `.env` and replace the two placeholders:

```dotenv
GEMINI_API_KEY=your-real-gemini-key
OPENAI_API_KEY=your-real-openai-key
AI_SEARCH_PROVIDER=gemini
AI_SEARCH_PROMPT_VARIANT=ontology
```

The frontend model selector displays only providers whose key is present. Start
the backend without exporting the keys manually:

```bash
.venv/bin/uvicorn app:app \
  --app-dir src/backend \
  --host 127.0.0.1 \
  --port 8000 \
  --reload \
  --env-file .env
```

Without either API key, the rest of the backend starts normally and AI Search
returns a configuration error. If a key has ever been committed, revoke it in
the provider console and create a replacement before running the backend.

## Play-by-Play action and RDF generation

`src/data_pipeline/parser.py` downloads the official EuroLeague Play-by-Play,
box-score, and points data. It can process either one game or every numeric game
code configured for a season.

Generate the action JSON and N-Triples for one game:

```bash
.venv/bin/python src/data_pipeline/parser.py E2023 170
```

Generate every configured game in a season:

```bash
.venv/bin/python src/data_pipeline/parser.py E2023
```

The configured maximum game codes are maintained in `DEFAULT_MAX_GAMES` inside
`src/data_pipeline/parser.py`. A different upper bound can be supplied without
changing the source code:

```bash
.venv/bin/python src/data_pipeline/parser.py E2023 --max-games 333
```

Existing pairs of output files are skipped by default. Use `--overwrite` to
regenerate them:

```bash
.venv/bin/python src/data_pipeline/parser.py E2023 170 --overwrite
```

The default processed-data root is `data/processed/`. Artifacts are separated by
category, and each processed game creates:

- `data/processed/all_actions/AllActions_<SEASON_CODE>_<GAME_CODE>.json`
- `data/processed/playbyplay_triplets/Triplets_<SEASON_CODE>_<GAME_CODE>.nt`

Use `--output-dir /path/to/processed-root` when a different root is needed; the
two category subdirectories are created automatically.
The parser writes the first overtime as `1OT`, while OCR timelines may write it
as `OT`. Synchronization code must normalize both values to the same canonical
first-overtime identifier before matching clocks.

## OCR RDF generation

`src/data_pipeline/ocr_triplets.py` converts video catalog metadata and OCR
timeline CSV rows into RDF N-Triples. Before matching, it checks the local
`AllActions_*.json` and `Triplets_*.nt` pair. Missing or invalid action artifacts
are generated automatically from the official EuroLeague API and validated.
Each Play-by-Play action is matched to the nearest OCR observation within four
game-clock seconds. Only observations referenced by at least one successful
match are written to production RDF. The timeline CSV remains unchanged and
retains every OCR observation for evaluation, debugging, and regeneration.

Generate OCR triples for one game:

```bash
.venv/bin/python src/data_pipeline/ocr_triplets.py E2023 170
```

Generate OCR triples for every video game registered in one season:

```bash
.venv/bin/python src/data_pipeline/ocr_triplets.py E2023
```

Use `--overwrite` to regenerate existing output. Files are written by default as
`data/processed/ocr_triplets/OCRTriplets_<SEASON_CODE>_<GAME_CODE>.nt`.

Use `--refresh-actions` to force regeneration of the Play-by-Play JSON and
N-Triples before generating OCR RDF. `--all-actions-dir` and
`--playbyplay-triplets-dir` can select different directories for those two
artifact categories.

Validate every generated `AllActions_*.json` and `Triplets_*.nt` pair with:

```bash
.venv/bin/python src/data_pipeline/validate_action_artifacts.py
```

The validator checks continuous internal sequences, unique official event IDs,
valid regulation/overtime clocks, possession references, N-Triples syntax and
duplicates, game-to-action links, and the RDF type of every action. During fresh
generation, the parser also compares every processed `(NUMBEROFPLAY, PLAYTYPE)`
pair with the included official API events and refuses to save incomplete
artifacts. EuroLeague `AG` (`ShotRejected`) events are intentionally excluded
from the generated JSON and RDF.

The generated graph uses the following structure:

```text
Game
  -> hasBroadcastVideo -> BroadcastVideo
       -> hasOCRObservation -> OCRObservation

PlayByPlayAction
  -> correspondsToOCRObservation -> OCRObservation
```

The reusable class and property declarations are in
`src/data_pipeline/ocr_schema.nt`. Import that schema once into the RDF store,
then import each generated `OCRTriplets_*.nt` data file. OCR periods are stored
canonically: `OT`, `1OT`, and `OT1` all become `OT`; later overtimes remain
`2OT`, `3OT`, and so on. OCR observations use the dedicated `ocrQuarter` and
`ocrClock` properties. The game-clock seconds remain an internal matching value
and are not materialized in the OCR RDF. YouTube URLs are stored as IRIs rather
than literal strings.

## Full-game video synchronization

The Video Shot feature synchronizes EuroLeague play-by-play actions with full-game YouTube videos. Synchronization is generated from the broadcast game clock through OCR and stored as timeline CSV files.

The processing flow is:

```text
YouTube full-game video
  -> temporary local MP4
  -> scoreboard clock OCR
  -> timeline CSV
  -> timeline validation
  -> catalog activation
  -> Video Shot frontend
```

New games must remain disabled until their timeline has been generated and validated successfully.

## Configuration files

The video synchronization system uses the following files:

- `src/data_pipeline/video_games.json` is the game catalog. It maps a EuroLeague season and game code to a YouTube video, an OCR profile, a start hint, and a timeline CSV.
- `src/data_pipeline/ocr_profiles.json` contains reusable scoreboard-layout profiles. Each profile defines the normalized clock region, image preprocessing, OCR thresholds, sampling settings, and clock-tracking rules.
- `src/data_pipeline/video_ocr.py` reads a full-game video and generates the clock timeline.
- `src/data_pipeline/validate_video_timelines.py` validates generated timelines and can repair legacy timeline files.
- `video_timelines/` contains the generated CSV files used by the backend.

The backend exposes only catalog entries that are enabled and have a readable, non-empty timeline. Disabled or unfinished games are therefore hidden from the Video Shot season and game selectors.

## Requirements

Run commands from the repository root. The project virtual environment must contain the OCR dependencies:

- `opencv-python`
- `easyocr`
- `yt-dlp`

Authenticated YouTube downloads also require access to the selected browser's cookies. On macOS, the first request may display a Keychain permission prompt.

## Adding a new game

### 1. Add a disabled catalog entry

Add the game to `src/data_pipeline/video_games.json` with `enabled` set to `false`:

```json
{
  "season_code": "E2024",
  "game_code": "123",
  "youtube_id": "YOUTUBE_VIDEO_ID",
  "youtube_url": "https://www.youtube.com/watch?v=YOUTUBE_VIDEO_ID",
  "ocr_profile": "euroleague_bottom_left_scorebug_16_9",
  "start_hint_seconds": 900,
  "playback_lead_seconds": 5,
  "assist_playback_lead_seconds": 9,
  "timeline_file": "video_timelines/E2024_123.csv",
  "enabled": false
}
```

Field reference:

- `season_code` is the EuroLeague season code used by the data API.
- `game_code` is the EuroLeague game code for that season.
- `youtube_id` is the YouTube video identifier.
- `youtube_url` is the full video URL.
- `ocr_profile` identifies the reusable scoreboard layout.
- `start_hint_seconds` is an approximate video position shortly before tip-off. It does not need to be exact, but it must not skip the beginning of the first quarter.
- `playback_lead_seconds` starts playback slightly before the selected action. The backend accepts values from 0 to 15 seconds and defaults to 5.
- `assist_playback_lead_seconds` is optional and controls how much of the pass is shown before an assisted basket. It accepts 0 to 15 seconds and defaults to at least 9 seconds. Assist actions use the linked made-shot clock when that RDF relation is available.
- `timeline_file` is the repository-relative output path.
- `enabled` controls whether the backend and frontend may expose the game.

Keep catalog entries ordered first by `season_code` and then by numeric `game_code`.

### 2. Check for duplicate games and videos

Run the following check after editing the catalog:

```bash
.venv/bin/python -c "
import json

games = json.load(open('src/data_pipeline/video_games.json'))['games']
keys = [(game['season_code'], game['game_code']) for game in games]
videos = [game['youtube_id'] for game in games]

print('Duplicate game keys:', len(keys) != len(set(keys)))
print('Duplicate YouTube IDs:', len(videos) != len(set(videos)))
"
```

Both results must be `False`.

The catalog can be sorted mechanically with:

```bash
jq '.games |= sort_by(.season_code, (.game_code | tonumber))' \
  src/data_pipeline/video_games.json \
  > /private/tmp/video_games.sorted.json

mv /private/tmp/video_games.sorted.json \
  src/data_pipeline/video_games.json
```

### 3. Verify YouTube access

Confirm that `yt-dlp` can access the video before downloading it:

```bash
.venv/bin/yt-dlp \
  --cookies-from-browser chrome \
  --remote-components ejs:github \
  --js-runtimes node:/usr/local/bin/node \
  --skip-download \
  "https://www.youtube.com/watch?v=YOUTUBE_VIDEO_ID"
```

If authentication fails, sign in to YouTube in the selected browser and retry. Approve the macOS Keychain prompt when requested.

### 4. Download a temporary local video

OpenCV may receive an HTTP 403 response when it attempts to read an authenticated YouTube media URL directly. The recommended workflow is therefore to download a temporary progressive MP4 and process the local file:

```bash
.venv/bin/yt-dlp \
  --cookies-from-browser chrome \
  --remote-components ejs:github \
  --js-runtimes node:/usr/local/bin/node \
  -f 18 \
  --no-part \
  -o /private/tmp/E2024_123.mp4 \
  "https://www.youtube.com/watch?v=YOUTUBE_VIDEO_ID"
```

Temporary videos must not be added to Git.

### 5. Confirm the OCR profile

List the available reusable layouts:

```bash
.venv/bin/python src/data_pipeline/video_ocr.py --list-profiles
```

The current catalog primarily uses:

- `euroleague_bottom_left_scorebug_16_9`
- `euroleague_left_scorebug_16_9`

Probe all configured profiles against the local video before a full OCR run:

```bash
.venv/bin/python src/data_pipeline/video_ocr.py \
  --season-code E2024 \
  --game-code 123 \
  --video-file /private/tmp/E2024_123.mp4 \
  --probe-profiles
```

A suitable profile should return plausible descending clock values, such as `9:58`, `9:30`, and `8:59`. If no profile produces valid readings:

1. Confirm that `start_hint_seconds` reaches the live game broadcast.
2. Inspect the video and verify the scoreboard position.
3. Try the other existing layout.
4. Create a new reusable profile only when the broadcast scoreboard layout is genuinely different.

Profile ROI values are normalized from 0 to 1, so a single profile can support multiple resolutions that use the same 16:9 broadcast layout.

### 6. Generate the timeline CSV

Run OCR against the downloaded file:

```bash
.venv/bin/python src/data_pipeline/video_ocr.py \
  --season-code E2024 \
  --game-code 123 \
  --video-file /private/tmp/E2024_123.mp4
```

The output path is taken from the catalog entry. A generated timeline has the following format:

```csv
video_time_sec,quarter,game_clock
985.0,1st,9:58
986.0,1st,9:57
```

The OCR tracker supports regulation periods and multiple overtime periods. It also rejects impossible clock jumps, prevents regular-period replays from being interpreted as overtime, removes conflicting readings, and keeps each period monotonic. A suspicious one-digit decimal reading after a large clock drop is confirmed on the next frame before it can move the tracker into the final seconds; this prevents OCR errors such as reading `51.3` as `5.3` from corrupting the rest of a period.

For frame-by-frame diagnostics, add `--trace-frames` and save the terminal output:

```bash
.venv/bin/python src/data_pipeline/video_ocr.py \
  --season-code E2024 \
  --game-code 220 \
  --video-file /private/tmp/E2024_220.mp4 \
  --output /private/tmp/E2024_220_candidate.csv \
  --trace-frames | tee /private/tmp/E2024_220_trace.log
```

The trace reports every sampled frame, including frames with no OCR text, low-confidence or unparseable readings, and the exact tracker accept/discard reason. With the default one-second sampling interval this means one trace entry per sampled video second, not every source-video frame.

The output CSV is written only after the OCR run completes successfully. An interrupted run does not create a partial replacement timeline.

### 7. Validate the generated timeline

Validate all timeline files that currently exist:

```bash
.venv/bin/python \
  src/data_pipeline/validate_video_timelines.py \
  --existing-only
```

Run strict validation for a new game before it is enabled:

```bash
.venv/bin/python \
  src/data_pipeline/validate_video_timelines.py \
  --catalog-file src/data_pipeline/video_games.json \
  --season-code E2024 \
  --game-code 123 \
  --strict
```

The new game must be reported as `OK` before it is enabled. `WARN` identifies incomplete start, end, or internal clock coverage and becomes a failure in strict mode.

The validator checks:

- A minimum number of timeline points.
- Required coverage for the first through fourth periods.
- Overtime duration and coverage when overtime exists.
- Strictly increasing video timestamps.
- A monotonic game clock within each period.
- Period clocks that do not exceed their valid duration.
- Clock decreases that remain physically possible relative to elapsed video time.
- Start and end coverage for each detected period.
- Large internal clock-coverage gaps that may leave Play-by-Play actions without a timestamp.

Do not enable a timeline reported as `FAIL`. Correct the start hint or OCR profile and run OCR again.

### 8. Enable the game

After the timeline passes validation, change its catalog entry to:

```json
"enabled": true
```

The backend will then include it in `/api/video/games`, and the Video Shot frontend will expose it through the season and game selectors.

### 9. Run the complete verification suite

Validate every enabled timeline:

```bash
.venv/bin/python \
  src/data_pipeline/validate_video_timelines.py \
  --enabled-only
```

Run the OCR unit tests:

```bash
.venv/bin/python -m unittest \
  src.data_pipeline.test_video_ocr \
  src.data_pipeline.test_video_timelines \
  src.backend.test_video_sync
```

Check the frontend JavaScript and the Git diff:

```bash
node --check src/frontend/js/api.js
node --check src/frontend/js/main.js
git diff --check
```

Optionally verify the backend catalog endpoint without starting a persistent server:

```bash
PYTHONPATH=src/backend .venv/bin/python -c "
from fastapi.testclient import TestClient
from app import app

response = TestClient(app).get('/api/video/games')
response.raise_for_status()
payload = response.json()
print('Available games:', len(payload['games']))
print('Available seasons:', payload['seasons'])
"
```

### 10. Remove the temporary video

Delete the temporary MP4 only after the CSV has passed validation:

```bash
rm /private/tmp/E2024_123.mp4
```

The generated CSV must remain in `video_timelines/` because it is required by the backend at runtime.

## Repairing a legacy timeline

The validator can repair an existing CSV by removing conflicting, duplicate, or temporally impossible readings:

```bash
.venv/bin/python src/data_pipeline/validate_video_timelines.py \
  --repair-file /path/to/input.csv \
  --repair-output video_timelines/E2024_123.csv
```

Always validate the repaired file before enabling the game.

## Recommended operating procedure

Use the following state transition for every new game:

```text
enabled: false
  -> verify catalog uniqueness
  -> verify YouTube access
  -> download temporary MP4
  -> confirm OCR profile
  -> generate timeline CSV
  -> validate timeline
  -> enabled: true
  -> run the complete verification suite
  -> remove temporary MP4
```

Never enable a game merely because a CSV file was created. Activation is permitted only after successful validation.
