# EuroleagueProject

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

The OCR tracker supports regulation periods and multiple overtime periods. It also rejects impossible clock jumps, prevents regular-period replays from being interpreted as overtime, removes conflicting readings, and keeps each period monotonic.

The output CSV is written only after the OCR run completes successfully. An interrupted run does not create a partial replacement timeline.

### 7. Validate the generated timeline

Validate all timeline files that currently exist:

```bash
.venv/bin/python \
  src/data_pipeline/validate_video_timelines.py \
  --existing-only
```

The new game must be reported as `OK` before it is enabled.

The validator checks:

- A minimum number of timeline points.
- Required coverage for the first through fourth periods.
- Overtime duration and coverage when overtime exists.
- Strictly increasing video timestamps.
- A monotonic game clock within each period.
- Period clocks that do not exceed their valid duration.
- Clock decreases that remain physically possible relative to elapsed video time.
- Start and end coverage for each detected period.

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
.venv/bin/python -m unittest src.data_pipeline.test_video_ocr
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
