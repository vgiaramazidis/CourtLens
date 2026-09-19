# CourtLens: UX and system review

Review dates: 18–19 September 2026. Branch: `feature/vasilis`.
This report covers the new search/report experience and representative existing workflows. It is a scoped engineering and visual audit, not a certification of every stored game, browser, AI response, or video timestamp.

## Changes made

- Explore has two local modes, **Ask a question** and **Browse statistics**. The primary navigation still contains exactly Explore, Video Analysis, and Games. Manual reports no longer compete with the AI input underneath it.
- All six manual report types remain available. Shared query filters now handle player names, numeric and alphanumeric player IDs, season/game scope, overtime, and valid clock ranges consistently. Filters use escaped literals and explicit validation. Event deduplication occurs before point aggregation.
- Missing or malformed shot coordinates remain in the table and are excluded from the court. Empty game rosters no longer crash the backend. Database outages return a failure instead of masquerading as no matching results.
- Profile questions such as “Who is Sloukas?” and “I want some info for Sloukas” return stored biography paragraphs, career highlights, a photo, and an official source link. These lookups do not require a working AI provider. Profile information is explicitly separate from season/game statistics and is not represented as a verified current-club feed.
- Game-action answers use canonical Play-by-Play data to compute the counts and scoring they describe. Other question types can receive a short AI explanation grounded in the returned results. A failed explanation does not discard successful query results.
- Provider outages show useful English error messages. The 50/50 quiz stops on a provider error rather than retrying generation repeatedly and eventually misreporting that no suitable data exists.

## Automated verification

| Suite | Result | Coverage |
|---|---:|---|
| Backend unit/regression tests | 79 passed | Search answers, filters, profile routing, request scope, empty/malformed data, provider errors, coach season scope, video mapping, evaluation utilities |
| Data pipeline tests | 69 passed | Parsing, action artifacts, OCR handling, timeline validation, CLI and evaluation behavior |
| Frontend Node tests | 12 passed | Request cancellation, section isolation, filters, video eligibility, names, CSV safety, answer request payloads and actionable error messages |
| JavaScript/Python syntax and Git whitespace checks | Passed | Changed modules and diff |

Commands:

```sh
node --test src/frontend/tests/*.cjs
PYTHONPATH=src/backend:src/data_pipeline .venv/bin/python -m unittest discover -s src/backend -p 'test_*.py'
PYTHONPATH=src/backend:src/data_pipeline .venv/bin/python -m unittest discover -s src/data_pipeline -p 'test_*.py'
.venv/bin/python src/data_pipeline/validate_video_timelines.py --enabled-only
node --check src/frontend/js/main.js
node --check src/frontend/js/api.js
git diff --check
```

The unit tests use fixtures/mocks where appropriate. The live checks below were run separately against the running backend and basketball database.

## Live correctness checks

Reference game: E2023 / 333, Real Madrid–Panathinaikos. Results were independently compared with `data/processed/all_actions/AllActions_E2023_333.json`, rather than compared only with another API view of the same aggregate.

| Check | Verified result |
|---|---|
| Field-goal attempts | 122 |
| Made field goals | 57 |
| Sloukas field-goal attempts | 6, all made |
| Fourth-quarter attempts in the last five minutes | 15 |
| Second-chance scoring | All returned player totals matched saved scoring events |
| Five-player group scoring | All returned group totals matched saved event/lineup membership |
| Fouls drawn | All ten returned leaders matched saved event counts |
| Blocks | The returned total matched the saved block event |
| Passing pairs | All ten returned pairs matched saved assist links |
| Invalid clock interval | HTTP 422 with a useful correction message |
| Nonexistent game roster | Empty roster without a server error |
| Sloukas profile | Name, birth date, biography, achievements, image and source returned |

Live OpenAI searches also verified:

- “How many points did Sloukas score?”: 24 points, derived from 4 made threes, 2 made twos and 8 made free throws in 14 matching scoring plays.
- “Show made three-point shots by Sloukas”: 4 matching actions and 12 points, distributed across quarters 1, 3 and 4. The answer and the frontend Play-by-Play list agree.
- “What was Sloukas's two-point shooting percentage?”: 2 made from 2 attempts, 100%, with a plain-English explanation.

The video test initially exposed a generated explanation claiming two makes while four matching actions were shown. That discrepancy prompted the deterministic action-answer implementation and a dedicated regression test. Rechecking the same question returned four in both places.

These are representative query checks, not an exhaustive evaluation of arbitrary AI-generated SPARQL. Model-generated queries and general explanations still require broader benchmark coverage for production confidence.

## UX, visual and accessibility review

Checked desktop layouts at 1280 pixels and the normal wide preview, and mobile layouts at 390 and 320 pixels.

- Local Explore modes are visually subordinate to the three primary sections. Only the active input/report form is displayed. Switching modes clears previous answers and filters. Resetting the statistics workspace keeps the user in Browse statistics.
- The light white/navy/orange presentation, typography, spacing, restrained borders, and arrow-free action buttons remain consistent with the approved direction. Profiles prioritize readable paragraphs over a wide biography table.
- Player-name report filters work in the actual UI. Selected shots can be inspected; clearing all players produces an empty result and clears selection; resetting filters restores the markers.
- Court/table controls remain available on mobile. The 320-pixel filter dialog fits the viewport; measured document width equals viewport width. The profile also has no horizontal page overflow at 320 pixels.
- Escape closes the native filter dialog and returns focus to its trigger. Reversed clock limits reopen the dialog with a specific error. Controls retain labels, focus styling, and non-color indications of selection.
- Static text contrast checks: primary ink on white 15.87:1; muted text on white 5.66:1; white text on the orange primary button 5.07:1; muted text on the page background 5.23:1. These exceed 4.5:1 for the checked normal-text combinations. This is not a full automated accessibility audit of every state.
- The final profile page has no duplicate DOM IDs, and its browser warning/error log was empty.
- Video Analysis resets the previous query/scope, lists only catalog-eligible games, loads the YouTube embed, and renders the 534 actions for the reference game. Searching narrows the list to the four matching Sloukas threes. A Watch action was exercised; continuous playback and frame-accurate synchronization across all footage were not certified in this review.
- Coach Challenge loaded a real historical scenario, accepted five distinct players, enabled simulation, and produced a result with its simulation/uncertainty label.
- Top 5 loaded a live question and correctly accepted “Tavares”, revealing the answer and updating the found-answer count. The other quiz formats were exercised at API level and encountered the provider outage described below.

## Remaining limitations and follow-up

1. **Provider availability:** Gemini returned 503 high-demand errors during the initial audit. The follow-up below moves Quiz Ball generation to GPT-5 Mini and makes it the default Search provider. All five quiz formats subsequently completed live checks. Gemini remains an optional Search provider; external outages can still affect either provider.
2. **Video timing gaps:** All 28 enabled timelines were structurally valid; 18 were OK and 10 had coverage warnings. Warnings affect E2023 games 60, 160, 296, 331, 333; E2024 games 189, 220, 273, 327; and E2025 game 406. The largest reported gap is 59 seconds in E2024/189, fourth quarter. These source/OCR gaps need separate video-level correction; timing files and catalog eligibility were not changed here.
3. **Stored profiles:** Biography/photo values come from the stored EuroLeague dataset, which can contain historical variants and older uniforms. The source note avoids claiming live roster accuracy. The official profile link is available for the full record.
4. **Result limits:** Manual shots return at most 500 events and rankings at most ten entries; the report description makes those limits visible. Broad, all-season output should not be interpreted as a full export of every event.
5. **Deployment/browser scope:** Checks used the local application, its configured live providers, and the Codex browser. Cross-browser/device testing, production HTTPS/CORS configuration, load testing, and a full screen-reader audit remain outside the completed checks.


## Follow-up: team logos, query errors, and shot-style requests

- Live `/api/teams` returned 89 team records with `foaf:depiction` logo URLs. The frontend uses those URLs in game headings and Coach Challenge matchups, with initials if a logo is unavailable or fails to load.
- The read-only validator previously searched command words inside literals, IRIs, and comments. It now checks command tokens outside those regions. Actual update and SERVICE commands remain rejected. Normal UI requests get one repair attempt and a plain-English error if both generated queries fail; evaluation requests retain technical diagnostics.
- Added eight regression tests for logos, lexical validation, bounded repair, and unsupported shot-style intent. All eight and the twelve frontend tests passed; the existing 79 backend tests also passed after the implementation.
- Verified the reference game's live SPARQL action fields and its official PlaybyPlay/Points feeds. They do not supply dunk/alley-oop labels. Search now recognizes dunk, alley-oop (including common misspellings), layup, floater and related technique requests, but explains that the current dataset cannot identify them reliably. It does not substitute all assisted two-pointers or report a misleading zero-match result. Supporting exact results requires a source with shot-technique labels or reviewed video annotations linked to action IDs.


## Follow-up: game labels, player roles and Quiz Ball

- All game choices in the shared Explore/Video Analysis selector include their game number. Stored phase/group/round metadata supplies Final, Semi-final, Third-place game, Playoffs, Play-in and Regular season labels. Live E2023 checks verified games 333, 332, 331 and 330 against their database stages. The video list remains restricted to catalog-eligible games.
- Coach Challenge displays stored Guard, Forward and Center roles beside each available player, merging multiple recorded roles. A short role guide explains them. No unsupported point-guard/shooting-guard specialization is inferred. Scenario headings also display the game number.
- GPT-5 Mini is the default Search model in application defaults, the example configuration and the local configuration. Generated Quiz Ball questions use OpenAI only; Top 5 remains deterministic and works without an AI key. All five formats returned HTTP 200 in live tests (roughly 1–6 seconds each during this run).
- Who is missing? now shows four player photos and a missing role on an illustrative half court. The missing player's identity/photo is not rendered before the answer. A correct full-name answer filled the missing slot and displayed the source-backed profile.
- Who am I? reveals a photo, position, country, biography, achievements and source after the round. A live correct “Diego Flaccadori” answer was accepted; the photo loaded and the country displayed as Italy. Historical profile caveats remain visible.
- The Larkin regression is covered: canonical full names take precedence over jersey surnames; legacy surname answers expand only through an unambiguous known full name. Accent differences, reversed full-name order, compound surnames and common generational suffixes are accepted. Wrong first names and incomplete passing-pair answers are rejected.
- Additional correctness fix: fast-break Top 5 queries now use the season/game/period described in the question, rather than using all-season totals under a season-specific heading.
- Automated checks: 95 backend tests and 16 frontend tests pass, including new identity, metadata, provider-selection, hidden-player and season-scope regressions. JavaScript syntax and whitespace checks pass.
- Manual browser checks covered desktop, 390-pixel mobile and a 320-pixel missing-player court, roster selection, correct/incorrect quiz guesses, clue progression, loaded profile photos, game labels and the selected GPT-5 Mini model. Checked mobile views had document width equal to viewport width.

The final 320-pixel court check showed five slots, all four known-player photos loaded, no horizontal overflow and an empty browser warning/error log. Live fast-break queries for E2023 and E2024 returned distinct season-scoped totals; combined profile roles were verified as `Forward / Guard`.
