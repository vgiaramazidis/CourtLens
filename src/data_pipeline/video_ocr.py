"""Generate a game-clock-to-video timeline from a full-game broadcast.

OCR layout details live in ``ocr_profiles.json`` and game-specific details live
in ``video_games.json``. A new game that uses an existing broadcast layout only
needs a catalog entry; it does not need Python code changes.
"""

from __future__ import annotations

import argparse
import csv
import importlib.metadata
import json
import os
import platform
import re
import shutil
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
DEFAULT_PROFILES_FILE = SCRIPT_DIR / "ocr_profiles.json"
DEFAULT_CATALOG_FILE = SCRIPT_DIR / "video_games.json"

# A halftime highlight can look like the next period when only the game clock
# is available. Permit one guarded correction only while the inferred period
# still consists of a tiny opening fragment, and confirm the replacement with
# three consecutive readings near the real period start.
PERIOD_REBASE_MIN_VIDEO_GAP_SECONDS = 300
PERIOD_REBASE_START_MIN_RATIO = 0.95
PERIOD_REBASE_MAX_INITIAL_OBSERVATIONS = 10
PERIOD_REBASE_MAX_INITIAL_CLOCK_SPAN_SECONDS = 30
PERIOD_REBASE_MIN_CLOCK_IMPROVEMENT_SECONDS = 10
PERIOD_REBASE_CONFIRMATION_READINGS = 3
PERIOD_REBASE_MAX_CONFIRMATION_GAP_SECONDS = 5

# A halftime highlight package can contain clocks from other games and mimic
# the next period. A real game clock cannot consume hundreds of seconds in a
# much shorter video interval. Roll such a candidate period back only after a
# substantial clock span makes the contradiction unambiguous.
COMPRESSED_PERIOD_MIN_CLOCK_SPAN_SECONDS = 300
COMPRESSED_PERIOD_MIN_VIDEO_CLOCK_RATIO = 0.5

# A full-game run should begin with a short, descending sequence near the
# start of the first period. This prevents a clock-like token in a pre-game
# graphic from becoming the tracker's initial reference point.
INITIAL_CLOCK_CONFIRMATION_READINGS = 3
INITIAL_CLOCK_MAX_CONFIRMATION_GAP_SECONDS = 5
INITIAL_CLOCK_MAX_RATE_DRIFT_SECONDS = 1.5
# Some broadcasts start the game at 10:00, immediately stop the clock because
# of a table/clock problem, and resume several minutes of video later. Preserve
# the first full-period clock only when it was read on more than one frame and
# a genuine descending opening sequence subsequently confirms the period.
INITIAL_CLOCK_ANCHOR_MIN_READINGS = 2
INITIAL_CLOCK_ANCHOR_MAX_CONFIRMATION_DELAY_SECONDS = 300

# After a long gap in readable clocks, the first new OCR token is unusually
# risky: it may be a replay, a correction animation or a one-frame digit
# error. Confirm any large drop with a short real-time descending sequence.
# This also handles a scorebug that remained frozen throughout a timeout.
GAPPED_CLOCK_MIN_VIDEO_GAP_SECONDS = 10
GAPPED_CLOCK_MIN_DROP_SECONDS = 8
GAPPED_CLOCK_CONFIRMATION_READINGS = 3
GAPPED_CLOCK_MAX_CONFIRMATION_GAP_SECONDS = 120
GAPPED_CLOCK_MAX_RATE_DRIFT_SECONDS = 1.5

# EuroLeague overtime follows the fourth period or another overtime after a
# short break. A late post-game replay showing an overtime-like clock must not
# create a period that was never played.
OVERTIME_START_MAX_VIDEO_GAP_SECONDS = 300
REQUIRED_REGULATION_PERIODS = ("1st", "2nd", "3rd", "4th")
GENERATED_PERIOD_MAX_LATE_START_SECONDS = 60
GENERATED_PERIOD_MAX_EARLY_END_SECONDS = 15


def clock_to_seconds(clock: str | None) -> float | None:
    if not clock:
        return None
    try:
        if ":" in clock:
            minutes, seconds = clock.split(":", 1)
            value = int(minutes) * 60 + int(seconds)
            return float(value) if 0 <= int(seconds) < 60 else None
        if "." in clock:
            return float(clock)
    except (TypeError, ValueError):
        return None
    return None


def parse_clock(text: str) -> str | None:
    normalized = (
        text.upper()
        .strip()
        .replace("O", "0")
        .replace("I", "1")
        .replace("S", "5")
        .replace("B", "8")
        .replace("Z", "2")
    )
    # Some scorebug fonts make ':' look like '.', so 7.24 is also 7:24.
    # A single digit after the separator (for example 15.9) remains a decimal clock.
    match_mmss = re.search(r"(?<!\d)(\d{1,2})[\.:](\d{2})(?!\d)", normalized)
    if match_mmss:
        clock = f"{match_mmss.group(1)}:{match_mmss.group(2)}"
        return clock if clock_to_seconds(clock) is not None else None

    match_decimal = re.search(r"(?<!\d)(\d{1,2}[\.:]\d)(?!\d)", normalized)
    if match_decimal:
        clock = match_decimal.group(1).replace(":", ".")
        seconds = clock_to_seconds(clock)
        return clock if seconds is not None and seconds < 60 else None

    # EasyOCR occasionally drops the separator while keeping every digit
    # (for example, ``7:41`` becomes ``741``). Accept only a complete 3- or
    # 4-digit MMSS token with a valid seconds component; ClockTracker still
    # enforces the period duration and temporal-jump safeguards afterwards.
    match_compact_mmss = re.fullmatch(r"\d{3,4}", normalized)
    if match_compact_mmss:
        digits = match_compact_mmss.group(0)
        clock = f"{digits[:-2]}:{digits[-2:]}"
        return clock if clock_to_seconds(clock) is not None else None
    return None


def advance_descending_confirmation(
    pending: tuple[float, float, int] | None,
    current_seconds: float,
    video_time: float,
    required_readings: int,
    max_video_gap_seconds: float,
    max_rate_drift_seconds: float,
) -> tuple[str, tuple[float, float, int] | None]:
    """Advance a real-time descending clock confirmation sequence."""
    if pending is None:
        return "started", (current_seconds, video_time, 1)

    pending_seconds, pending_video_time, count = pending
    video_gap = video_time - pending_video_time
    clock_drop = pending_seconds - current_seconds
    if 0 < video_gap <= max_video_gap_seconds and (
        0 < clock_drop <= video_gap + max_rate_drift_seconds
    ):
        next_pending = (current_seconds, video_time, count + 1)
        if count + 1 >= required_readings:
            return "confirmed", None
        return "pending", next_pending

    if current_seconds == pending_seconds and 0 < video_gap <= max_video_gap_seconds:
        # A stopped clock neither confirms nor invalidates the candidate. Use
        # the newest frame as the reference for the next moving clock.
        return "holding", (current_seconds, video_time, count)

    return "rejected", None


@dataclass
class InitialClockGate:
    """Require a plausible first-period clock sequence before tracking."""

    period_seconds: float
    minimum_start_ratio: float
    pending: tuple[float, float, int] | None = None
    opening_anchor: tuple[float, str] | None = None
    opening_anchor_readings: int = 0
    confirmed_backfill: tuple[float, str] | None = None
    last_decision: str = "not_evaluated"

    def accept(self, clock: str, video_time: float) -> bool:
        seconds = clock_to_seconds(clock)
        if seconds is None:
            self.last_decision = "initial_invalid_clock"
            return False
        if seconds < self.period_seconds * self.minimum_start_ratio:
            self.pending = None
            self.last_decision = "initial_clock_below_start_window"
            return False

        if abs(seconds - self.period_seconds) <= 0.1:
            if self.opening_anchor is None:
                self.opening_anchor = (video_time, clock)
            self.opening_anchor_readings += 1

        status, self.pending = advance_descending_confirmation(
            self.pending,
            seconds,
            video_time,
            INITIAL_CLOCK_CONFIRMATION_READINGS,
            INITIAL_CLOCK_MAX_CONFIRMATION_GAP_SECONDS,
            INITIAL_CLOCK_MAX_RATE_DRIFT_SECONDS,
        )
        self.last_decision = f"initial_clock_confirmation_{status}"
        if status == "confirmed" and self.opening_anchor is not None:
            anchor_video_time, anchor_clock = self.opening_anchor
            confirmation_delay = video_time - anchor_video_time
            if (
                self.opening_anchor_readings >= INITIAL_CLOCK_ANCHOR_MIN_READINGS
                and 0 <= confirmation_delay <= INITIAL_CLOCK_ANCHOR_MAX_CONFIRMATION_DELAY_SECONDS
            ):
                self.confirmed_backfill = (anchor_video_time, anchor_clock)
        return status == "confirmed"

    def take_confirmed_backfill(self) -> tuple[float, str] | None:
        """Return and clear a confirmed full-period opening observation."""
        backfill = self.confirmed_backfill
        self.confirmed_backfill = None
        return backfill


def load_json(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
    except FileNotFoundError as exc:
        raise ValueError(f"Configuration file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Configuration root must be an object: {path}")
    return payload


def load_profiles(path: Path) -> dict[str, dict[str, Any]]:
    profiles = load_json(path).get("profiles")
    if not isinstance(profiles, dict) or not profiles:
        raise ValueError(f"No OCR profiles found in {path}")

    for name, profile in profiles.items():
        if not isinstance(profile, dict):
            raise ValueError(f"OCR profile '{name}' must be an object")
        roi = profile.get("roi", {})
        for field in ("x", "y", "width", "height"):
            value = roi.get(field)
            if not isinstance(value, (int, float)) or not 0 <= value <= 1:
                raise ValueError(f"Profile '{name}' ROI '{field}' must be between 0 and 1")
        if roi["width"] <= 0 or roi["height"] <= 0:
            raise ValueError(f"Profile '{name}' ROI width and height must be positive")
        if roi["x"] + roi["width"] > 1 or roi["y"] + roi["height"] > 1:
            raise ValueError(f"Profile '{name}' ROI extends outside the frame")
    return profiles


def load_game_catalog(path: Path) -> list[dict[str, Any]]:
    games = load_json(path).get("games")
    if not isinstance(games, list):
        raise ValueError(f"Game catalog must contain a 'games' list: {path}")
    return [game for game in games if isinstance(game, dict)]


def find_game_config(
    games: list[dict[str, Any]], season_code: str, game_code: str
) -> dict[str, Any] | None:
    return next(
        (
            game
            for game in games
            if str(game.get("season_code")) == season_code
            and str(game.get("game_code")) == game_code
        ),
        None,
    )


def resolve_repo_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else REPO_ROOT / path


def youtube_url_from_id(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


@dataclass(frozen=True)
class OcrRunStatistics:
    timeline_points: int
    removed_points: int
    fps: float
    media_duration_seconds: float | None
    scan_start_seconds: float
    scan_end_seconds: float
    sampling_interval_seconds: float

    @property
    def scanned_video_seconds(self) -> float:
        return max(0.0, self.scan_end_seconds - self.scan_start_seconds)


@dataclass
class ClockTracker:
    periods: list[str]
    regular_period_seconds: int = 600
    overtime_period_seconds: int = 300
    period_end_max_seconds: float = 15
    period_start_min_ratio: float = 0.9
    max_upward_jump_seconds: float = 3
    max_downward_jump_seconds: float = 15
    period_index: int = 0
    last_clock: str | None = None
    last_video_time: float | None = None
    last_seen_video_time: float | None = None
    pending_single_digit_decimal: str | None = None
    pending_gapped_clock_drop: tuple[float, float, int] | None = None
    pending_gapped_clock_backfills: tuple[tuple[float, str, str], ...] = ()
    confirmed_gapped_clock_backfills: tuple[tuple[float, str, str], ...] = ()
    period_observation_count: int = 0
    period_first_seconds: float | None = None
    period_start_video_time: float | None = None
    previous_period_end_state: (
        tuple[
            int,
            str,
            float | None,
            float | None,
            float | None,
            int,
        ]
        | None
    ) = None
    invalidated_period: tuple[str, float] | None = None
    pending_period_rebase: tuple[float, float, int] | None = None
    last_decision: str = "not_evaluated"

    @classmethod
    def from_profile(cls, profile: dict[str, Any]) -> "ClockTracker":
        config = profile.get("clock_tracking", {})
        periods = config.get("periods") or ["1st", "2nd", "3rd", "4th", "OT"]
        return cls(
            periods=[str(period) for period in periods],
            regular_period_seconds=int(config.get("regular_period_seconds", 600)),
            overtime_period_seconds=int(config.get("overtime_period_seconds", 300)),
            period_end_max_seconds=float(config.get("period_end_max_seconds", 15)),
            period_start_min_ratio=float(config.get("period_start_min_ratio", 0.9)),
            max_upward_jump_seconds=float(config.get("max_upward_jump_seconds", 3)),
            max_downward_jump_seconds=float(config.get("max_downward_jump_seconds", 15)),
        )

    @property
    def period(self) -> str:
        return self.periods[self.period_index]

    def period_duration(self, index: int | None = None) -> int:
        target_index = self.period_index if index is None else index
        return self.regular_period_seconds if target_index < 4 else self.overtime_period_seconds

    def _can_start_period_rebase(
        self,
        previous_seconds: float,
        current_seconds: float,
        video_time: float | None,
    ) -> bool:
        """Identify a short highlight fragment before the real period start."""
        if (
            self.period_index == 0
            or video_time is None
            or self.last_video_time is None
            or self.period_first_seconds is None
            or self.period_observation_count > PERIOD_REBASE_MAX_INITIAL_OBSERVATIONS
        ):
            return False
        duration = self.period_duration()
        initial_span = self.period_first_seconds - previous_seconds
        return (
            0 <= initial_span <= PERIOD_REBASE_MAX_INITIAL_CLOCK_SPAN_SECONDS
            and video_time - self.last_video_time >= PERIOD_REBASE_MIN_VIDEO_GAP_SECONDS
            and current_seconds >= duration * PERIOD_REBASE_START_MIN_RATIO
            and current_seconds - self.period_first_seconds
            >= PERIOD_REBASE_MIN_CLOCK_IMPROVEMENT_SECONDS
        )

    def _advance_period_rebase(
        self,
        current_seconds: float,
        video_time: float | None,
    ) -> str:
        """Return pending, confirmed, or rejected for a rebase sequence."""
        if self.pending_period_rebase is None or video_time is None:
            return "rejected"
        pending_seconds, pending_video_time, count = self.pending_period_rebase
        video_gap = video_time - pending_video_time
        clock_drop = pending_seconds - current_seconds
        if (
            0 < video_gap <= PERIOD_REBASE_MAX_CONFIRMATION_GAP_SECONDS
            and 0 < clock_drop <= video_gap + 5
        ):
            count += 1
            self.pending_period_rebase = (current_seconds, video_time, count)
            return "confirmed" if count >= PERIOD_REBASE_CONFIRMATION_READINGS else "pending"
        self.pending_period_rebase = None
        return "rejected"

    def _reject(self, reason: str) -> None:
        self.last_decision = reason
        return None

    def take_confirmed_backfills(self) -> tuple[tuple[float, str, str], ...]:
        """Return and clear clocks withheld while a gapped sequence was confirmed."""
        backfills = self.confirmed_gapped_clock_backfills
        self.confirmed_gapped_clock_backfills = ()
        return backfills

    def take_invalidated_period(self) -> tuple[str, float] | None:
        """Return and clear a period rejected as temporally impossible."""
        invalidated = self.invalidated_period
        self.invalidated_period = None
        return invalidated

    def _rollback_compressed_period(
        self,
        current_seconds: float,
        video_time: float | None,
    ) -> bool:
        """Undo a highlight period whose clock runs impossibly fast."""
        if (
            video_time is None
            or self.period_start_video_time is None
            or self.period_first_seconds is None
            or self.previous_period_end_state is None
        ):
            return False
        clock_span = self.period_first_seconds - current_seconds
        video_span = video_time - self.period_start_video_time
        if (
            clock_span < COMPRESSED_PERIOD_MIN_CLOCK_SPAN_SECONDS
            or video_span >= clock_span * COMPRESSED_PERIOD_MIN_VIDEO_CLOCK_RATIO
        ):
            return False

        invalid_period = self.period
        invalid_start = self.period_start_video_time
        (
            self.period_index,
            self.last_clock,
            self.last_video_time,
            self.last_seen_video_time,
            self.period_first_seconds,
            self.period_observation_count,
        ) = self.previous_period_end_state
        self.previous_period_end_state = None
        self.period_start_video_time = None
        self.pending_period_rebase = None
        self.pending_single_digit_decimal = None
        self.pending_gapped_clock_drop = None
        self.pending_gapped_clock_backfills = ()
        self.confirmed_gapped_clock_backfills = ()
        self.invalidated_period = (invalid_period, invalid_start)
        return True

    def accept(self, clock: str, video_time: float | None = None) -> tuple[str, str] | None:
        current_seconds = clock_to_seconds(clock)
        if current_seconds is None:
            return self._reject("invalid_clock")
        if clock == self.last_clock:
            # Track how long the scorebug remains frozen without replacing the
            # time of the last real clock change. Both values are needed to
            # distinguish a resumed game from a correction animation.
            if video_time is not None:
                self.last_seen_video_time = video_time
            self.pending_gapped_clock_drop = None
            self.pending_gapped_clock_backfills = ()
            return self._reject("duplicate_clock")
        if current_seconds > self.period_duration() + 1:
            return self._reject("clock_exceeds_period_duration")

        previous_seconds = clock_to_seconds(self.last_clock)
        confirmed_single_digit_decimal = False
        accepted_reason = "accepted"
        is_period_reset = False
        if self.pending_single_digit_decimal is not None:
            pending_seconds = clock_to_seconds(self.pending_single_digit_decimal)
            self.pending_single_digit_decimal = None
            if (
                pending_seconds is not None
                # Repeating the same truncated value is not confirmation. In
                # E2024/220, 43.3 was read twice as 3.3 while the clock was
                # stopped; accepting the second reading poisoned every later
                # frame. A real running final-seconds clock must move down.
                and 0 < pending_seconds - current_seconds <= self.max_downward_jump_seconds
            ):
                # Two consecutive final-seconds readings confirm that the large
                # clock drop was real. The first reading remains omitted.
                confirmed_single_digit_decimal = True

        if previous_seconds is not None:
            next_index = min(self.period_index + 1, len(self.periods) - 1)
            next_period_start = self.period_duration(next_index) * self.period_start_min_ratio
            enough_time_for_period_end = True
            if video_time is not None and self.last_video_time is not None:
                elapsed_video_time = max(0.0, video_time - self.last_video_time)
                # A decimal final-seconds clock such as 9.4 can be misread as
                # 9:24. It cannot represent the next period if only a couple
                # of video seconds have elapsed since 11.4 remained.
                enough_time_for_period_end = elapsed_video_time + 5 >= previous_seconds
            is_period_reset = (
                self.period_index < len(self.periods) - 1
                and previous_seconds <= self.period_end_max_seconds
                and current_seconds >= next_period_start
                and current_seconds <= self.period_duration(next_index) + 1
                and enough_time_for_period_end
            )
            if (
                is_period_reset
                and next_index >= 4
                and video_time is not None
                and self.last_video_time is not None
                and video_time - self.last_video_time > OVERTIME_START_MAX_VIDEO_GAP_SECONDS
            ):
                is_period_reset = False
            if is_period_reset:
                self.previous_period_end_state = (
                    self.period_index,
                    str(self.last_clock),
                    self.last_video_time,
                    self.last_seen_video_time,
                    self.period_first_seconds,
                    self.period_observation_count,
                )
                self.period_index += 1
                self.period_observation_count = 0
                self.period_first_seconds = None
                self.period_start_video_time = None
                self.pending_period_rebase = None
                self.pending_gapped_clock_drop = None
                self.pending_gapped_clock_backfills = ()
                accepted_reason = "accepted_period_reset"
            else:
                change = current_seconds - previous_seconds
                confirmed_period_rebase = False
                if self.pending_period_rebase is not None:
                    rebase_status = self._advance_period_rebase(current_seconds, video_time)
                    if rebase_status == "pending":
                        return self._reject("period_rebase_confirmation_pending")
                    confirmed_period_rebase = rebase_status == "confirmed"
                if (
                    not confirmed_period_rebase
                    and change > self.max_upward_jump_seconds
                    and self._can_start_period_rebase(previous_seconds, current_seconds, video_time)
                ):
                    self.pending_period_rebase = (
                        current_seconds,
                        float(video_time),
                        1,
                    )
                    return self._reject("period_rebase_candidate_pending")
                if change > self.max_upward_jump_seconds:
                    if not confirmed_period_rebase:
                        return self._reject("upward_jump_too_large")
                is_suspicious_single_digit_decimal = (
                    not confirmed_period_rebase
                    and not confirmed_single_digit_decimal
                    and re.fullmatch(r"\d\.\d", clock) is not None
                    and previous_seconds >= 15
                    and previous_seconds - current_seconds >= 10
                )
                if is_suspicious_single_digit_decimal:
                    # EasyOCR can drop an internal digit (for example, read
                    # 51.3 as 5.3). Do not let one such frame move the tracker
                    # into the final seconds and make subsequent correct clocks
                    # look like impossible upward jumps. A second compatible
                    # final-seconds frame confirms a genuine large drop.
                    self.pending_single_digit_decimal = clock
                    return self._reject("single_digit_decimal_confirmation_pending")
                confirmed_gapped_clock_drop = False
                if self.pending_gapped_clock_drop is not None and video_time is not None:
                    gap_status, self.pending_gapped_clock_drop = advance_descending_confirmation(
                        self.pending_gapped_clock_drop,
                        current_seconds,
                        video_time,
                        GAPPED_CLOCK_CONFIRMATION_READINGS,
                        GAPPED_CLOCK_MAX_CONFIRMATION_GAP_SECONDS,
                        GAPPED_CLOCK_MAX_RATE_DRIFT_SECONDS,
                    )
                    if gap_status in {"pending", "holding"}:
                        pending_result = (video_time, self.period, clock)
                        if (
                            not self.pending_gapped_clock_backfills
                            or self.pending_gapped_clock_backfills[-1][2] != clock
                        ):
                            self.pending_gapped_clock_backfills += (pending_result,)
                        return self._reject("gapped_clock_drop_confirmation_pending")
                    if gap_status == "confirmed":
                        confirmed_gapped_clock_drop = True
                        self.confirmed_gapped_clock_backfills = self.pending_gapped_clock_backfills
                    self.pending_gapped_clock_backfills = ()

                if (
                    not confirmed_period_rebase
                    and not confirmed_single_digit_decimal
                    and not confirmed_gapped_clock_drop
                    and change < 0
                    and video_time is not None
                    and self.last_video_time is not None
                    and video_time - self.last_video_time >= GAPPED_CLOCK_MIN_VIDEO_GAP_SECONDS
                    and previous_seconds - current_seconds >= GAPPED_CLOCK_MIN_DROP_SECONDS
                ):
                    video_gap = video_time - self.last_video_time
                    clock_drop = previous_seconds - current_seconds
                    if clock_drop > video_gap + 5:
                        # A replay can show a perfectly descending clock from
                        # another moment, but no real game clock can consume
                        # more time than elapsed in the video. Do not let that
                        # sequence poison the next genuine reading.
                        self.pending_gapped_clock_drop = None
                        self.pending_gapped_clock_backfills = ()
                        return self._reject("gapped_clock_drop_faster_than_video")
                    self.pending_gapped_clock_drop = (
                        current_seconds,
                        video_time,
                        1,
                    )
                    self.pending_gapped_clock_backfills = (
                        (
                            video_time,
                            self.period,
                            clock,
                        ),
                    )
                    return self._reject("gapped_clock_drop_confirmation_pending")

                if not confirmed_period_rebase and not confirmed_gapped_clock_drop:
                    allowed_downward_jump = self.max_downward_jump_seconds
                    if video_time is not None and self.last_video_time is not None:
                        elapsed_video_time = max(0.0, video_time - self.last_video_time)
                        allowed_downward_jump = min(
                            allowed_downward_jump,
                            elapsed_video_time + 5,
                        )
                    if -change > allowed_downward_jump:
                        return self._reject("downward_jump_faster_than_video")

                if confirmed_period_rebase:
                    self.period_observation_count = 0
                    self.period_first_seconds = None
                    self.period_start_video_time = None
                    self.pending_period_rebase = None
                    accepted_reason = "accepted_period_rebase"
                elif confirmed_single_digit_decimal:
                    accepted_reason = "accepted_confirmed_single_digit_decimal"
                elif confirmed_gapped_clock_drop:
                    accepted_reason = "accepted_confirmed_gapped_clock_drop"

        if not is_period_reset and self._rollback_compressed_period(
            current_seconds,
            video_time,
        ):
            return self._reject("temporally_compressed_period")

        self.last_clock = clock
        self.last_video_time = video_time
        self.last_seen_video_time = video_time
        if self.period_first_seconds is None:
            self.period_first_seconds = current_seconds
            self.period_start_video_time = video_time
        self.period_observation_count += 1
        self.last_decision = accepted_reason
        return self.period, clock


def roi_pixels(
    profile: dict[str, Any], frame_width: int, frame_height: int
) -> tuple[int, int, int, int]:
    roi = profile["roi"]
    x = max(0, min(frame_width - 1, round(float(roi["x"]) * frame_width)))
    y = max(0, min(frame_height - 1, round(float(roi["y"]) * frame_height)))
    width = max(1, round(float(roi["width"]) * frame_width))
    height = max(1, round(float(roi["height"]) * frame_height))
    return x, y, min(width, frame_width - x), min(height, frame_height - y)


def sanitize_timeline_results(
    results: list[tuple[float, str, str]],
    trace: Callable[[str], None] | None = None,
) -> tuple[list[tuple[float, str, str]], int]:
    """Keep each period monotonic and prefer the latest duplicate clock reading.

    Broadcast replays and official clock corrections can briefly reintroduce a
    higher clock value. Removing the conflicting older tail prevents play links
    from seeking to a replay or pre-correction timestamp.
    """
    sanitized: list[tuple[float, str, str]] = []
    removed = 0
    for result in results:
        _video_time, period, clock = result
        current_seconds = clock_to_seconds(clock)
        if current_seconds is None:
            removed += 1
            if trace:
                trace(f"[TRACE POST] {result} decision=discard_invalid_clock")
            continue

        while sanitized and sanitized[-1][1] == period:
            previous_seconds = clock_to_seconds(sanitized[-1][2])
            if previous_seconds is None or current_seconds > previous_seconds:
                removed_result = sanitized.pop()
                removed += 1
                if trace:
                    trace(
                        f"[TRACE POST] {removed_result} "
                        f"decision=discard_older_conflicting_tail "
                        f"replacement={result}"
                    )
                continue
            if current_seconds == previous_seconds:
                if current_seconds <= 0.1:
                    # The first zero is the period-ending horn. Later zeroes
                    # commonly come from replays, post-game graphics or
                    # interviews and must not move the video link forward.
                    removed += 1
                    if trace:
                        trace(
                            f"[TRACE POST] {result} "
                            "decision=discard_duplicate_period_end_keep_first "
                            f"preserved={sanitized[-1]}"
                        )
                    break
                removed_result = sanitized[-1]
                sanitized[-1] = result
                removed += 1
                if trace:
                    trace(
                        f"[TRACE POST] {removed_result} "
                        f"decision=discard_duplicate_prefer_latest "
                        f"replacement={result}"
                    )
                break
            sanitized.append(result)
            break
        else:
            sanitized.append(result)
    return sanitized, removed


def remove_temporally_impossible_results(
    results: list[tuple[float, str, str]],
    grace_seconds: float = 5,
    trace: Callable[[str], None] | None = None,
) -> tuple[list[tuple[float, str, str]], int]:
    """Reject clock drops that are faster than the elapsed video time."""
    sanitized: list[tuple[float, str, str]] = []
    removed = 0
    for result in results:
        video_time, period, clock = result
        if sanitized and sanitized[-1][1] == period:
            previous_video_time, _previous_period, previous_clock = sanitized[-1]
            previous_seconds = clock_to_seconds(previous_clock)
            current_seconds = clock_to_seconds(clock)
            if (
                previous_seconds is not None
                and current_seconds is not None
                and previous_seconds - current_seconds
                > video_time - previous_video_time + grace_seconds
            ):
                removed += 1
                if trace:
                    trace(
                        f"[TRACE POST] {result} "
                        f"decision=discard_clock_drop_faster_than_video "
                        f"previous={sanitized[-1]}"
                    )
                continue
        sanitized.append(result)
    return sanitized, removed


def timeline_completeness_errors(
    results: list[tuple[float, str, str]],
) -> list[str]:
    """Return fatal coverage problems for a generated full-game timeline."""
    by_period: dict[str, list[float]] = {}
    for _video_time, period, clock in results:
        seconds = clock_to_seconds(clock)
        if seconds is not None:
            by_period.setdefault(period, []).append(seconds)

    errors: list[str] = []
    for period in REQUIRED_REGULATION_PERIODS:
        clocks = by_period.get(period)
        if not clocks:
            errors.append(f"missing {period}")
            continue
        if clocks[0] < 600 - GENERATED_PERIOD_MAX_LATE_START_SECONDS:
            errors.append(f"{period} starts too late at {clocks[0]:g}s")
        if clocks[-1] > GENERATED_PERIOD_MAX_EARLY_END_SECONDS:
            errors.append(f"{period} ends too early at {clocks[-1]:g}s")
    return errors


def get_stream_url(
    url: str,
    yt_dlp_module: Any,
    cookies_from_browser: str | None = None,
) -> str:
    options: dict[str, Any] = {
        # OpenCV needs a progressive HTTP file for reliable random frame seeks;
        # authenticated YouTube sessions otherwise prefer an HLS manifest.
        "format": "18/best[protocol=https][ext=mp4]/best[protocol=https]",
        "quiet": True,
        "extractor_retries": 5,
        "remote_components": {"ejs:github"},
    }
    if node_path := shutil.which("node"):
        options["js_runtimes"] = {"node": {"path": node_path}}
    if cookies_from_browser:
        options["cookiesfrombrowser"] = (cookies_from_browser, None, None, None)
    with yt_dlp_module.YoutubeDL(options) as downloader:
        info = downloader.extract_info(url, download=False)
        return str(info["url"])


def preprocess_roi(roi: Any, profile: dict[str, Any], cv2_module: Any) -> Any:
    config = profile.get("preprocess", {})
    gray = cv2_module.cvtColor(roi, cv2_module.COLOR_BGR2GRAY)
    scale = float(config.get("scale", 3.0))
    if scale != 1:
        gray = cv2_module.resize(
            gray, None, fx=scale, fy=scale, interpolation=cv2_module.INTER_CUBIC
        )

    threshold = str(config.get("threshold", "otsu"))
    invert_flag = cv2_module.THRESH_BINARY_INV if config.get("invert") else cv2_module.THRESH_BINARY
    if threshold == "otsu":
        _, gray = cv2_module.threshold(gray, 0, 255, invert_flag + cv2_module.THRESH_OTSU)
    elif threshold == "adaptive":
        gray = cv2_module.adaptiveThreshold(
            gray,
            255,
            cv2_module.ADAPTIVE_THRESH_GAUSSIAN_C,
            invert_flag,
            21,
            5,
        )
    elif threshold != "none":
        raise ValueError(f"Unsupported threshold mode: {threshold}")
    return gray


def run_ocr(
    youtube_url: str,
    profile: dict[str, Any],
    start_seconds: float,
    output_path: Path,
    debug_dir: Path,
    save_debug_frames: bool,
    cookies_from_browser: str | None = None,
    video_file: Path | None = None,
    trace_frames: bool = False,
) -> OcrRunStatistics:
    try:
        import cv2
        import easyocr
        import yt_dlp
    except ImportError as exc:
        raise RuntimeError(
            "OCR dependencies are missing. Install opencv-python, easyocr, and yt-dlp."
        ) from exc

    ocr_config = profile.get("ocr", {})
    reader = easyocr.Reader(ocr_config.get("languages", ["en"]), gpu=False)
    stream_url = (
        str(video_file.resolve())
        if video_file is not None
        else get_stream_url(youtube_url, yt_dlp, cookies_from_browser)
    )
    capture = cv2.VideoCapture(stream_url)
    if not capture.isOpened():
        raise RuntimeError("Could not open the YouTube video stream")

    fps = float(capture.get(cv2.CAP_PROP_FPS) or 25)
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    frame_id = max(0, int(start_seconds * fps))
    interval_seconds = float(profile.get("sampling", {}).get("interval_seconds", 1.0))
    post_final_period_seconds = float(
        profile.get("sampling", {}).get("post_final_period_seconds", 900.0)
    )
    frame_step = max(1, round(fps * interval_seconds))
    media_duration_seconds = frame_count / fps if frame_count > 0 else None
    last_sampled_video_time = start_seconds
    confidence_threshold = float(ocr_config.get("confidence_threshold", 0.4))
    allowlist = str(ocr_config.get("allowlist", "0123456789:."))
    tracker = ClockTracker.from_profile(profile)
    initial_clock_gate = InitialClockGate(
        period_seconds=float(tracker.regular_period_seconds),
        minimum_start_ratio=tracker.period_start_min_ratio,
    )
    results: list[tuple[float, str, str]] = []
    completed_period_index: int | None = None
    completed_period_video_time: float | None = None

    if save_debug_frames:
        debug_dir.mkdir(parents=True, exist_ok=True)

    print(f"Processing {youtube_url}")
    print(
        f"FPS: {fps:.2f}; starting at {start_seconds:.2f}s; sampling every {interval_seconds:.2f}s"
    )

    while frame_count <= 0 or frame_id < frame_count:
        capture.set(cv2.CAP_PROP_POS_FRAMES, frame_id)
        ok, frame = capture.read()
        if not ok:
            break

        frame_height, frame_width = frame.shape[:2]
        x, y, width, height = roi_pixels(profile, frame_width, frame_height)
        roi = frame[y : y + height, x : x + width]
        if roi.size == 0:
            if trace_frames:
                video_time = frame_id / fps
                print(
                    f"[TRACE FRAME] {video_time:.2f}s frame={frame_id} decision=discard_empty_roi"
                )
            frame_id += frame_step
            continue

        processed = preprocess_roi(roi, profile, cv2)
        if save_debug_frames:
            cv2.imwrite(str(debug_dir / f"frame_{frame_id}.png"), processed)

        video_time = frame_id / fps
        last_sampled_video_time = video_time
        readings = reader.readtext(processed, allowlist=allowlist)
        frame_trace: list[str] = []
        if not readings:
            frame_trace.append("decision=no_ocr_text")
        for _bbox, text, probability in readings:
            confidence = float(probability)
            raw_text = str(text)
            if confidence < confidence_threshold:
                frame_trace.append(
                    f"raw={raw_text!r} confidence={confidence:.2f} "
                    "decision=below_confidence_threshold"
                )
                continue
            clock = parse_clock(raw_text)
            if not clock:
                frame_trace.append(
                    f"raw={raw_text!r} confidence={confidence:.2f} decision=unparseable_clock"
                )
                continue
            if tracker.last_clock is None:
                if not initial_clock_gate.accept(clock, video_time):
                    frame_trace.append(
                        f"raw={raw_text!r} parsed={clock} confidence={confidence:.2f} "
                        f"period={tracker.period} decision={initial_clock_gate.last_decision}"
                    )
                    continue
                opening_backfill = initial_clock_gate.take_confirmed_backfill()
                if opening_backfill is not None:
                    backfill_video_time, backfill_clock = opening_backfill
                    results.append((backfill_video_time, tracker.period, backfill_clock))
                    if trace_frames:
                        print(
                            f"[TRACE BACKFILL] {backfill_video_time:.2f}s "
                            f"period={tracker.period} clock={backfill_clock} "
                            "decision=confirmed_initial_clock_anchor"
                        )
            accepted = tracker.accept(clock, video_time)
            invalidated_period = tracker.take_invalidated_period()
            if invalidated_period is not None:
                invalid_period, invalid_start = invalidated_period
                retained_results = [
                    result
                    for result in results
                    if not (result[1] == invalid_period and result[0] >= invalid_start)
                ]
                removed_count = len(results) - len(retained_results)
                results = retained_results
                frame_trace.append(
                    f"raw={raw_text!r} parsed={clock} confidence={confidence:.2f} "
                    f"period={invalid_period} "
                    "decision=discard_temporally_compressed_period "
                    f"removed={removed_count}"
                )
            if not accepted:
                frame_trace.append(
                    f"raw={raw_text!r} parsed={clock} confidence={confidence:.2f} "
                    f"period={tracker.period} decision={tracker.last_decision}"
                )
                continue
            period, accepted_clock = accepted
            confirmed_backfills = tracker.take_confirmed_backfills()
            for confirmed_backfill in confirmed_backfills:
                results.append(confirmed_backfill)
                backfill_video_time, backfill_period, backfill_clock = confirmed_backfill
                if trace_frames:
                    print(
                        f"[TRACE BACKFILL] {backfill_video_time:.2f}s "
                        f"period={backfill_period} clock={backfill_clock} "
                        "decision=confirmed_gapped_sequence"
                    )
            results.append((video_time, period, accepted_clock))
            frame_trace.append(
                f"raw={raw_text!r} parsed={clock} confidence={confidence:.2f} "
                f"period={period} decision={tracker.last_decision}"
            )
            print(f"[{confidence:.2f}] {video_time:.2f}s ({period}) -> {accepted_clock}")

            accepted_seconds = clock_to_seconds(accepted_clock)
            if completed_period_index is not None and tracker.period_index > completed_period_index:
                # A tied game continued into overtime, so wait for that period to finish.
                completed_period_index = None
                completed_period_video_time = None
            if (
                tracker.period_index >= 3
                and accepted_seconds is not None
                and accepted_seconds <= tracker.period_end_max_seconds
            ):
                completed_period_index = tracker.period_index
                completed_period_video_time = video_time

        if trace_frames:
            print(f"[TRACE FRAME] {video_time:.2f}s frame={frame_id} " + " | ".join(frame_trace))

        frame_id += frame_step
        if (
            completed_period_index is not None
            and completed_period_video_time is not None
            and tracker.period_index == completed_period_index
            and frame_id / fps - completed_period_video_time >= post_final_period_seconds
        ):
            print(
                f"Stopping {post_final_period_seconds:.0f}s after "
                f"{tracker.period} reached its final seconds"
            )
            break

    capture.release()
    if not results:
        raise RuntimeError(
            "No valid clock readings found. Check the selected OCR profile and start hint."
        )

    trace = print if trace_frames else None
    results, removed_points = sanitize_timeline_results(results, trace=trace)
    results, temporal_removed = remove_temporally_impossible_results(
        results,
        trace=trace,
    )
    removed_points += temporal_removed
    completeness_errors = timeline_completeness_errors(results)
    if completeness_errors:
        raise RuntimeError("Incomplete full-game OCR timeline: " + "; ".join(completeness_errors))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["video_time_sec", "quarter", "game_clock"])
        writer.writerows((round(video, 2), period, clock) for video, period, clock in results)
    print(
        f"Saved {len(results)} timeline points to {output_path} "
        f"({removed_points} conflicting/duplicate points removed)"
    )
    return OcrRunStatistics(
        timeline_points=len(results),
        removed_points=removed_points,
        fps=fps,
        media_duration_seconds=media_duration_seconds,
        scan_start_seconds=start_seconds,
        scan_end_seconds=last_sampled_video_time,
        sampling_interval_seconds=interval_seconds,
    )


def probe_profiles(
    youtube_url: str,
    profiles: dict[str, dict[str, Any]],
    start_seconds: float,
    duration_seconds: float = 600,
    step_seconds: float = 30,
    cookies_from_browser: str | None = None,
    video_file: Path | None = None,
) -> dict[str, list[tuple[float, str, float]]]:
    """Sample a video and report which reusable layouts can read its clock."""
    try:
        import cv2
        import easyocr
        import yt_dlp
    except ImportError as exc:
        raise RuntimeError(
            "OCR dependencies are missing. Install opencv-python, easyocr, and yt-dlp."
        ) from exc

    stream_url = (
        str(video_file.resolve())
        if video_file is not None
        else get_stream_url(youtube_url, yt_dlp, cookies_from_browser)
    )
    capture = cv2.VideoCapture(stream_url)
    if not capture.isOpened():
        raise RuntimeError("Could not open the YouTube video stream")
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 25)
    languages = next(iter(profiles.values())).get("ocr", {}).get("languages", ["en"])
    reader = easyocr.Reader(languages, gpu=False)
    matches: dict[str, list[tuple[float, str, float]]] = {
        profile_name: [] for profile_name in profiles
    }

    sample_count = max(1, int(duration_seconds / step_seconds) + 1)
    for sample_index in range(sample_count):
        video_seconds = start_seconds + sample_index * step_seconds
        capture.set(cv2.CAP_PROP_POS_FRAMES, int(video_seconds * fps))
        ok, frame = capture.read()
        if not ok:
            break
        frame_height, frame_width = frame.shape[:2]

        for profile_name, profile in profiles.items():
            x, y, width, height = roi_pixels(profile, frame_width, frame_height)
            roi = frame[y : y + height, x : x + width]
            if roi.size == 0:
                continue
            processed = preprocess_roi(roi, profile, cv2)
            ocr_config = profile.get("ocr", {})
            readings = reader.readtext(
                processed,
                allowlist=str(ocr_config.get("allowlist", "0123456789:.")),
            )
            threshold = float(ocr_config.get("confidence_threshold", 0.4))
            valid = [
                (parse_clock(str(text)), float(probability))
                for _bbox, text, probability in readings
                if float(probability) >= threshold
            ]
            valid = [(clock, confidence) for clock, confidence in valid if clock]
            if valid:
                clock, confidence = max(valid, key=lambda reading: reading[1])
                matches[profile_name].append((video_seconds, str(clock), confidence))

    capture.release()
    return matches


def installed_package_version(*names: str) -> str | None:
    for name in names:
        try:
            return importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            continue
    return None


def physical_memory_bytes() -> int | None:
    try:
        return int(os.sysconf("SC_PAGE_SIZE")) * int(os.sysconf("SC_PHYS_PAGES"))
    except (AttributeError, OSError, TypeError, ValueError):
        return None


def write_run_metrics(
    output_path: Path,
    *,
    season_code: str,
    game_code: str,
    profile_name: str,
    source: str,
    timeline_path: Path,
    statistics: OcrRunStatistics,
    elapsed_seconds: float,
    started_at: datetime,
) -> None:
    """Persist reproducible end-to-end OCR timing and environment metadata."""
    scanned_minutes = statistics.scanned_video_seconds / 60
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "format_version": 1,
        "game": {
            "season_code": season_code,
            "game_code": game_code,
            "ocr_profile": profile_name,
            "source": source,
            "timeline_output": str(timeline_path),
        },
        "run": {
            "started_at_utc": started_at.isoformat(),
            "processing_wall_time_seconds": elapsed_seconds,
            "media_duration_seconds": statistics.media_duration_seconds,
            "scan_start_seconds": statistics.scan_start_seconds,
            "scan_end_seconds": statistics.scan_end_seconds,
            "scanned_video_seconds": statistics.scanned_video_seconds,
            "sampling_interval_seconds": statistics.sampling_interval_seconds,
            "timeline_points": statistics.timeline_points,
            "removed_points": statistics.removed_points,
            "processing_seconds_per_scanned_video_minute": (
                elapsed_seconds / scanned_minutes if scanned_minutes else None
            ),
            "scanned_video_seconds_per_processing_second": (
                statistics.scanned_video_seconds / elapsed_seconds if elapsed_seconds else None
            ),
        },
        "environment": {
            "operating_system": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor() or None,
            "cpu_count": os.cpu_count(),
            "physical_memory_bytes": physical_memory_bytes(),
            "python_version": platform.python_version(),
            "python_executable": Path(sys.executable).name,
            "packages": {
                "easyocr": installed_package_version("easyocr"),
                "opencv": installed_package_version("opencv-python", "opencv-python-headless"),
                "torch": installed_package_version("torch"),
                "yt_dlp": installed_package_version("yt-dlp"),
            },
        },
    }
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season-code", default="E2023")
    parser.add_argument("--game-code", default="333")
    parser.add_argument("--youtube-url")
    parser.add_argument("--youtube-id")
    parser.add_argument(
        "--video-file", type=Path, help="Use a downloaded local video instead of YouTube"
    )
    parser.add_argument("--profile", help="Override the OCR profile from the game catalog")
    parser.add_argument("--profiles-file", type=Path, default=DEFAULT_PROFILES_FILE)
    parser.add_argument("--catalog-file", type=Path, default=DEFAULT_CATALOG_FILE)
    parser.add_argument("--start-seconds", type=float)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--metrics-output",
        type=Path,
        help="Write end-to-end OCR timing and environment metrics as JSON",
    )
    parser.add_argument("--debug-dir", type=Path)
    parser.add_argument("--save-debug-frames", action="store_true")
    parser.add_argument(
        "--trace-frames",
        action="store_true",
        help=(
            "Print OCR text, confidence, parsed clock and accept/discard reason "
            "for every sampled frame"
        ),
    )
    parser.add_argument(
        "--cookies-from-browser",
        help="Load authenticated YouTube cookies from this browser (for example: chrome)",
    )
    parser.add_argument("--probe-profiles", action="store_true")
    parser.add_argument("--probe-duration-seconds", type=float, default=600)
    parser.add_argument("--probe-step-seconds", type=float, default=30)
    parser.add_argument("--list-profiles", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        profiles = load_profiles(args.profiles_file.resolve())
        if args.list_profiles:
            for name, profile in profiles.items():
                print(f"{name}: {profile.get('description', '')}")
            return 0

        games = load_game_catalog(args.catalog_file.resolve())
        game = find_game_config(games, args.season_code, args.game_code) or {}
        profile_name = args.profile or game.get("ocr_profile")
        if not profile_name or profile_name not in profiles:
            parser.error(f"Unknown or missing OCR profile: {profile_name!r}")

        youtube_url = args.youtube_url or game.get("youtube_url")
        youtube_id = args.youtube_id or game.get("youtube_id")
        if not youtube_url and youtube_id:
            youtube_url = youtube_url_from_id(str(youtube_id))
        if not youtube_url and not args.video_file:
            parser.error("Provide --youtube-url/--youtube-id or add the game to video_games.json")

        output_value = args.output or game.get("timeline_file")
        output_path = resolve_repo_path(
            output_value or f"video_timelines/{args.season_code}_{args.game_code}.csv"
        )
        debug_dir = resolve_repo_path(
            args.debug_dir or f"debug_frames/{args.season_code}_{args.game_code}"
        )
        start_seconds = (
            args.start_seconds
            if args.start_seconds is not None
            else float(game.get("start_hint_seconds", 0))
        )
        if args.probe_profiles:
            matches = probe_profiles(
                youtube_url=str(youtube_url),
                profiles=profiles,
                start_seconds=start_seconds,
                duration_seconds=args.probe_duration_seconds,
                step_seconds=args.probe_step_seconds,
                cookies_from_browser=args.cookies_from_browser,
                video_file=args.video_file,
            )
            for candidate_name, readings in matches.items():
                preview = ", ".join(
                    f"{video_seconds:.0f}s={clock} ({confidence:.2f})"
                    for video_seconds, clock, confidence in readings[:8]
                )
                print(
                    f"{candidate_name}: {len(readings)} valid samples{': ' + preview if preview else ''}"
                )
            return 0
        started_at = datetime.now(timezone.utc)
        started_counter = time.perf_counter()
        run_statistics = run_ocr(
            youtube_url=str(youtube_url),
            profile=profiles[str(profile_name)],
            start_seconds=start_seconds,
            output_path=output_path,
            debug_dir=debug_dir,
            save_debug_frames=args.save_debug_frames,
            cookies_from_browser=args.cookies_from_browser,
            video_file=args.video_file,
            trace_frames=args.trace_frames,
        )
        elapsed_seconds = time.perf_counter() - started_counter
        if args.metrics_output:
            metrics_path = resolve_repo_path(args.metrics_output)
            source = args.video_file.name if args.video_file is not None else str(youtube_url)
            write_run_metrics(
                metrics_path,
                season_code=args.season_code,
                game_code=args.game_code,
                profile_name=str(profile_name),
                source=source,
                timeline_path=output_path,
                statistics=run_statistics,
                elapsed_seconds=elapsed_seconds,
                started_at=started_at,
            )
            print(f"Saved OCR run metrics to {metrics_path}")
        return 0
    except (RuntimeError, ValueError) as exc:
        parser.exit(1, f"error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
