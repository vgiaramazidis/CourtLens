# CourtLens

EuroLeague games, shot charts, player analysis and basketball quizzes in one English-language interface.

- **Video Analysis:** The default workspace. YouTube footage beside either a shot chart or Play-by-Play, with optional AI Search and a read-only SPARQL editor. Only games with available video appear.
- **Explore:** Browse statistics by default, with AI Search, player biographies, tables and a 3D shot court available.
- **Games:** Coach Challenge and five Quiz Ball formats.

CourtLens is an early-access project. See [known limitations](#known-limitations) and the [academic evaluations](evaluation/README.md).

## Run locally

Use Python 3.13. Node.js 22 or later is needed only for frontend tests; the frontend has no build step.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` locally:

- `SPARQL_ENDPOINT`: the URL of your populated basketball SPARQL database. The example points to a local server; this repository does not provision or contain the full database.
- `OPENAI_API_KEY`: enables GPT-5 Mini Search and generated Quiz Ball questions.
- `GEMINI_API_KEY`: optional alternate Search provider.

Keep actual keys and deployment addresses out of commits. The example values are placeholders.

Start the backend from the repository root:

```bash
.venv/bin/uvicorn src.backend.app:app --host 127.0.0.1 --port 8000 --reload --env-file .env
```

In another terminal:

```bash
python3 -m http.server 3000 --directory src/frontend
```

Open [CourtLens](http://localhost:3000). Serve only `src/frontend`, not the repository root. The frontend uses the backend on port 8000 of the same host.

GPT-5 Mini is the default Search model. Generated quizzes use OpenAI exclusively; Top 5 uses database statistics without an AI call. The server starts without AI keys, but generated questions require the configured provider. Basketball queries require a populated SPARQL endpoint.

## Test

The automated tests use fixtures and mocks; they do not require live AI keys, video downloads or a database.

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m unittest discover -s tests -t . -p 'test_*.py'
node --test tests/frontend/*.test.cjs
.venv/bin/ruff check src tests tools
.venv/bin/ruff format --check src tests tools
```

## Repository layout

```text
src/backend/         API, database queries, search and quiz helpers
src/frontend/        HTML, CSS and browser JavaScript
src/data_pipeline/   Data ingestion, OCR and artifact validation
video_timelines/     Runtime synchronization CSVs
tests/               Backend, pipeline, evaluation and frontend tests
tools/evaluation/    Optional benchmark commands
evaluation/          Academic reports, final evidence and shared benchmark inputs
```

[Evaluation](evaluation/README.md) contains the four academic evaluations, their final evidence and reproduction commands. Backend query builders live in `queries.py`, database access in `database.py`, and AI prompts in `prompts.py`. Keep comments in English: start modules with a short purpose statement, use docstrings for non-obvious function contracts, and explain constraints or reasons beside the relevant code. Avoid decorative banners, change history and comments that repeat the next statement. Keep modules grouped by responsibility; extract shared code only when there is actual reuse.

Generated data, downloaded videos, new evaluation outputs and local archives are ignored by Git. Final academic reports, protocols and selected evidence are retained under `evaluation/professor/`. Intermediate research runs, original annotation workbooks and RDF exports remain in an ignored local archive and are not included in a new clone. Git history may still contain previous copies—see [repository publication](#repository-publication).

## Data pipeline

Run commands from the repository root. To create the Play-by-Play JSON and RDF for one game:

```bash
.venv/bin/python src/data_pipeline/parser.py E2023 170
.venv/bin/python src/data_pipeline/validate_action_artifacts.py
```

Omit the game code to process a season. Existing outputs are skipped; `--overwrite` regenerates them. Outputs go to `data/processed/all_actions/` and `data/processed/playbyplay_triplets/`. These local artifacts are also required for OCR evaluation.

Existing video timelines need no OCR installation. To generate a new timeline, install `requirements-ocr.txt`, add a disabled entry to `src/data_pipeline/video_games.json`, and obtain a local full-game video. The entry specifies the YouTube ID, OCR profile, start hint and timeline output path; profiles live in `src/data_pipeline/ocr_profiles.json`.

```bash
.venv/bin/python -m pip install -r requirements-ocr.txt
.venv/bin/python src/data_pipeline/video_ocr.py --list-profiles
.venv/bin/python src/data_pipeline/video_ocr.py --season-code E2023 --game-code 170 --video-file /path/to/game.mp4 --probe-profiles
.venv/bin/python src/data_pipeline/video_ocr.py --season-code E2023 --game-code 170 --video-file /path/to/game.mp4
.venv/bin/python src/data_pipeline/validate_video_timelines.py --season-code E2023 --game-code 170 --strict
```

Replace the example game and video path with the new entry. Enable it only after validation passes and spot-checking synchronization in the video. Keep runtime CSVs in `video_timelines/`; do not commit downloaded videos.

Generate OCR RDF using the catalog and timelines:

```bash
.venv/bin/python src/data_pipeline/ocr_triplets.py E2023 170
```

Missing action artifacts are generated automatically. Output goes to `data/processed/ocr_triplets/`. Import `src/data_pipeline/ocr_schema.nt` once into the RDF store, followed by the generated RDF files. Each command supports `--help` for additional options.

## Known limitations

- Timeline coverage does not guarantee frame-accurate synchronization, especially for stopped-clock events; see the [OCR report](evaluation/professor/3_ocr/REPORT.md).
- Player profiles and photos can reflect older club information. Dunk and alley-oop labels are not available reliably in the source data.
- Statistics have result limits, and AI-generated queries can fail or require correction. Historical benchmark scores are not a guarantee for new questions.
- Public hosting requires HTTPS, persistent backend hosting without `--reload`, appropriate API URL/CORS configuration, access controls and AI request/spending limits. The local commands above are development commands.

## Repository publication

Final academic reports and selected supporting evidence remain in `evaluation/professor/`. Reproducible benchmark questions, human annotations and baseline timelines are retained in `evaluation/fixtures/`. Local report drafts, working spreadsheets and intermediate exports under the ignored `outputs/` directory are not included in a new clone.

Local archives are not included in a new clone or backed up remotely. Completed participant response sheets belong in ignored `outputs/evaluation/user_evaluation/`, not in version control.

Before making the repository public, review all branches and Git history for credentials and private material: deleting or ignoring a file does not erase earlier commits. Review the older `main` branch separately and verify third-party asset/data permissions. Dependencies are pinned directly, not through a complete transitive lockfile.

## License

A license has not been selected yet. Third-party basketball data, photos, team logos and videos are separate from the CourtLens source code; this repository does not grant rights to those materials.
